document.getElementById('connect').addEventListener('click', async () => {
  await chrome.runtime.sendMessage({type: 'connect'});
  document.getElementById('status').textContent = '已喚醒擴充功能，請回到 Windows 工具查看結果。';
});
