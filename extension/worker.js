import {runPageCommand} from './page.mjs';

const BASE = 'https://civitai.red';
let ownedId = null;
let metadata = null;
let polling = false;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const fail = (code, message) => { const error = new Error(message); error.code = code; throw error; };

chrome.webRequest.onBeforeSendHeaders.addListener(details => {
  if (details.tabId !== ownedId || new URL(details.url).pathname !== '/api/trpc/image.getInfinite') return;
  const values = Object.fromEntries((details.requestHeaders || []).map(x => [x.name.toLowerCase(), x.value]));
  if (values['x-client'] !== 'web') return;
  try {
    const original = JSON.parse(new URL(details.url).searchParams.get('input') || '{}').json || {};
    const keys = ['browsingLevel', 'excludedTagIds', 'excludedUserIds', 'hideAutoResources', 'hideManualResources', 'hideChallenges'];
    metadata = {headers: {'x-client': 'web', 'x-client-version': values['x-client-version'] || ''},
      filters: Object.fromEntries(Object.entries(original).filter(([key]) => keys.includes(key)))};
  } catch { /* Missing metadata fails closed during init. */ }
}, {urls: [BASE + '/api/trpc/image.getInfinite*']}, ['requestHeaders']);

async function waitLoaded(tabId) {
  const until = Date.now() + 45000;
  while (Date.now() < until) {
    const tab = await chrome.tabs.get(tabId);
    if (tab.status === 'complete') return tab;
    await sleep(200);
  }
  fail('LOAD_TIMEOUT', '工具分頁載入逾時，請檢查網站。');
}

// Chrome on Windows may ignore state:'minimized' at creation or restore the window on navigation.
async function keepMinimized(windowId) {
  try {
    const current = await chrome.windows.get(windowId);
    if (current.state !== 'minimized') await chrome.windows.update(windowId, {state: 'minimized', focused: false});
  } catch { /* Ownership checks elsewhere decide whether the run continues. */ }
}

async function ownedTab() {
  const {ownedTab: saved} = await chrome.storage.session.get('ownedTab');
  if (!saved) fail('TAB_CLOSED', '工具分頁尚未建立，請重新執行。');
  let tab;
  try { tab = await chrome.tabs.get(saved.id); } catch { fail('TAB_CLOSED', '工具分頁已關閉，本次停止。'); }
  if (!tab.url?.startsWith(BASE + '/')) fail('WRONG_TAB', '工具分頁已被導向其他網站，本次停止。');
  const results = await chrome.scripting.executeScript({target: {tabId: tab.id},
    func: () => sessionStorage.getItem('civit-helper-owned')});
  if (results[0]?.result !== saved.marker) fail('WRONG_TAB', '工具分頁標記失效，本次停止。');
  ownedId = tab.id;
  return {tab, marker: saved.marker};
}

async function initialize() {
  const {ownedTab: saved} = await chrome.storage.session.get('ownedTab');
  let existing = false;
  if (saved) {
    try { await chrome.tabs.get(saved.id); existing = true; } catch { /* A closed tab can be recreated at the start of a new run. */ }
  }
  if (existing) {
    await ownedTab();
  } else {
    const taskWindow = await chrome.windows.create({url: BASE + '/images', type: 'normal', state: 'minimized', focused: false});
    const tab = taskWindow.tabs?.[0];
    if (!tab?.id) fail('WINDOW_FAILED', '無法建立工具專用最小化視窗。');
    ownedId = tab.id;
    await keepMinimized(taskWindow.id);
    await waitLoaded(tab.id);
    const marker = crypto.randomUUID();
    await chrome.scripting.executeScript({target: {tabId: tab.id},
      func: value => sessionStorage.setItem('civit-helper-owned', value), args: [marker]});
    await chrome.storage.session.set({ownedTab: {id: tab.id, marker, windowId: taskWindow.id}});
  }
  const {tab} = await ownedTab();
  metadata = null;
  await chrome.tabs.update(tab.id, {url: BASE + '/images'});
  await chrome.tabs.reload(tab.id);
  await waitLoaded(tab.id);
  await keepMinimized(tab.windowId);
  const until = Date.now() + 15000;
  while (!metadata && Date.now() < until) await sleep(250);
  if (!metadata || !('browsingLevel' in metadata.filters)) fail('FEED_MISSING', '尚未取得網站圖片來源，請確認登入或安全驗證。');
  return metadata;
}

async function navigate(path) {
  if (!/^\/(images\/\d+|images|user\/[^/?#]+)$/.test(path)) fail('INVALID_PATH', '拒絕未知頁面路徑。');
  const {tab} = await ownedTab();
  await chrome.tabs.update(tab.id, {url: BASE + path, active: false});
  await waitLoaded(tab.id);
  await keepMinimized(tab.windowId);
  await ownedTab();
}

export async function dispatch(command) {
  if (Date.now() >= command.expiresAt) fail('WINDOW_EXPIRED', '命令已過期，沒有操作。');
  if (command.op === 'ping') return {version: chrome.runtime.getManifest().version, extensionId: chrome.runtime.id};
  if (command.op === 'init') return initialize();
  if (command.op === 'close') {
    const {ownedTab: saved} = await chrome.storage.session.get('ownedTab');
    if (!saved) return {closed: true};
    let tab;
    try { tab = await chrome.tabs.get(saved.id); } catch { await chrome.storage.session.remove('ownedTab'); return {closed: true}; }
    await ownedTab();
    if (tab.windowId !== saved.windowId) fail('WRONG_TAB', '工具分頁已移到其他視窗，保留由使用者處理。');
    const tabs = await chrome.tabs.query({windowId: saved.windowId});
    if (tabs.length === 1) await chrome.windows.remove(saved.windowId);
    else await chrome.tabs.remove(saved.id);
    await chrome.storage.session.remove('ownedTab');
    ownedId = null;
    return {closed: true};
  }
  if (command.op === 'navigate') { await navigate(command.path); return {loaded: true}; }
  if (!['read', 'action', 'probeHeart', 'probeFollow'].includes(command.op)) fail('INVALID_COMMAND', '拒絕未知操作。');
  if (command.op === 'action') {
    if (!['heart', 'follow'].includes(command.kind) || !/^\d+$/.test(command.target)) fail('INVALID_COMMAND', '操作目標格式不正確。');
    await navigate(command.kind === 'heart' ? '/images/' + command.target : '/user/' + encodeURIComponent(command.username));
  }
  const {tab, marker} = await ownedTab();
  const results = await chrome.scripting.executeScript({target: {tabId: tab.id}, world: 'MAIN',
    func: runPageCommand, args: [{...command, marker}]});
  const result = results[0]?.result;
  if (!result?.ok) fail(result?.code || 'PAGE_ERROR', result?.error || '工具分頁沒有回覆結果。');
  return result.result;
}

export async function poll() {
  if (polling) return;
  polling = true;
  let stage = 'config';
  try {
    const configResponse = await fetch(chrome.runtime.getURL('local-config.json'), {cache: 'no-store'});
    if (!configResponse.ok) throw new Error('config');
    const config = await configResponse.json();
    const base = `http://127.0.0.1:${config.port}`;
    const headers = {'X-Civit-Helper-Token': config.token, 'X-Civit-Helper-Origin': chrome.runtime.getURL('').replace(/\/$/, ''),
      'Content-Type': 'application/json'};
    stage = 'connect';
    for (let index = 0; index < 3000; index++) {
      const saved = await chrome.storage.session.get('pendingResult');
      if (saved.pendingResult) {
        const response = await fetch(base + '/result', {method: 'POST', headers,
          body: JSON.stringify(saved.pendingResult), signal: AbortSignal.timeout(5000)});
        if (!response.ok && response.status !== 409) throw new Error('result');
        await chrome.storage.session.remove('pendingResult');
      }
      const response = await fetch(base + '/poll', {headers, signal: AbortSignal.timeout(5000)});
      if (!response.ok) {
        const error = new Error(response.status === 403 ? '配對驗證被拒絕（HTTP 403）' : `本機工具回覆 HTTP ${response.status}`);
        error.code = response.status === 403 ? 'authentication_failed' : 'connection_failed';
        throw error;
      }
      const {command} = await response.json();
      if (!command) { await sleep(500); continue; }
      let result;
      try { result = {id: command.id, ok: true, result: await dispatch(command)}; }
      catch (error) { result = {id: command.id, ok: false, code: error.code || 'EXTENSION_ERROR',
        error: error.code ? error.message : '擴充功能操作失敗，請確認工具分頁及網站登入。'}; }
      await chrome.storage.session.set({pendingResult: result});
    }
  } catch (error) {
    // The local tool only listens while a job runs, so a refused fetch while idle is normal.
    const safeMessage = error instanceof TypeError ? '目前沒有執行中的工作（本機工具只在執行或診斷時連線，屬正常）。'
      : error.code ? error.message : stage === 'config' ? '無法讀取本機配對設定。' : '本機連線中斷或逾時。';
    await chrome.storage.local.set({connectionStatus: {state: error instanceof TypeError ? 'idle' : error.code || 'connection_failed', stage,
      message: safeMessage, checkedAt: new Date().toISOString(), version: chrome.runtime.getManifest().version}});
  }
  finally { polling = false; }
}

const installAlarm = () => chrome.alarms.create('civit-helper-poll', {periodInMinutes: 0.5});
chrome.runtime.onInstalled.addListener(() => { installAlarm(); poll(); });
chrome.runtime.onStartup.addListener(() => { installAlarm(); poll(); });
chrome.alarms.onAlarm.addListener(alarm => { if (alarm.name === 'civit-helper-poll') poll(); });
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id === chrome.runtime.id && message?.type === 'connect') { poll(); respond({ok: true}); }
});
installAlarm();
