# run24 圖片清單格式失敗修正

## 證據
11:34 manual/run 已連線，但image.getInfinite回傳值是str，不是預期items物件，因此未操作任何目標（0/50、0/3）。只讀重現Newest、Most Reactions、Most Comments三來源均為str；短前綴為devalue表格格式，JSON解析為list。

Civitai官方trpc-union-transformer.ts明確以字串判定devalue、以物件判定superjson，並按伺服器池混用。原工具只解superjson，屬本工具兼容性缺口。

## 修正
0.2.2使用npm標準devalue 6.0.3 parser，同時處理read回應及操作acknowledgment。read回應正規化為既有Python橋接協定；原有自己分頁標記、來源／token驗證、請求發出前目標防護及成功後重讀狀態均保留。

esbuild將decoder與所有依賴包在runPageCommand函式本體內，以支援chrome.scripting序列化，不從MAIN world依賴模組閉包。附上MIT授權。使用者不需npm，權限不變。

## 驗證
- devalue feed fixture RED→GREEN：圖片ID、作者ID及游標正確還原。
- heart／follow devalue狀態與ackfixture：本機模擬各一個正確請求，確認accepted、fetch還原；無真實網站操作。
- 原錯誤目標請求阻擋測試仍通過。
- 完整41項測試通過；獨立review未發現Important／Critical問題。
- 尚待使用者重新載入0.2.2後，以最小化工具視窗只讀驗證實際三來源及狀態。未宣稱每日任務已完成。
