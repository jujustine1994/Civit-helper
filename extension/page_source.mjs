import {parse as parseDevalue} from 'devalue';

// Bundled inside the serialized function: no external imports at execution time.
export async function execute(cmd) {
  const fail = (code, message) => { const e = new Error(message); e.code = code; throw e; };
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const decode = payload => {
    if (Array.isArray(payload)) {
      if (payload.length !== 1) fail('SCHEMA', '網站回應無法可靠對應單一操作。');
      payload = payload[0];
    }
    if (!payload?.result || payload.error) fail('SITE_ERROR', '網站拒絕資料或操作，請檢查登入及網站限制。');
    const data = payload.result.data;
    if (typeof data === 'string') return parseDevalue(data);
    return data && typeof data === 'object' && 'json' in data ? data.json : data;
  };
  const today = () => new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Taipei', year: 'numeric', month: '2-digit', day: '2-digit'
  }).format(new Date());
  const windowValid = () => {
    if (Date.now() >= cmd.expiresAt || (cmd.day && today() !== cmd.day)) {
      fail('WINDOW_EXPIRED', '點擊前已跨日或達時間上限，未送出操作。');
    }
  };
  const visible = node => Boolean(node && (node.offsetWidth || node.offsetHeight || node.getClientRects().length));
  const waitFor = async finder => {
    const until = Date.now() + 20000;
    while (Date.now() < until) {
      windowValid();
      const found = finder();
      if (found) return found;
      await sleep(200);
    }
    fail('BUTTON_MISSING', '找不到可靠的操作入口，網站可能尚未載入或已變更。');
  };
  const read = async (path, params, headers = cmd.headers || {}) => {
    if (!/^\/api\/(auth\/session|trpc\/[a-zA-Z0-9.]+)$/.test(path)) fail('INVALID_PATH', '拒絕未授權資料路徑。');
    const url = new URL(path, location.origin);
    for (const [key, value] of Object.entries(params || {})) url.searchParams.set(key, value);
    const response = await fetch(url.href, {method: 'GET', credentials: 'same-origin',
      headers, cache: 'no-store', signal: AbortSignal.timeout(30000)});
    const contentType = response.headers.get('content-type') || '';
    let data = contentType.includes('json') ? await response.json() : null;
    if (path.startsWith('/api/trpc/')) {
      const normalize = entry => {
        if (!entry?.result || typeof entry.result.data !== 'string') return entry;
        const decoded = parseDevalue(entry.result.data);
        // Keep the Python bridge protocol JSON-only; metadata BigInts are strings.
        const plain = JSON.parse(JSON.stringify(decoded, (_key, value) => typeof value === 'bigint' ? String(value) : value));
        return {...entry, result: {...entry.result, data: {json: plain}}};
      };
      data = Array.isArray(data) ? data.map(normalize) : normalize(data);
    }
    return {status: response.status, contentType, data};
  };
  const query = async (method, input) => {
    const params = input === undefined ? {} : {input: JSON.stringify({json: input})};
    const response = await read('/api/trpc/' + method, params);
    if (response.status === 401) fail('LOGIN_REQUIRED', '請在日常 Chrome 先登入 Civitai。');
    if (response.status !== 200) fail('SITE_ERROR', '網站限制存取或資料請求失敗，進度保留。');
    return decode(response.data);
  };
  const account = async () => {
    const response = await read('/api/auth/session');
    const id = response.data?.user?.id;
    if (!id) fail('LOGIN_REQUIRED', '請在日常 Chrome 先登入 Civitai。');
    if (cmd.accountId && String(id) !== cmd.accountId) fail('ACCOUNT_CHANGED', '登入帳號已變更，停止以保護進度。');
    return String(id);
  };
  const state = async () => {
    if (cmd.kind === 'heart') {
      const data = await query('reaction.getMyImageReactions', {imageIds: [Number(cmd.target)]});
      if (!data || typeof data !== 'object' || Array.isArray(data)
          || Object.values(data).some(xs => !Array.isArray(xs) || xs.some(x => typeof x !== 'string'))) {
        fail('SCHEMA', '無法確認愛心狀態。');
      }
      return (data[cmd.target] || []).includes('Heart');
    }
    const data = await query('user.getFollowingUsers');
    if (!Array.isArray(data) || data.some(x => !Number.isInteger(x))) fail('SCHEMA', '無法確認追蹤狀態。');
    return data.includes(Number(cmd.target));
  };
  // Comments (#comment-<id>) carry their own reaction buttons; only the image's own controls count.
  const imageButtons = selector => [...document.querySelectorAll(selector)]
    .filter(button => visible(button) && !button.closest('[id^="comment-"]'));
  const heartButton = async () => {
    await waitFor(() => imageButtons('button[aria-label="Heart reaction"],button[aria-label="Add reaction"]')[0]);
    let heart = imageButtons('button[aria-label="Heart reaction"]');
    if (!heart.length) {
      const add = imageButtons('button[aria-label="Add reaction"]');
      if (add.length !== 1) fail('AMBIGUOUS', '表情入口不唯一，停止以避免操作錯誤。');
      add[0].click(); // Opens controls only; does not react.
    }
    await waitFor(() => imageButtons('button[aria-label="Heart reaction"]')[0]);
    heart = imageButtons('button[aria-label="Heart reaction"]');
    if (heart.length !== 1) fail('AMBIGUOUS', '愛心按鈕不唯一，停止以避免操作錯誤。');
    return heart[0];
  };
  const followButton = async (probe = false) => {
    const matches = () => [...document.querySelectorAll('button')].filter(button =>
      visible(button) && (probe ? /^(Follow(?: back)?|Unfollow)$/i : /^Follow(?: back)?$/i).test(button.textContent.trim()));
    await waitFor(() => matches()[0]);
    const buttons = matches();
    if (buttons.length !== 1) fail('AMBIGUOUS', '追蹤按鈕不唯一，停止以避免操作錯誤。');
    return buttons[0];
  };
  try {
    if (location.origin !== 'https://civitai.red') fail('WRONG_TAB', '工具分頁已離開 Civitai，本次停止。');
    if (cmd.marker && sessionStorage.getItem('civit-helper-owned') !== cmd.marker) fail('WRONG_TAB', '工具分頁標記失效，本次停止。');
    if (/just a moment|attention required|security verification/i.test(document.title)) fail('VERIFICATION_REQUIRED', '網站需要人工安全驗證，請自行處理。');
    windowValid();
    if (cmd.op === 'read') return {ok: true, result: await read(cmd.path, cmd.params, cmd.headers)};
    if (cmd.op === 'probeHeart') { await heartButton(); return {ok: true, result: {heart_button_count: 1}}; }
    if (cmd.op === 'probeFollow') { await followButton(true); return {ok: true, result: {follow_button_count: 1}}; }
    if (cmd.op !== 'action' || !['heart', 'follow'].includes(cmd.kind) || !/^\d+$/.test(cmd.target)) fail('INVALID_COMMAND', '拒絕未知操作。');
    const expectedPath = cmd.kind === 'heart' ? '/images/' + cmd.target : '/user/' + encodeURIComponent(cmd.username);
    if (location.pathname !== expectedPath) fail('WRONG_TARGET', '分頁目標與操作不一致，本次停止。');
    await account();
    if (await state()) fail('ALREADY_DONE', '目標已操作，拒絕再次點擊。');
    const button = cmd.kind === 'heart' ? await heartButton() : await followButton();
    await waitFor(() => !button.disabled);
    if (await state()) fail('ALREADY_DONE', '操作前狀態已變更，拒絕重複點擊。');
    await account();
    const method = cmd.kind === 'heart' ? 'reaction.toggle' : 'user.toggleFollow';
    const originalFetch = window.fetch;
    let timer;
    let wrapped;
    const accepted = new Promise((resolve, reject) => {
      timer = setTimeout(() => reject(Object.assign(new Error('網站未回覆操作結果，保留待確認紀錄。'), {code: 'UNCONFIRMED'})), 30000);
      wrapped = async function (...args) {
        let guarded = false;
        try {
          const url = new URL(typeof args[0] === 'string' || args[0] instanceof URL ? args[0] : args[0].url, location.origin);
          const options = args[1] || {};
          if (url.origin === location.origin && url.pathname.startsWith('/api/trpc/')
              && (options.method || args[0]?.method || 'GET').toUpperCase() === 'POST') {
            const raw = options.body ?? (args[0] instanceof Request ? await args[0].clone().text() : '');
            const body = JSON.parse(raw);
            const inputs = body.json ? [body.json] : Object.values(body).map(x => x?.json);
            const matching = url.pathname === '/api/trpc/' + method && inputs.length === 1 && inputs.every(input => input && (cmd.kind === 'heart'
              ? input.entityType === 'image' && input.entityId === Number(cmd.target) && input.reaction === 'Heart'
              : input.targetUserId === Number(cmd.target)));
            if (!matching) {
              const error = Object.assign(new Error('按鈕請求與預定圖片或作者不一致，已阻止送出。'), {code: 'WRONG_TARGET'});
              reject(error);
              throw error;
            }
            windowValid();
            guarded = true;
          }
        } catch (error) {
          reject(Object.assign(new Error('無法確認操作目標，已阻止請求送出。'), {code: error.code || 'WRONG_TARGET'}));
          throw error;
        }
        const response = await originalFetch.apply(this, args);
        if (guarded) {
          if (!response.ok) reject(Object.assign(new Error('網站未接受操作，保留待確認紀錄。'), {code: 'UNCONFIRMED'}));
          else {
            try { resolve(await response.clone().json()); }
            catch { reject(Object.assign(new Error('網站操作回應格式不明，保留待確認紀錄。'), {code: 'UNCONFIRMED'})); }
          }
        }
        return response;
      };
      window.fetch = wrapped;
    });
    try {
      windowValid();
      button.click();
      const result = decode(await accepted);
      if ((cmd.kind === 'heart' && result !== 'created') || (cmd.kind === 'follow' && result?.following !== true)) fail('UNCONFIRMED', '網站未確認新增操作，保留待確認紀錄。');
      return {ok: true, result: {accepted: true}};
    } finally {
      clearTimeout(timer);
      if (window.fetch === wrapped) window.fetch = originalFetch;
    }
  } catch (error) {
    return {ok: false, code: error.code || 'PAGE_ERROR', error: error.code ? error.message : '頁面操作失敗，進度保留；請檢查網路與網站。'};
  }
}
