"""Shared entry point for the desktop tool and scheduled background runs."""
import argparse
import json
import logging
import sys
import time

from civit_helper.state import (RUNTIME, RunLock, Store, BusyError, TARGETS,
                                setup_logging, taipei_now)
from civit_helper.core import execute, automatic_allowed


def output(value):
    if sys.stdout:
        print(json.dumps(value, ensure_ascii=True), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Civit Helper')
    parser.add_argument('command', nargs='?', default='gui',
                        choices=['gui', 'run', 'login', 'inspect', 'doctor', 'status', 'schedule-xml'])
    parser.add_argument('--source', choices=['manual', 'scheduled'], default='manual')
    args = parser.parse_args(argv)
    if args.command == 'gui':
        from civit_helper.gui import launch
        launch()
        return 0
    if args.command == 'schedule-xml':
        from pathlib import Path
        from civit_helper.schedule import task_xml
        from civit_helper.state import ROOT
        RUNTIME.mkdir(exist_ok=True)
        (RUNTIME / 'schedule.xml').write_text(
            task_xml(ROOT, Path(sys.executable).with_name('pythonw.exe')), encoding='utf-16')
        return 0
    if args.command == 'status':
        store = Store()
        try:
            output(store.status())
        finally:
            store.close()
        return 0
    if args.command == 'run' and args.source == 'scheduled' and not automatic_allowed(taipei_now()):
        output({'status': 'waiting', 'message': '目前不是台灣時間 04:00 排程時段；不自動執行，需補跑請手動啟動。'})
        return 0
    store = None
    run_id = None
    try:
        with RunLock(RUNTIME / 'run.lock'):
            setup_logging(args.source + '/' + args.command)
            store = Store()
            day = taipei_now().date().isoformat()
            if (args.command == 'run' and not store.pending()
                    and all(store.progress(day)[k] >= n for k, n in TARGETS.items())):
                # Record it: otherwise the window keeps showing the previous diagnostic and
                # pressing 「立即執行」 looks like it did nothing.
                counts = store.progress(day)
                message = f'今天已完成（愛心 {counts["heart"]}/50、追蹤 {counts["follow"]}/3），不需要再執行。'
                run_id = store.start_run(args.source + '/' + args.command)
                store.end_run(run_id, 'complete', message)
                logging.info('run_id=%s already complete today; nothing to do', run_id)
                from civit_helper.history import write_history
                write_history(store)
                output({'status': 'complete', 'message': message, 'progress': counts})
                return 0
            run_id = store.start_run(args.source + '/' + args.command)
            logging.info('run_id=%s started', run_id)
            from civit_helper.notice import requires_warning, confirm_scheduled_run
            if requires_warning(args.command, args.source):
                message = '排程倒數 3 分鐘；關閉通知即可取消這次執行。'
                with store.db:
                    store.db.execute('UPDATE runs SET message=? WHERE id=?', (message, run_id))
                logging.info('run_id=%s %s', run_id, message)
                try:
                    accepted = confirm_scheduled_run()
                except Exception:
                    store.end_run(run_id, 'error', '無法顯示排程倒數通知，本次不執行。')
                    logging.error('run_id=%s countdown UI unavailable; no browser work started', run_id)
                    return 2
                if not accepted:
                    message = '使用者關閉通知，已取消這次排程；當日進度保留。'
                    store.end_run(run_id, 'cancelled', message)
                    logging.info('run_id=%s %s', run_id, message)
                    output({'status': 'cancelled', 'message': message})
                    return 0
                if taipei_now().date().isoformat() != day or not automatic_allowed(taipei_now()):
                    message = '已離開台灣時間 04:00 排程時段，本次不執行。'
                    store.end_run(run_id, 'waiting', message)
                    output({'status': 'waiting', 'message': message})
                    return 0
            from civit_helper.site import LoginRequired, VerificationRequired
            from civit_helper.bridge import BridgeError, ensure_extension_config
            from civit_helper.remote_site import BridgeSite
            try:
                ensure_extension_config()
                if args.command == 'doctor':
                    from civit_helper.diagnostics import check_connection
                    with store.db:
                        store.db.execute('UPDATE runs SET message=? WHERE id=?', ('等待連線診斷；請重新載入0.2.1擴充功能並按「立即連接」。此模式不操作網站。', run_id))
                    result = check_connection()
                elif args.command == 'login':
                    from civit_helper.login import open_daily_browser
                    open_daily_browser()
                    result = {'status': 'setup_required', 'message': '已開啟日常 Chrome 的 Civitai，請正常登入；載入擴充功能後按「檢查網站」。'}
                else:
                    with store.db:
                        store.db.execute('UPDATE runs SET message=? WHERE id=?', ('等待日常 Chrome 擴充功能連線，請確認已載入 Civit Helper。', run_id))
                    with BridgeSite(seconds=1200) as site:
                        if args.command == 'inspect':
                            diagnostic = site.inspect()
                            if diagnostic.get('logged_in'):
                                store.bind(diagnostic['account'])
                            (RUNTIME / 'diagnostic.json').write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding='utf-8')
                            result = {'status': 'ready' if diagnostic.get('logged_in') else 'login_required',
                                      'message': ('日常 Chrome 只讀檢查完成；尚未測試實際愛心與追蹤。' if diagnostic.get('logged_in') else
                                                  '擴充功能已連線；請在日常 Chrome 登入 Civitai。'),
                                      'diagnostic': diagnostic}
                        else:
                            result = execute(store, site)
            except Exception as exc:
                from civit_helper.site import VerificationRequired
                if isinstance(exc, LoginRequired):
                    status = 'login_required'
                elif isinstance(exc, VerificationRequired):
                    status = 'verification_required'
                else:
                    status = 'error'
                # Do not dump arbitrary browser exceptions: they may contain auth URLs.
                safe = str(exc) if isinstance(exc, (LoginRequired, VerificationRequired, ValueError, BridgeError)) else (
                    str(exc) if type(exc).__module__ == 'civit_helper.site' else
                    f'執行失敗（{type(exc).__name__}），進度已保留；請檢查網路、Chrome 或重新登入。')
                result = {'status': status, 'message': safe, 'progress': store.progress(day)}
            store.end_run(run_id, result['status'], result['message'])
            logging.info('run_id=%s result=%s', run_id, json.dumps(result, ensure_ascii=False))
            if args.command == 'run':
                from civit_helper.history import write_history
                write_history(store)
            output(result)
            return 0 if result['status'] in ('complete', 'ready', 'setup_required') else 2
    except BusyError as exc:
        output({'status': 'busy', 'message': str(exc)})
        return 5
    finally:
        if store:
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
