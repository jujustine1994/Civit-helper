# Civit Helper

Windows 個人每日任務工具。使用已安裝 Chrome，每日台灣時間 **04:00** 在背景替 50 張圖片按 ❤️，並追蹤 3 位尚未追蹤的作者；未完成每 30 分鐘補跑。

## 開啟與首次使用

1. 雙擊本資料夾的 **`launch.vbs`**，開啟中文工具視窗，不顯示命令列。
2. 按 **登入／重新登入**，在新開的正常 Chrome 專用視窗親自登入 Civitai。**成功後請關閉這個專用 Chrome 視窗**，工具才會檢查並確認登入。登入期間不由自動化控制瀏覽器；工具不索取或讀取密碼。
3. 按 **檢查網站**，只讀檢查登入、圖片來源及愛心狀態。
4. 按 **立即執行**。成功操作立即保存；之後手動補跑只補不足數量。

Chrome 專用資料位於 `runtime/chrome-profile`，不會接管或關閉平常的 Chrome。專用視窗首次出現 Chrome 初始設定時，請自行完成必要提示。登入憑證保存在專用 profile，請勿分享 `runtime` 資料夾。

## 排程

安裝：PowerShell 執行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\install_schedule.ps1`。

移除：執行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\remove_schedule.ps1`。只移除本工具排程，不刪資料。

排程名稱 **CivitHelper_Daily**，起始時間包含 `+08:00`，不依賴 Windows 時區。使用目前 Windows 帳號的已登入工作階段，不保存 Windows 密碼、不要求系統管理員權限。鎖定畫面時可執行；登出、關機或休眠時無法工作。登入後延遲 2 分鐘檢查並補跑，亦設定錯過時間後補跑；不主動喚醒電腦。自動工作在台灣時間 04:00 前直接退出，手動執行不受限制。

背景使用 headless Chrome 和 pythonw，不搶視窗或滑鼠鍵盤，但仍會使用 CPU、記憶體和網路。關閉工具視窗不會取消已啟動的背景工作。登入、檢查與工作共用 OS 互斥鎖，同時啟動時後者會退出。

## 行為與恢復

- 隨機打散候選；跳過既有愛心和追蹤，不取消任何操作。
- 愛心達 50 後只繼續找作者；追蹤不足會換排序和時間範圍，不把搜尋停滯當成「全站沒人可追蹤」。尊重頁面原本的圖片內容範圍。
- 當次最多 20 分鐘；不足保留進度，下次續跑。愛心和追蹤分開記錄。
- 操作前先寫入意圖，操作後核對網站狀態；中斷時下次先確認結果，避免盲目重按。
- 台灣日期每天重置目標；過去追蹤歷史永久保留。跨日待確認操作算回原始日期。
- 綁定第一次登入確認的帳號，換帳號會停止。若需改綁帳號，先備份資料再由維護者處理，避免混算。
- 登入失效、安全驗證、網路失敗或頁面變更會明確記錄；工具不自動解驗證，也不保證網站任務獎勵發放，不自動領獎。

## 紀錄

視窗按 **查看 log 紀錄**。文字 log 在 `runtime/logs/civit.log`，每日輪替；保留 30 個每日檔。資料庫 `runtime/state.db` 儲存每日進度、待確認操作和執行結果。最近只讀診斷為 `runtime/diagnostic.json`；啟動層錯誤在 `runtime/launcher.log`。

「尚未登入」代表需要完成首次設定；「部分完成／搜尋停滯」可直接補跑；「結果待確認」請先跑網站檢查再補跑，不要手動重複按同一目標。

## 命令列與環境

Python 位於 `%USERPROFILE%\venvs\CivitHelper\Scripts\python.exe`。在專案目錄執行：

```powershell
& "$env:USERPROFILE\venvs\CivitHelper\Scripts\python.exe" app.py status
& "$env:USERPROFILE\venvs\CivitHelper\Scripts\python.exe" app.py inspect
& "$env:USERPROFILE\venvs\CivitHelper\Scripts\python.exe" app.py login
& "$env:USERPROFILE\venvs\CivitHelper\Scripts\python.exe" app.py run
& "$env:USERPROFILE\venvs\CivitHelper\Scripts\python.exe" -m unittest discover -s tests -v
```

重建環境：`uv venv "$env:USERPROFILE\venvs\CivitHelper" --python 3.13`，再執行 `uv pip install --python "$env:USERPROFILE\venvs\CivitHelper\Scripts\python.exe" -r requirements.txt`。不需要額外下載 Chromium，使用系統 Chrome。

## 驗證狀態

已確認背景 Chrome 可以載入圖片頁、讀取圖片與作者候選、辨識表情入口。**尚需使用者首次登入，才能驗證實際愛心與追蹤以及任務計數。**單元測試不等於網站實測成功。

實作參照：[Civitai 官方原始碼](https://github.com/civitai/civitai)、[Playwright Chrome 支援](https://playwright.dev/python/docs/browsers)、[Windows 排程重複間隔](https://learn.microsoft.com/en-us/windows/win32/taskschd/repetitionpattern-interval)。
