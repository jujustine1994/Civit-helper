import json
import threading
import time
from urllib.parse import quote

from .bridge import Bridge, BridgeError
from .core import RunWindowExpired
from .daily_chrome import DailyChrome, chrome_windows, minimize_windows
from .site import ChromeSite, SiteError, LoginRequired, VerificationRequired, decode_trpc, follow_state
from .state import taipei_now


class BridgeSite(ChromeSite):
    """Same core interface, implemented by the extension in the user's Chrome."""
    tool_windows = ()

    def __enter__(self):
        self.bridge = Bridge()
        self.bridge.__enter__()
        self.tool_windows = []
        self.chrome = None
        try:
            # Start Chrome only after the bridge listens, so the extension's onStartup poll
            # connects at once instead of waiting ~30 s for the next alarm.
            self.chrome = DailyChrome()
            self.chrome.__enter__()
            # Chrome ignores the extension's minimized state on Windows (seen live 2026-10-20),
            # so the window that appears during init is minimized from here instead.
            before = set(chrome_windows())
            done = threading.Event()

            def watch():
                while not done.wait(0.2):
                    for hwnd in chrome_windows():
                        if hwnd not in before and hwnd not in self.tool_windows:
                            self.tool_windows.append(hwnd)
                    minimize_windows(self.tool_windows)

            watcher = threading.Thread(target=watch, daemon=True)
            watcher.start()
            try:
                data = self.bridge.command('init', timeout=110)
            finally:
                done.set()
                watcher.join(timeout=2)
            minimize_windows(self.tool_windows)
            self.client_headers = data['headers']
            self.feed_filters = data['filters']
            if 'browsingLevel' not in self.feed_filters:
                raise SiteError('無法確認日常 Chrome 的圖片瀏覽範圍，已停止。')
            return self
        except BaseException:
            self.__exit__()
            raise

    def __exit__(self, *args):
        try:
            self.bridge.command('close', timeout=10)
        except BridgeError:
            import logging
            logging.warning('未能確認工具最小化視窗已關閉；未操作日常其他視窗。')
        finally:
            try:
                if self.chrome:
                    self.chrome.__exit__(*args)
            finally:
                self.bridge.__exit__()

    def _get_json(self, path, params=None, headers=None):
        self._budget()
        try:
            result = self.bridge.command('read', path=path, params=params, headers=headers or {})
        except BridgeError as exc:
            self._translate(exc)
        status = result.get('status')
        if status == 401:
            raise LoginRequired('請先在安裝擴充功能的日常 Chrome 登入 Civitai。')
        if status in (403, 429):
            raise VerificationRequired('網站要求驗證或限制存取，本次停止。')
        if status != 200 or 'json' not in result.get('contentType', ''):
            raise SiteError('網站資料讀取失敗或需要人工檢查，進度保留。')
        return result['data']

    def query(self, method, data=None):
        headers = {**self.client_headers, 'x-client-date': str(int(time.time() * 1000))}
        params = {'input': json.dumps({'json': data}, separators=(',', ':'))} if data is not None else None
        return decode_trpc(self._get_json('/api/trpc/' + method, params, headers))

    def navigate(self, path):
        self._budget()
        try:
            self.bridge.command('navigate', path=path)
        except BridgeError as exc:
            self._translate(exc)
        finally:
            minimize_windows(self.tool_windows)

    @staticmethod
    def _translate(exc):
        code = getattr(exc, 'code', None)
        if code == 'WINDOW_EXPIRED':
            raise RunWindowExpired() from exc
        if code == 'LOGIN_REQUIRED':
            raise LoginRequired(str(exc)) from exc
        if code == 'VERIFICATION_REQUIRED':
            raise VerificationRequired(str(exc)) from exc
        raise SiteError(str(exc)) from exc

    def apply(self, kind, target):
        if self.state(kind, target) is not False:
            raise SiteError('目標已操作或狀態不明，拒絕再次點擊。')
        args = {'kind': kind, 'target': str(target), 'accountId': self.account(),
                'day': self.work_day,
                'expiresAt': min(self.write_expires_at, int((time.time() + 110) * 1000)),
                'headers': {**self.client_headers, 'x-client-date': str(int(time.time() * 1000))}}
        if kind == 'follow':
            args['username'] = self._creator_name(target)
        if not self.before_write():
            raise RunWindowExpired()
        try:
            result = self.bridge.command('action', timeout=110, **args)
        except BridgeError as exc:
            self._translate(exc)
        finally:
            minimize_windows(self.tool_windows)
        if not isinstance(result, dict) or result.get('accepted') is not True:
            raise SiteError('未收到可靠的操作成功確認，進度保留。')

    def inspect(self):
        result = {'browser_mode': 'daily_chrome_extension', 'frontend_observed': bool(self.client_headers),
                  'write_actions_tested': False}
        try:
            result['account'] = self.account()
            result['logged_in'] = True
            follow_state(self.query('user.getFollowingUsers'), result['account'])
            result['following_readable'] = True
        except LoginRequired as exc:
            result.update(logged_in=False, message=str(exc))
        data = self.query('image.getInfinite', {**self.feed_filters, 'limit': 3, 'sort': 'Newest',
                                               'period': 'AllTime', 'types': ['image']})
        batch = self._batch(data.get('items', []))
        if not batch:
            raise SiteError('未取得圖片來源，網站尚未就緒。')
        result['candidate_count'] = len(batch)
        self.navigate('/images/' + batch[0]['image'])
        result.update(self.bridge.command('probeHeart'))
        if result.get('logged_in'):
            result['heart_state_readable'] = type(self.state('heart', batch[0]['image'])) is bool
        self.navigate('/user/' + quote(self._creator_name(batch[0]['author']), safe=''))
        result.update(self.bridge.command('probeFollow'))
        return result
