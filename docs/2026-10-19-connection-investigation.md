# 2026-10-19 04:00 連線失敗調查

- 排程04:00啟動，03分鐘倒數後等候110秒初始化，另外10秒關閉命令同樣無回應，04:05結束；愛心0、追蹤0。
- Windows目前Chrome主程序建立時間2026-10-16，不能歸因於Chrome當時未開。
- 用戶圖片確認Default Chrome中Civit Helper 0.2.0已啟用，無卡片錯誤；runtime/extension-pair.json仍不存在。
- 原版worker捕捉全部fetch例外後不留下原因，故目前證據不足以判定網路、權限或背景程式哪一層失敗。不可將單元測試通過宣稱為連線已修復。
- 新版0.2.1：增加無網站操作的doctor/ping、驗證用health端點、本機請求／認證／拒絕原因統計，以及擴充功能popup的階段與結果。維持token、Origin、Host驗證，不擴張權限，不改04:00排程。
- 回歸先RED再GREEN：worker網路錯誤與HTTP403可見且無機密、health不交付工作、配對拒絕與無連線區分。完整39項測試通過。
- 尚待：用戶重新載入0.2.1並按popup診斷後，依具體結果定位和修復原始連線失敗。

## 實際請求證據（07:02）

- 新增僅來源格式的log，不包含token或cookie。實際輸出：browser=''、declared=''，拒絕原因invalid_origin。
- 這證明localhost可達、worker有定時輪詢；失敗點是目前執行中的舊程式沒有送來源標記，而Chrome對此GET也省略Origin。
- 用戶截圖顯示0.2.0。0.2.1的worker會送X-Civit-Helper-Origin，因此需要在Chrome重新載入才套用；沒有放寬token、來源或Host驗證。
- 尚未收到0.2.1的有效ping回應，不能宣稱已通過實際連線。需完成此步後再安排網站只讀檢查，不能把診斷成功等同每日任務完成。
