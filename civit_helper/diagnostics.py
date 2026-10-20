import json
from .bridge import Bridge, BridgeError
from .daily_chrome import DailyChrome
from .state import RUNTIME, taipei_now


def check_connection(timeout=180):
    """Only health/ping traffic; never creates tabs or touches website data."""
    report = {'checked_at': taipei_now().isoformat(), 'website_actions': False}
    with Bridge() as bridge, DailyChrome():  # Chrome after the bridge listens (see BridgeSite).
        try:
            pong = bridge.command('ping', timeout=timeout)
            if not isinstance(pong, dict) or not isinstance(pong.get('version'), str):
                raise BridgeError('擴充功能回應格式不符，請重新載入 0.2.1 或更新版本。')
            report.update(status='ready', message='擴充功能連線成功；這次僅測試連線，未操作 Civitai。', extension=pong)
        except BridgeError as exc:
            message = '擴充功能仍使用舊程式，請在卡片按重新載入，確認版本 0.2.1。' if getattr(exc, 'code', '') == 'INVALID_COMMAND' else str(exc)
            report.update(status='error', message=message)
        report['transport'] = bridge.diagnostics()
    RUNTIME.mkdir(exist_ok=True)
    (RUNTIME / 'connection-diagnostic.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report
