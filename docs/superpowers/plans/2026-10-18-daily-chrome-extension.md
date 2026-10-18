# Daily Chrome Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 改以日常 Chrome 擴充功能執行，排程先倒數180秒，手動不倒數。
**Architecture:** 保留 SQLite／execute／OS lock，替換 ChromeSite 為 BridgeSite。只在工作期間建立127.0.0.1:43187短期HTTP bridge，帶32-byte token；MV3擴充功能只操作自己建立的Civitai分頁。
**Tech Stack:** Python HTTPServer / Chrome MV3 / JavaScript / Tkinter。
**Spec:** ../specs/2026-10-18-civit-helper-design.md

## Global Constraints
- 既有50愛心、3追蹤與pending恢復規則不變。
- 排程前180秒警告，關閉取消當次；手動不警告；倒數跨日不執行。
- 不接管日常其他分頁、不讀cookie、不開remote-debugging、不繞過驗證。
- localhost token僅本機，不存Git，不傳Civitai；bridge拒絕其他Host／Origin／錯誤token。
- 擴充功能需本人手動載入一次。

## Review Focus
- 擴充功能未安裝：有界等待並顯示設定指引，不誤判完成。
- 回應逾時後晚到：不可交給下一個命令，保留pending。
- 瀏覽器重啟／tab ID重用：只重用已驗證工具標記的分頁。
- 點擊前跨日：JS在導航等待後及點擊前驗日期與deadline。
- 關閉通知：不能開瀏覽器或送出任務；手動不警告。

### Task 1: Countdown and secure bridge
**Files:** notice.py, bridge.py, tests/test_notice.py, tests/test_bridge.py
**Interfaces:** Bridge.command(op,**data)->dict; Bridge context manager; confirm_scheduled_run()->bool。
- [ ] 寫測試並跑出失敗：180秒／關閉／手動略過；token、Origin、Host、命令結果關聯。
- [ ] 實作倒數及loopback bridge；配對設定extension/local-config.json自動生成。
- [ ] 跑測試確認通過，提交。

### Task 2: MV3 worker and BridgeSite
**Files:** extension/manifest.json, worker.js, popup.html/js, civit_helper/remote_site.py, tests/test_extension.py
**Interfaces:** worker ops init/read/navigate/action/probeHeart/probeFollow；BridgeSite符合既有Site介面。
- [ ] 寫fixture測試：權限限縮、只用自己分頁、讀取回應格式、點擊逾時／跨日拒絕。
- [ ] 實作MV3輪詢、自己分頁的標記和操作；保留現行頁面內容範圍，狀態以讀取API確認。
- [ ] 執行JS syntax、瀏覽器fixture及Python測試；提交。

### Task 3: Desktop integration and handoff
**Files:** app.py, gui.py, login.py, README.md
**Interfaces:** 既有CLI切換至BridgeSite；GUI加開啟擴充功能設定資料夾、登入為日常Chrome正常tab。
- [ ] 整合倒數與擴充功能，更新GUI及文件；不修改既有日常Chrome設定。
- [ ] 跑完整測試及GUI smoke；確認排程仍指向同一CLI並包含3分鐘時間預算。
- [ ] 獨立審閱、修正重要問題；請用戶一次載入擴充功能，再驗證登入後讀取和實際任務。

## Ledger
2026-10-18 timing correction (supersedes earlier retry rulings): 用戶明確要求僅早上04:00，移除30分鐘重複、LogonTrigger、StartWhenAvailable。安裝起點取下一個04:00；CLI阻擋白天自動啟動。關閉提醒／失敗當日不自動重試，只能手動補跑。14項相關測試通過，Windows讀回下次2026-10-19 04:00+08:00。
Ruling: 使用者選擇日常Chrome擴充功能，這是明確需求變更，取代原專用profile主要路徑；舊adapter暫留做已有fixture測試，不再由預設CLI呼叫。
Ruling: 關閉通知取消「當次」排程，30分鐘後未完成補跑會再次通知。代價：仍在工作時可能再看到提醒。
Spec review: 無須再問用戶的重要歧義；token 不送入MAIN世界、命令以ID關聯且不重送。
Task 1: countdown RED→GREEN（3 tests）；bridge authentication/result correlation RED→GREEN。
Task 2: permissions/origin browser fixture RED→GREEN；Python BridgeSite 和MV3整合完成，待用戶重新載入後live。
Task 3: CLI/GUI切換完成，登入只開日常Chrome；已安裝的Windows排程仍指向相同CLI。
Final review: 新的獨立reviewer發現遠端讀取後跨日及錯誤按鈕target binding缺口。
Final: fixed remote window — 原始day與write deadline由core保存，所有準備後再檢查；2 tests RED→GREEN。
Final: fixed target binding — MAIN fetch guard在發送前驗證唯一mutation方法、圖片／作者ID；錯誤推薦按鈕fixture RED→GREEN，禁止錯誤請求送出。
Ruling: 使用者要求新視窗而非新增既有分頁；改為最小化獨立視窗，結束時只關閉歸屬已驗證的工具視窗／分頁。代價：無法連線清理時可能留下最小化視窗，會記log，絕不強關其他視窗。
Window ownership/cleanup Node fixture RED→GREEN，含使用者新增分頁保護。
Ruling: Chrome extension 的GET可能省略Origin，使用token認證的X-Civit-Helper-Origin作fallback；若瀏覽器Origin同時存在則須一致，不放寬網站Origin。配對測試RED→GREEN。
Verification: 已唯讀確認Default Chrome已載入本專案extension，無disable_reasons，權限符合manifest；第一次連線未完成配對，待使用者重新載入最新版。
Outstanding: 日常Chrome連線、登入後讀取、實際50/3及任務獎勵計數仍待live驗證。Chrome完全關閉時自動啟動路徑尚未交付，README暫明列需Chrome開啟。
