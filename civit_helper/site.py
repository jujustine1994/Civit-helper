"""Chrome adapter: authenticated reads, normal visible-page button actions.

No password extraction, stealth patches, CAPTCHA handling or direct write API.
"""
import json
import logging
import random
import re
import time
from urllib.parse import quote, parse_qs, urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from .state import RUNTIME

BASE = 'https://civitai.red'


class SiteError(RuntimeError):
    pass


class LoginRequired(SiteError):
    pass


class VerificationRequired(SiteError):
    pass


def decode_trpc(payload):
    if isinstance(payload, list):
        if len(payload) != 1:
            raise SiteError('網站回傳了不符預期的多筆資料，已停止。')
        payload = payload[0]
    if not isinstance(payload, dict) or 'error' in payload:
        raise SiteError('網站拒絕資料請求；可能需重新登入或網站介面已變更。')
    try:
        data = payload['result']['data']
    except (KeyError, TypeError) as exc:
        raise SiteError('網站回應格式已變更，已停止。') from exc
    return data.get('json') if isinstance(data, dict) and 'json' in data else data


def reaction_state(data, target):
    if not isinstance(data, dict) or any(
            not isinstance(v, list) or any(not isinstance(x, str) for x in v) for v in data.values()):
        raise SiteError('無法確認愛心狀態：網站回應格式已變更。')
    return 'Heart' in data.get(str(target), [])


class ChromeSite:
    def __init__(self, *, headed=False, seconds=1200):
        self.headed = headed
        self.deadline = time.monotonic() + seconds
        self.client_headers = {}
        self.usernames = {}
        self.seed = []
        self.feed_filters = {}
        self.account_id = None
        self.browser = None
        self.playwright = None

    def __enter__(self):
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch_persistent_context(
                str(RUNTIME / 'chrome-profile'), channel='chrome', headless=not self.headed,
                viewport={'width': 1280, 'height': 900}, locale='en-US',
                timezone_id='Asia/Taipei', accept_downloads=False)
            self.page = self.browser.pages[0] if self.browser.pages else self.browser.new_page()
            self.page.set_default_timeout(15000)
            self.page.on('response', self._observe)
            self.navigate('/images')
            # The feed's own public request supplies current frontend headers.
            for _ in range(30):
                if self.client_headers:
                    break
                if not self.headed:
                    self.check_page()
                self.page.wait_for_timeout(500)
            return self
        except BaseException:
            self.__exit__()
            raise

    def __exit__(self, *args):
        try:
            if self.browser:
                self.browser.close()
        finally:
            if self.playwright:
                self.playwright.stop()

    def _budget(self):
        if time.monotonic() >= self.deadline:
            raise SiteError('本次執行達時間上限，保留進度等待補跑。')

    def _observe(self, response):
        if not response.url.startswith(BASE + '/api/trpc/'):
            return
        headers = response.request.headers
        if headers.get('x-client') == 'web':
            self.client_headers = {k: v for k, v in headers.items()
                                   if k in ('x-client', 'x-client-version')}
        if response.url.split('?')[0] == BASE + '/api/trpc/image.getInfinite' and response.ok:
            try:
                raw = parse_qs(urlparse(response.request.url).query).get('input', ['{}'])[0]
                original = json.loads(raw).get('json', {})
                self.feed_filters = {key: value for key, value in original.items()
                                     if key in ('browsingLevel', 'excludedTagIds', 'excludedUserIds',
                                                'hideAutoResources', 'hideManualResources', 'hideChallenges')}
                data = decode_trpc(response.json())
                if isinstance(data, dict) and isinstance(data.get('items'), list):
                    self.seed = data['items']
            except Exception:
                pass  # Diagnostic feed is optional; strict reads below still fail closed.

    def check_page(self):
        title = self.page.title().lower()
        if any(x in title for x in ('just a moment', 'attention required', 'security verification')):
            raise VerificationRequired('網站要求人工安全驗證；請使用「登入／重新登入」。')
        if '/login' in self.page.url or '/auth/signin' in self.page.url:
            raise LoginRequired('尚未登入或登入已失效，請先使用「登入／重新登入」。')

    def navigate(self, path):
        self._budget()
        r = self.page.goto(BASE + path, wait_until='domcontentloaded', timeout=45000)
        if not self.headed:
            self.check_page()
        if r and r.status >= 400 and not self.headed:
            raise SiteError(f'網站頁面無法載入（HTTP {r.status}），稍後再試。')

    def _get_json(self, path, params=None, headers=None):
        self._budget()
        r = self.browser.request.get(BASE + path, params=params, headers=headers, timeout=30000)
        if r.status == 401:
            raise LoginRequired('網站拒絕已登入資料請求，請重新登入或執行網站檢查。')
        if r.status in (403, 429):
            raise VerificationRequired(f'網站限制存取（HTTP {r.status}），已停止；請稍後檢查。')
        if not r.ok:
            raise SiteError(f'網站資料請求失敗（HTTP {r.status}），保留進度。')
        if 'json' not in r.headers.get('content-type', ''):
            raise VerificationRequired('網站回傳非資料頁面，可能需要人工驗證。')
        return r.json()

    def query(self, method, data=None):
        if not self.client_headers:
            raise SiteError('未取得網站正常資料請求，請執行「檢查網站」。')
        headers = {**self.client_headers, 'x-client-date': str(int(time.time() * 1000)),
                   'referer': self.page.url}
        params = {'input': json.dumps({'json': data}, separators=(',', ':'))} if data is not None else None
        return decode_trpc(self._get_json('/api/trpc/' + method, params, headers))

    def account(self):
        data = self._get_json('/api/auth/session')
        if not isinstance(data, dict) or not isinstance(data.get('user'), dict) or not data['user'].get('id'):
            raise LoginRequired('尚未登入或登入已失效，請先使用「登入／重新登入」。')
        account = str(data['user']['id'])
        if self.account_id is not None and self.account_id != account:
            raise SiteError('執行中登入帳號變更，已停止以保護進度。')
        self.account_id = account
        return account

    def state(self, kind, target):
        self.account()  # Every operation must still belong to the bound session.
        if kind == 'heart':
            return reaction_state(self.query('reaction.getMyImageReactions', {'imageIds': [int(target)]}), target)
        if kind == 'follow':
            data = self.query('user.getFollowingUsers')
            if not isinstance(data, list) or any(type(x) is not int for x in data):
                raise SiteError('無法確認追蹤名單：網站回應格式已變更。')
            return int(target) in data
        raise ValueError('unknown action kind')

    def _creator_name(self, target):
        if target not in self.usernames:
            data = self.query('user.getCreator', {'id': int(target)})
            if not isinstance(data, dict) or not isinstance(data.get('username'), str):
                raise SiteError('無法辨識作者，網站資料可能已變更。')
            self.usernames[target] = data['username']
        return self.usernames[target]

    def apply(self, kind, target):
        if self.state(kind, target) is not False:
            raise SiteError('目標已操作或狀態不明，拒絕再次點擊。')
        if kind == 'heart':
            self.navigate('/images/' + str(int(target)))
            button = self.page.locator('button[aria-label="Heart reaction"]')
            if button.count() == 0:
                add = self.page.get_by_role('button', name='Add reaction', exact=True)
                if add.count() == 1:
                    add.click()
            button.wait_for(state='visible')
            method = 'reaction.toggle'
        elif kind == 'follow':
            self.navigate('/user/' + quote(self._creator_name(target), safe=''))
            button = self.page.get_by_role('button', name=re.compile(r'^Follow(?: back)?$', re.I))
            button.wait_for(state='visible')
            method = 'user.toggleFollow'
        else:
            raise ValueError('unknown action kind')
        if button.count() != 1:
            raise SiteError('找到多個可能按鈕，已停止以避免操作錯誤目標。')
        # Recheck after navigating; the UI itself is optimistic and isn't proof.
        if self.state(kind, target) is not False:
            raise SiteError('操作前狀態已變更，已停止以避免取消既有操作。')
        with self.page.expect_response(
                lambda r: r.url.startswith(BASE + '/api/trpc/') and method in r.url.split('?')[0]
                and r.request.method == 'POST', timeout=30000) as received:
            button.click()
        response = received.value
        if not response.ok:
            raise SiteError(f'網站未接受操作（HTTP {response.status}），保留待確認紀錄。')
        result = decode_trpc(response.json())
        if kind == 'follow' and (not isinstance(result, dict) or result.get('following') is not True):
            raise SiteError('網站未確認新增追蹤，保留待確認紀錄。')
        if kind == 'heart' and result != 'created':
            raise SiteError('網站未確認新增愛心，保留待確認紀錄。')
        self.page.wait_for_timeout(600)

    def _batch(self, items):
        batch = []
        for item in items:
            if not isinstance(item, dict) or type(item.get('id')) is not int:
                raise SiteError('圖片清單格式已變更，停止搜尋。')
            user = item.get('user') or {}
            author = item.get('userId') or user.get('id')
            if type(author) is not int:
                raise SiteError('圖片缺少可靠的作者識別碼，停止搜尋。')
            if user.get('username'):
                self.usernames[str(author)] = user['username']
            batch.append({'image': str(item['id']), 'author': str(author)})
        return batch

    def candidates(self):
        seen = set()
        # Different source routes prevent cycling through the same popular authors.
        sources = [('Newest', 'AllTime'), ('Most Reactions', 'Day'),
                   ('Most Reactions', 'Week'), ('Newest', 'Week'), ('Most Comments', 'Month')]
        random.shuffle(sources)
        if self.seed:
            batch = self._batch(self.seed)
            seen.update(x['image'] for x in batch)
            yield batch
        for sort, period in sources:
            cursor = None
            cursors = set()
            stagnant = 0
            for _ in range(100):
                self._budget()
                if 'browsingLevel' not in self.feed_filters:
                    raise SiteError('無法確認目前圖片瀏覽範圍，已停止以保留既有內容設定。')
                params = {**self.feed_filters, 'limit': 50, 'sort': sort, 'period': period, 'types': ['image']}
                if cursor is not None:
                    params['cursor'] = cursor
                data = self.query('image.getInfinite', params)
                if not isinstance(data, dict) or not isinstance(data.get('items'), list):
                    raise SiteError('網站搜尋結果格式已變更，無法繼續尋找作者。')
                batch = [x for x in self._batch(data['items']) if x['image'] not in seen]
                seen.update(x['image'] for x in batch)
                if batch:
                    yield batch
                    stagnant = 0
                else:
                    stagnant += 1
                cursor = data.get('nextCursor')
                marker = json.dumps(cursor, sort_keys=True)
                if cursor is None or marker in cursors or stagnant >= 2:
                    break
                cursors.add(marker)
        logging.warning('所有搜尋來源停滯或達本次搜尋上限，等待下次補跑。')

    def inspect(self):
        result = {'background_chrome': not self.headed, 'page_loaded': True,
                  'frontend_observed': bool(self.client_headers)}
        try:
            result['account'] = self.account()
            result['logged_in'] = True
            following = self.query('user.getFollowingUsers')
            result['following_readable'] = isinstance(following, list)
        except LoginRequired as exc:
            result.update(logged_in=False, message=str(exc))
        # Public feed validates source expansion even before first login.
        data = self.query('image.getInfinite', {**self.feed_filters, 'limit': 3, 'sort': 'Newest', 'period': 'AllTime', 'types': ['image']})
        batch = self._batch(data.get('items', []))
        result['candidate_count'] = len(batch)
        if batch:
            self.navigate('/images/' + batch[0]['image'])
            self.page.wait_for_timeout(1500)
            result['heart_button_count'] = self.page.locator('button[aria-label="Heart reaction"]').count()
            result['add_reaction_count'] = self.page.get_by_role('button', name='Add reaction', exact=True).count()
            if result.get('logged_in'):
                result['heart_state_readable'] = type(self.state('heart', batch[0]['image'])) is bool
        result['write_actions_tested'] = False
        return result
