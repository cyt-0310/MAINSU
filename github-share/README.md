# 備審文字面試：流程 2～12

Python 3.12 專案。以備審候選事件建立個人化題庫，透過 Gemini 評分、檢索原文證據及動態追問。只使用文字回答，不含語音、面部偵測、科系常見問題或第十三步報告。

本次 MVP 整合新增 student.profile.json → question.plan.json 的明確介面，以及正常面試結束自動顯示逐主題完整度摘要。可用 `run_text_interview.py summary <session.json>` 離線查看舊紀錄。完整操作與驗證狀態請看 [MVP.md](../MVP.md)。摘要不是綜合等第評分報告。

## 功能與狀態

- Docling／EasyOCR PDF 解析、異常編碼局部補救、閱讀順序整理及候選事件切分。
- 事件父子層級、來源頁碼／座標、向量檢索、候選技能樹。
- 自介＋1～2 個備審事件；完整度門檻 55%，相關度低於 0.4 最多重述一次，仍離題就換題。
- 輸入文字後按 **Enter 立即結束本題回答並送出**，不必等待時間到。空白 Enter 會提醒補上文字；到時會提交目前已輸入文字。Ctrl+C 中斷面試。
- 一般單題 120 秒、自介 90 秒、主題 4 分鐘、全場 20 分鐘／15 題上限。模型等待時間計入面試時間。
- 新增追問前，主題及全場都須至少剩餘 60 秒；生成後再次檢查。主題不足則換題，全場不足則結束，不增加未實際提出的追問計數。離題重述仍依原有規則執行。門檻可在 `interview_gap_detection/config/settings.json` 的 `followup.min_remaining_seconds` 調整（路徑位於 `integration_review/integrated/` 下）。此設定為語音使用情境預留回答時間，目前介面仍為文字回答。

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

題庫在 `outputs/prepared-01/topics.json`。回答會先保存再分析。重新練習請換新輸出名稱；接續原面試則使用下方的 `--resume`。

### 服務忙碌與中斷續答

相關度計算前，先以本機規則排除空白、純符號、單獨的「測試回答範例：」「以下是我的回答：」「待補」等佔位文字。這些嘗試保留於紀錄，但不進入語意相關度、完整度評估或模型對話內容；畫面提醒未實質作答後重問原題，不增加題數，與離題共用每主題一次重述機會。再次未實質作答就換題，並遵守既有時間／題數上限。短回答、「不知道」或真正的離題敘述仍交由既有流程判斷，不以字數判定內容不足。

Gemini HTTP 500、502、503 或 504 會額外自動重試最多 3 次，等待約 2、4、8 秒並加少量隨機延遲。400／403／429 不自動重試；不會自動改用其他模型或服務。正常分析時間仍計入面試，但失敗請求、自動重試等待與失敗後等待使用者選擇的時間不計入。

按 Enter 送出的回答會先存入 session JSON，再開始分析。重試仍失敗時，按 Enter 可重新分析同一份回答；輸入 `q` 可保存離開。失敗回合不採用部分評分、不增加追問題數。尚未送出的輸入不保證能在中斷後恢復。

在新的終端機設定好 API 金鑰後，用原本的題庫資料夾與 session 檔案繼續：

```powershell
.\.venv\Scripts\python.exe integration_review\integrated\run_text_interview.py interview outputs\prepared-01 --output outputs\session-01.json --resume
```

離線期間不計入面試時間；程式會核對題庫與備審索引。只有新版包含 `runtime` 恢復狀態的紀錄支援續答，舊版紀錄仍可查看摘要。

PDF 解析完成會同時輸出 `portfolio.md`、`portfolio.events.json` 與 `portfolio.docling.json`。閱讀 `outputs/parsed-01/portfolio.md` 即可核對結果：最上方是事件切分總表及各事件完整內容（含來源頁碼、所屬課程與子事件），後面是逐頁解析原文。在 VS Code 開啟 MD 後按 `Ctrl+Shift+V` 可預覽表格與標題。事件內容依現有切分結果呈現，仍需對照 PDF 確認。

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
