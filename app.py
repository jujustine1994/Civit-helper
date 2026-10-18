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
                        choices=['gui', 'run', 'login', 'inspect', 'status', 'schedule-xml'])
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
        output({'status': 'waiting', 'message': '台灣時間 04:00 前，等待當日排程。'})
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
                output({'status': 'complete', 'progress': store.progress(day)})
                return 0
            run_id = store.start_run(args.source + '/' + args.command)
            logging.info('run_id=%s started', run_id)
            from civit_helper.site import ChromeSite, LoginRequired, VerificationRequired
            try:
                with ChromeSite(headed=args.command == 'login',
                                seconds=1800 if args.command == 'login' else 1200) as site:
                    if args.command == 'login':
                        logging.info('等待使用者在專用 Chrome 完成登入；不需要提供密碼給工具。')
                        while True:
                            if site.page.is_closed():
                                result = {'status': 'login_required', 'message': '登入視窗已關閉，可再次使用「登入／重新登入」。'}
                                break
                            try:
                                account = site.account()
                                store.bind(account)
                                result = {'status': 'ready', 'message': '登入已保存；可按「檢查網站」或「立即執行」。'}
                                break
                            except (LoginRequired, VerificationRequired):
                                site.page.wait_for_timeout(2000)
                    elif args.command == 'inspect':
                        diagnostic = site.inspect()
                        if diagnostic.get('logged_in'):
                            store.bind(diagnostic['account'])
                        (RUNTIME / 'diagnostic.json').write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding='utf-8')
                        result = {'status': 'ready' if diagnostic.get('logged_in') else 'login_required',
                                  'message': ('網站只讀檢查完成；尚未測試實際愛心與追蹤。' if diagnostic.get('logged_in') else
                                              '背景 Chrome 及圖片來源正常；請先登入工具專用 Chrome。'),
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
                safe = str(exc) if isinstance(exc, (LoginRequired, VerificationRequired, ValueError)) else (
                    str(exc) if type(exc).__module__ == 'civit_helper.site' else
                    f'執行失敗（{type(exc).__name__}），進度已保留；請檢查網路、Chrome 或重新登入。')
                result = {'status': status, 'message': safe, 'progress': store.progress(day)}
            store.end_run(run_id, result['status'], result['message'])
            logging.info('run_id=%s result=%s', run_id, json.dumps(result, ensure_ascii=False))
            output(result)
            return 0 if result['status'] in ('complete', 'ready') else 2
    except BusyError as exc:
        output({'status': 'busy', 'message': str(exc)})
        return 5
    finally:
        if store:
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
