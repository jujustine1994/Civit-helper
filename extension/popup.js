const status = document.getElementById('status');
const details = document.getElementById('details');
const version = chrome.runtime.getManifest().version;
document.getElementById('version').textContent = `已載入版本 ${version}`;

async function probe() {
  const report = {version, checkedAt: new Date().toISOString(), websiteActions: false};
  status.textContent = '正在測試本機連線…';
  let stage = 'config';
  try {
    const response = await fetch(chrome.runtime.getURL('local-config.json'), {cache: 'no-store'});
    if (!response.ok) throw new Error('無法讀取本機配對設定。');
    const config = await response.json();
    stage = 'connect';
    const health = await fetch(`http://127.0.0.1:${config.port}/health`, {
      headers: {'X-Civit-Helper-Token': config.token,
        'X-Civit-Helper-Origin': chrome.runtime.getURL('').replace(/\/$/, '')},
      signal: AbortSignal.timeout(5000)});
    report.httpStatus = health.status;
    if (!health.ok) throw new Error(health.status === 403 ? '本機配對驗證被拒絕，請把這段診斷文字交給維護者。' : `本機工具回覆 HTTP ${health.status}。`);
    stage = 'worker';
    await chrome.runtime.sendMessage({type: 'connect'});
    report.state = 'connected';
    report.message = '本機連線及擴充功能背景程式正常，請回Windows工具查看診斷結果。';
  } catch (error) {
    report.state = 'error';
    report.stage = stage;
    report.message = error instanceof TypeError ? 'Failed to fetch：本機工具未開啟診斷服務，或本機連線被瀏覽器／網路設定攔截。'
      : stage === 'worker' ? '本機連線正常，但擴充功能背景程式沒有回應；請查看卡片的Service Worker錯誤。' : error.message;
  }
  const stored = await chrome.storage.local.get('connectionStatus');
  report.background = stored.connectionStatus || null;
  status.textContent = report.message;
  details.value = JSON.stringify(report, null, 2);
}
document.getElementById('connect').addEventListener('click', probe);
probe();
