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
- [ ] 建立測試：每日限額、部分續跑、pending 恢復、跨日、帳號綁定與 OS 鎖。
- [ ] 執行 unittest，確認缺少模組而失敗。
- [ ] 實作 SQLite 狀態和互斥鎖、日期與核心，網站透過介面注入。
- [ ] 執行 unittest，所有核心測試通過。
- [ ] 提交核心。

### Task 2: Chrome 與網站 adapter
**Files:** civit_helper/site.py, app.py, tests/test_site.py, requirements.txt
**Interfaces:** Site.account(), candidates(), state(kind,target), apply(kind,target); CLI run/login/inspect/status。
- [ ] 只讀檢查網站／官方原始碼，確認候選及操作狀態；登入仍需本人操作。
- [ ] 建立 fixture 測試：已追蹤／已按愛心不操作、驗證頁停止、缺少確認拒絕計數。
- [ ] 執行測試確認失敗，再實作 adapter 與 CLI。
- [ ] 測試通過，執行 inspect；若尚未登入明確報告，不當成實測成功。
- [ ] 提交 adapter。

### Task 3: Windows GUI 與排程
**Files:** civit_helper/gui.py, launch.vbs, install_schedule.ps1, remove_schedule.ps1, tests/test_schedule.py, README.md
**Interfaces:** GUI 呼叫同一 Python CLI；XML schedule 04:00+08:00 並每 30 分鐘重複。
- [ ] 建立排程 XML／啟動參數的測試，先確認失敗。
- [ ] 實作中文 GUI、隱藏啟動、安裝移除排程及 README。
- [ ] 跑完整 unittest、GUI 啟動及只讀網站檢查。
- [ ] 註冊排程並讀回確認；以 status 驗證持久化結果。
- [ ] 提交並請獨立 reviewer 審查，修正重要問題並重新測試。

## Execution Ledger
Pre-flight: Task 1 → Task 2 以 Store/execute/site 介面共用；Task 2 → Task 3 以 CLI 共用，介面名稱一致。
Ruling: 這是新建空白專案，直接在使用者指定資料夾初始化 Git，不另建 worktree，避免交付兩份入口。代價：此目錄為實作工作目錄。
Ruling: 使用者已明確要求審閱後開始，省略再次請求計畫批准，審閱確認沒有必須向使用者確認的事項。
