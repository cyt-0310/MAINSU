# 任務三：MVP 與第一段整合

程式位於 github-share/。

## MVP 範圍

先交付可追溯的 PDF 結構資料、學生資料到題庫的明確交接介面，及一輪文字問答／缺口追問。保留自我介紹和 1～2 個備審事件，不加語音、面部偵測、常見題或綜合等第評分。

| 輸出 | 介面／檔案 | 目前狀態 |
|---|---|---|
| Output 1：PDF → Structured Data | parse → .md、.docling.json、.events.json；含 reading_units、events、頁碼／座標與父子關係 | 原倉庫已有解析器。本次驗證四份既有 events.json 可銜接下游，沒有重新跑 OCR。 |
| Output 2：Student Profile → Question Plan | prepare 新增 student.profile.json 與 question.plan.json；plan 指令可獨立讀取 profile＋索引重新規劃 | 本次已新增交接檔案、來源一致性檢查及測試。topics.json 保留供現有面試入口使用。 |
| Output 3：Dynamic Follow-up | interview：主問題 → 文字回答 → 累積相關度／完整度／一致性 → 缺口 → 單題追問 → 再回答 | 原流程已有串接；本次以假模型驗證一輪追問可走到結尾摘要，未用真實 API 重跑整場。 |

Student Profile v1 包含 target_department、source_documents、events、skill_tree，以及未確認狀態。student_name 為 null，不從檔名猜姓名。事件中六類資訊為動機、角色、行動、成果、反思及能力，每項保留引用、單元與頁碼；技能及模型推論仍需核對。

Question Plan v1 包含 target_department、source_documents、questions 與限制。題目以 profile 的事件類別、角色／其他面向及 RAG 證據規劃；不會把 profile 外的事件 ID 當作合法題目。重新規劃時會核對 profile 的事件、來源檔及原文片段是否與索引一致，避免把不同學生的資料接在一起。

## 原程式已有什麼分析？

- 經驗內容：STAR 五個細項平均，轉為百分比。
- 個人特質：ASK 三個細項平均，轉為百分比。
- 深度邏輯：Gibbs 兩個細項平均，轉為百分比。
- 同主題跨輪每項取最高分；三項各達 55% 才算完整度達標。
- 未達標面向按低分優先；同分為個人特質→深度邏輯→經驗內容。
- 相關度採同主題累積回答；低於 0.4 最多重述一次，之後仍低於 0.4 就換題。
- 一致性檢查保留備審與回答的差異引文、來源頁碼／輪次及 source_verified。這是待核對差異，不等於確認學生說謊。

原程式把這些存進 log，結束時只印結束原因。本次新增 results_summary.py，正常面試結束自動顯示逐主題摘要，且 session JSON 內新增 summary 欄位。摘要包含三項完整度、55% 達標狀態、優先缺口、最後一次累積相關度、追問／重述次數、作答時間／超時、差異引文與結束原因。沒有成功分析的主題顯示「未評估」，不以零分替代，不計算未定義的整體評分。

## 從新下載版本開始

先在倉庫根目錄開 PowerShell，進入實際專案資料夾：

```powershell
cd github-share
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r integration_review\integrated\requirements-ai.txt -r docling_pdf\requirements.txt
New-Item -ItemType Directory -Force -Path data, outputs | Out-Null
```

依 README 在目前視窗設定自己的 Gemini 金鑰、LLM_PROVIDER=gemini、GEMINI_TRANSPORT=rest 及帳號可用的 GEMINI_MODEL；現行預設模型為 gemini-3.5-flash-lite。API 額度依帳號而定。本次沒有代讀或使用你的金鑰。

### Output 1

將自己的 PDF 放入 data/portfolio.pdf：

```powershell
.\.venv\Scripts\python.exe integration_review\integrated\run_text_interview.py parse data\portfolio.pdf --output outputs\parsed-01
```

輸出 outputs/parsed-01/portfolio.events.json 是第一段交接資料。

### Output 2

```powershell
.\.venv\Scripts\python.exe integration_review\integrated\run_text_interview.py prepare outputs\parsed-01\portfolio.events.json --output outputs\prepared-01
```

成功後可查看：

- outputs/prepared-01/events.structured.json：候選事件及提取面向。
- outputs/prepared-01/student.profile.json：學生資料交接介面。
- outputs/prepared-01/question.plan.json：題庫規劃交接介面。
- outputs/prepared-01/topics.json：現有面試主程式相容輸入。
- outputs/prepared-01/evidence.index.json：檢索證據與向量。

要示範「讀已存的 Student Profile 再產出 Question Plan」，不必重做 PDF 或事件提取：

```powershell
.\.venv\Scripts\python.exe integration_review\integrated\run_text_interview.py plan outputs\prepared-01\student.profile.json --index outputs\prepared-01\evidence.index.json --output outputs\replanned-01
```

這仍會呼叫 LLM 產生題目。事件、原文或索引若變更，應先重建一致的 profile／索引，不能把不同人的輸出混接。

### Output 3 與最後顯示結果

```powershell
.\.venv\Scripts\python.exe integration_review\integrated\run_text_interview.py interview outputs\prepared-01 --output outputs\session-01.json
```

文字輸入後按 Enter 送出。若完整度已全部達標、重述仍離題、主題或全場上限已到，就依規則換題／結束，不強制為展示而產生不必要追問。結束時會自動顯示結果摘要。

單獨顯示已保存的面試紀錄，不必設定 API 金鑰、不呼叫 AI：

```powershell
.\.venv\Scripts\python.exe integration_review\integrated\run_text_interview.py summary outputs\session-01.json --output outputs\session-01.summary.md
```

舊版只有 log、沒有 summary 欄位的 session 也可直接使用。摘要依既有成功評估重建，不會重新評分；中斷紀錄明確顯示尚未完成。輸出檔案／資料夾存在時請用新名稱。

## 驗證與限制

自動測試共 50 項；本次下載版本通過 48 項，跳過兩個需要私人 PDF 結果的測試。另外四份本機既有解析輸出分別有 13、11、29、13 個可追溯事件，已驗證可被新版本讀取，未重新執行解析。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s integration_review\integrated -p "test_*.py"
```

模型／向量測試使用假回應，不會呼叫付費 API。此次檢查的本機 gemini-session-01.json 是未完成紀錄，只有一個主題有分析；已在本倉庫 github-share/outputs/existing-session.summary.md 產生其私人摘要。該檔與新 profile／plan／問答都由新增 .gitignore 排除，不應發布。
