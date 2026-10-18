# Civit Helper

Windows 小工具搭配日常 Chrome 擴充功能，每日台灣時間 **04:00** 執行 50 個愛心及追蹤 3 位新作者。使用日常 Chrome 的登入環境，另外開獨立、最小化的工具視窗，結束後關閉；不加入既有視窗的分頁列，不控制滑鼠鍵盤。

## 首次設定

1. 在平常使用的 Chrome 開啟 `chrome://extensions`，打開「開發人員模式」。
2. 按「載入未封裝項目」，選擇本專案的 **`extension`** 資料夾。
3. 在同一個 Chrome 使用者環境正常登入 https://civitai.red/images 。已有登入就不必重登。
4. 雙擊 **`launch.vbs`** 開啟中文 Windows 視窗，按「檢查網站」。
5. 檢查通過後按「立即執行」。手動執行不倒數。

若工具正在等待連線，可點 Chrome 的 Civit Helper 擴充功能圖示，再按「立即連接本機工具」。日常也會每 30 秒自動檢查是否有本機工作。更新 extension 程式檔案後，需在 `chrome://extensions` 卡片按「重新載入」才生效。

擴充功能只取得 Civitai 網站、指定本機連接埠及操作工具分頁所需權限，不申請所有網站、cookies 或 debugger 權限。它不讀取密碼、不自動操作 Google 登入、不修改安全設定。配對設定 `extension/local-config.json` 自動產生，只留本機、不存 Git、不傳網站。請勿分享這個檔案或 `runtime`。

## 排程與取消

排程名稱 **CivitHelper_Daily**，台灣時間每天 **04:00** 先顯示 **3 分鐘倒數視窗**。

- 按通知的「關閉／取消這次」或右上角 X：取消當次，進度保留。
- 沒有操作：180 秒後開始執行。
- 僅每天台灣時間 04:00 自動啟動一次；沒有每30分鐘重試、登入觸發或錯過後自動補跑。未完成可由你手動補跑。
- 手動「立即執行」直接開始，不倒數。
- 通知顯示失敗、倒數跨日或台灣時間未到04:00：不執行。

時間包含 `+08:00`，不依賴 Windows 時區。使用目前 Windows 帳號的登入工作階段，不保存 Windows 密碼、不要求管理員權限。關機、登出或休眠時無法執行，錯過04:00就等隔天，不主動喚醒電腦。日常 Chrome 必須已開啟並載入擴充功能；若未連線會明確記錄，需補跑請手動啟動。

安裝／更新排程：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_schedule.ps1
```

移除本工具排程（保留所有資料）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\remove_schedule.ps1
```

## 進度與故障恢復

- 隨機打散圖片候選。已按愛心、已追蹤、自己及工具曾追蹤的人會跳過，不取消任何既有操作。
- 愛心達50後不再額外按，繼續尋找尚未追蹤的作者直到3位。
- 必要時換排序及時間範圍，避免重複掃描同批作者；保持頁面原有內容瀏覽範圍。
- 每次工作最多20分鐘，部分完成即時保存。手動及排程補跑共用資料，只補不足數量。
- 操作前寫入意圖，收到對應成功回應並重新讀取狀態才計數。中斷後先核對，不盲目重按。
- 跨日待確認操作算回原日期；追蹤歷史永久保留。綁定帳號，換帳號會停止。
- 工具分頁被關閉、離開 Civitai、需要驗證、網路或連線失敗時停止並記錄，不把搜尋停滯當成「全站沒有可追蹤的人」。
- 工具視窗起始就最小化，結束時只關閉工具自己的視窗。若使用者在工具視窗增加其他分頁，只移除工具分頁，不關閉其他分頁；若標記或視窗歸屬不符，不強制關閉。
- 每日任務獎勵條件仍由網站決定；工具不自動領獎。

## 紀錄與入口

視窗提供「立即執行、登入／重新登入、檢查網站、查看 log、開啟擴充功能資料夾」。登入按鈕只在正常 Chrome 開啟 Civitai，使用者自行完成登入。

文字 log：`runtime/logs/civit.log`，每日輪替、保留30份。當日進度與待確認操作：`runtime/state.db`。最新只讀診斷：`runtime/diagnostic.json`。啟動層錯誤：`runtime/launcher.log`。

關閉 Windows 工具主視窗不會取消已開始的工作；要取消尚未開始的排程，請關閉獨立的3分鐘倒數通知。相同時間只能有一個工作。

## 維護

Python：`%USERPROFILE%\venvs\CivitHelper\Scripts\python.exe`。

```powershell
& "$env:USERPROFILE\venvs\CivitHelper\Scripts\python.exe" app.py status
& "$env:USERPROFILE\venvs\CivitHelper\Scripts\python.exe" app.py inspect
& "$env:USERPROFILE\venvs\CivitHelper\Scripts\python.exe" app.py run
& "$env:USERPROFILE\venvs\CivitHelper\Scripts\python.exe" -m unittest discover -s tests -v
```

舊專用 Chrome adapter 及登入函式暫留作測試參照，預設程式不再使用。`runtime/chrome-profile` 是舊測試資料，不是日常 Chrome。網站實際愛心、追蹤及任務計數，需載入擴充功能後登入實測；單元測試通過不等於網站任務已完成。

參照：[Chrome scripting](https://developer.chrome.com/docs/extensions/reference/api/scripting)、[alarms](https://developer.chrome.com/docs/extensions/reference/api/alarms)、[Civitai 官方原始碼](https://github.com/civitai/civitai)。
