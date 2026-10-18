# Civit Helper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Windows Chrome 背景每日 50 個愛心、3 位新追蹤，提供手動補跑與 log。
**Architecture:** SQLite journal + 單程序鎖；網站 adapter 和執行協調分開。GUI 和排程共用 CLI。
**Tech Stack:** Python 3.13 / Playwright / SQLite / Tkinter / Windows Task Scheduler。
**Spec:** ../specs/2026-10-18-civit-helper-design.md

## Global Constraints
- 台灣時間 04:00，每 30 分鐘補跑；04:00 前僅允許手動啟動。
- 專用 Chrome profile，不碰日常瀏覽器；不繞過驗證。
- 每日 50 個愛心、3 位新追蹤；部分完成保留，永不取消。
- 每次 20 分鐘，日誌 30 天，追蹤歷史永久保留。

## Review Focus
- 程序在點擊後中斷：意圖重讀狀態，不盲目 toggle。
- 跨日或改帳號：原日期恢復確認，帳號不一致停止。
- 重複分頁／同作者：永久追蹤歷史與本次候選去重。
- 登入或安全驗證：不操作並明確顯示。
- 排程與手動競爭：OS file lock 互斥，錯過排程可補跑。

### Task 1: Journal 與執行核心
**Files:** civit_helper/state.py, core.py, tests/test_core.py
**Interfaces:** Store(path), progress(day), prepare(day,kind,target), confirm(day,kind,target); execute(store,site,source,now,deadline).
- [x] 建立測試：每日限額、部分續跑、pending 恢復、跨日、帳號綁定與 OS 鎖。
- [x] 執行 unittest，確認缺少模組而失敗。
- [x] 實作 SQLite 狀態和互斥鎖、日期與核心，網站透過介面注入。
- [x] 執行 unittest，所有核心測試通過。
- [x] 提交核心。

### Task 2: Chrome 與網站 adapter
**Files:** civit_helper/site.py, app.py, tests/test_site.py, requirements.txt
**Interfaces:** Site.account(), candidates(), state(kind,target), apply(kind,target); CLI run/login/inspect/status。
- [x] 只讀檢查網站／官方原始碼，確認候選及操作狀態；登入仍需本人操作。
- [x] 建立測試：已追蹤／已按愛心不操作、缺少確認拒絕計數；Chrome fixture 覆蓋延遲入口。
- [x] 執行測試確認失敗，再實作 adapter 與 CLI。
- [x] 測試通過，執行 inspect；未登入時正確報告，不當成實測成功。
- [x] 提交 adapter。

### Task 3: Windows GUI 與排程
**Files:** civit_helper/gui.py, launch.vbs, install_schedule.ps1, remove_schedule.ps1, tests/test_schedule.py, README.md
**Interfaces:** GUI 呼叫同一 Python CLI；XML schedule 04:00+08:00 並每 30 分鐘重複。
- [x] 建立排程 XML／啟動參數的測試，先確認失敗。
- [x] 實作中文 GUI、隱藏啟動、安裝移除排程及 README。
- [x] 跑完整 unittest、GUI 啟動及只讀網站檢查。
- [x] 註冊排程並讀回確認；以 status 驗證持久化結果。
- [x] 提交並請獨立 reviewer 審查，修正重要問題並重新測試。

## Execution Ledger
Pre-flight: Task 1 → Task 2 以 Store/execute/site 介面共用；Task 2 → Task 3 以 CLI 共用，介面名稱一致。
Ruling: 這是新建空白專案，直接在使用者指定資料夾初始化 Git，不另建 worktree，避免交付兩份入口。代價：此目錄為實作工作目錄。
Ruling: 使用者已明確要求審閱後開始，省略再次請求計畫批准，審閱確認沒有必須向使用者確認的事項。
Task 1: complete，10 tests passed；b63b097。
Task 2/3: complete（本機與只讀驗證），16 tests passed；61d5789；GUI_SMOKE_OK。
Ruling: 測試暫存目錄與 Git 索引受到執行沙箱限制，使用受審核的本機執行驗證，不改動測試資料持久化語義。代價：測試需要此環境允許存取 Windows 暫存目錄。
Ruling: Windows 拒絕未限定使用者的 LogonTrigger；改為 trigger 與 principal 均限定目前 SID，非管理員註冊成功。不提高排程執行權限。代價：僅此使用者登入時補跑，符合需求。
Final review: independent reviewer found delayed reaction entry, midnight write window, and misleading diagnostic readiness。
Final: fixed 延遲反應入口 — 真實 Chrome 延遲掛載 fixture RED→GREEN。
Final: fixed 導航期間跨日 — test_midnight_during_navigation_prevents_click RED→GREEN。
Final: fixed 不合法追蹤名單仍顯示就緒 — strict follow_state/inspect tests RED→GREEN；suite 21/21。
Ruling: 使用者回報 Google 拒絕自動化登入環境。首次登入改以無自動化控制的正常 Chrome 啟動，使用者關閉專用視窗後才接回背景檢查；不修改偵測旗標、不降低帳號安全設定。代價：登入完成後需手動關閉專用視窗。
Login regression tests RED→GREEN；suite 23/23。
Outstanding: 使用者正在首次登入；實際愛心、追蹤及網站任務計數待登入完成後驗證。
