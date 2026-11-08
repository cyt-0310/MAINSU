# 備審文字面試：流程 2～12

Python 3.12 專案。以備審候選事件建立個人化題庫，透過 Gemini 評分、檢索原文證據及動態追問。只使用文字回答，不含語音、面部偵測、科系常見問題或第十三步報告。

本次 MVP 整合新增 student.profile.json → question.plan.json 的明確介面，以及正常面試結束自動顯示逐主題完整度摘要。可用 `run_text_interview.py summary <session.json>` 離線查看舊紀錄。完整操作與驗證狀態請看 [MVP.md](../MVP.md)。摘要不是綜合等第評分報告。

## 功能與狀態

- Docling／EasyOCR PDF 解析、異常編碼局部補救、閱讀順序整理及候選事件切分。
- 事件父子層級、來源頁碼／座標、向量檢索、候選技能樹。
- 自介＋1～2 個備審事件；完整度門檻 55%，相關度低於 0.4 最多重述一次，仍離題就換題。
- 輸入文字後按 **Enter 立即結束本題回答並送出**，不必等待時間到。空白 Enter 會提醒補上文字；到時會提交目前已輸入文字。Ctrl+C 中斷面試。
- 一般單題 120 秒、自介 90 秒、主題 4 分鐘、全場 20 分鐘／15 題上限。模型等待時間計入面試時間。

使用者已在本機確認 Gemini REST 的 gemini-3.5-flash-lite 連線及 prepare 成功。自動測試以假模型回應檢查流程，並不代表評分準確率或所有終端中文輸入法已驗收。

## 1. 安裝

下載或 clone 本倉庫後，在專案根目錄開啟 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r integration_review\integrated\requirements-ai.txt
```

若需要從 PDF 開始，另安裝：

```powershell
.\.venv\Scripts\python.exe -m pip install -r docling_pdf\requirements.txt
```

模型首次使用需要連網下載。API 免費額度及可用模型依各自帳號為準；不要假設所有請求都免費。

## 2. 每位成員設定自己的 Gemini 金鑰

到 [Google AI Studio](https://aistudio.google.com/apikey) 建立自己的金鑰。先執行第一行，看到提示才貼金鑰並按 Enter；接著執行其餘三行。金鑰只在目前視窗使用，不會寫入程式。

```powershell
$geminiKey = Read-Host "貼上自己的 Gemini 金鑰" -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', $geminiKey).Password
$env:LLM_PROVIDER = "gemini"
$env:GEMINI_TRANSPORT = "rest"
$env:GEMINI_MODEL = "gemini-3.5-flash-lite"
```

執行一個短連線測試：

```powershell
.\.venv\Scripts\python.exe integration_review\integrated\run_text_interview.py check --timeout 60
```

API 模式會把備審與問答傳給服務。測試請使用可提供給 Gemini 處理的備審副本。免費方案的資料使用條款請查看 [Google 官方價格說明](https://ai.google.dev/gemini-api/docs/pricing)。

## 3. 使用自己的 PDF 跑題庫與面試

先把備審副本放入 `data/portfolio.pdf`。這個資料夾與 `outputs/` 都排除於 Git 追蹤之外。

```powershell
.\.venv\Scripts\python.exe integration_review\integrated\run_text_interview.py parse data\portfolio.pdf --output outputs\parsed-01
.\.venv\Scripts\python.exe integration_review\integrated\run_text_interview.py prepare outputs\parsed-01\portfolio.events.json --output outputs\prepared-01
.\.venv\Scripts\python.exe integration_review\integrated\run_text_interview.py interview outputs\prepared-01 --output outputs\session-01.json
```

題庫在 `outputs/prepared-01/topics.json`。面試時輸入完成即可按 Enter，畫面會顯示「回答已送出，正在分析」。下一次請換新輸出名稱。

多份備審可依序列出多個 .events.json，但必須屬於同一學生。

## 4. 執行測試

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s integration_review\integrated -p "test_*.py"
```

自動測試不需要真實金鑰，也不會發出付費 API 請求。缺少本機測試資料時，相關測試會跳過。

## 團隊協作

1. 每次開始工作先 Fetch／Pull，取得同學最新修改。
2. 建立自己的分支，例如 feature/question-bank，只改自己負責的功能。
3. 測試後 Commit，Push，再開 Pull Request 給同學檢查。
4. 合併後其他成員再 Pull。不要互傳整包 .venv 或 API 金鑰。

.gitignore 已排除常見私人輸出；若另用自訂名稱存檔，仍請先檢查 GitHub Desktop 的 Changes。尤其不能提交金鑰、真實備審、事件證據或問答；Private 倉庫也一樣。專案設定的模型名稱可以共用，每人實際金鑰必須自己設定。

## 檔案分工

| 路徑 | 工作 |
|---|---|
| docling_pdf/parse_pdf.py | PDF 解析與候選事件 |
| integration_review/integrated/evidence.py | 事件來源與 RAG 索引 |
| integration_review/integrated/ai_services.py | 技能整理、題庫與回答檢核 |
| integration_review/integrated/interview_session.py | 面試狀態、重述與追問規則 |
| integration_review/integrated/run_text_interview.py | 文字輸入、Enter 提交與主入口 |
| integration_review/integrated/interview_gap_detection/ | 缺口規則、提示、模型串接與設定 |

這是本機 Python 程式；GitHub 用來共用程式碼，不會自動變成線上面試網站。
