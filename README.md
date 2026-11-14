# 備審文字面試：流程 2～12

Python 3.12 專案。以備審候選事件建立個人化題庫，透過 Gemini 評分、檢索原文證據及動態追問。只使用文字回答，不含語音、面部偵測、科系常見問題或第十三步報告。

## 功能與狀態

- Docling／EasyOCR PDF 解析、異常編碼局部補救、閱讀順序整理及候選事件切分。
- 事件父子層級、來源頁碼／座標、向量檢索、候選技能樹。
- 自介＋1～2 個備審事件；完整度門檻 55%，相關度低於 0.4 最多重述一次，仍離題就換題。
- 輸入文字後按 **Enter 立即結束本題回答並送出**，不必等待時間到。空白 Enter 會提醒補上文字；到時會提交目前已輸入文字。Ctrl+C 中斷面試。
- 一般單題 120 秒、自介 90 秒、主題 4 分鐘、全場 20 分鐘／15 題上限。模型等待時間計入面試時間。主題剩餘不足 60 秒時不再追問或重述，直接換下一個主題。時間到仍未作答視為相關度 0%，與離題共用每主題一次的重述機會。

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

API 模式會把備審與問答傳給服務。請先使用下方虛構範例；免費方案的資料使用條款請查看 [Google 官方價格說明](https://ai.google.dev/gemini-api/docs/pricing)。

## 3. 先用虛構資料跑題庫與面試

examples/fictional.events.json 是手寫的虛構解析格式範例，不是真實 PDF 的解析結果。它能測試第 5～12 步的接線，不驗證第 2～4 步 PDF 解析品質。

```powershell
New-Item -ItemType Directory -Force outputs | Out-Null
.\.venv\Scripts\python.exe integration_review\integrated\run_text_interview.py prepare examples\fictional.events.json --output outputs\demo-01
.\.venv\Scripts\python.exe integration_review\integrated\run_text_interview.py interview outputs\demo-01 --output outputs\session-01.json
```

題庫在 outputs/demo-01/topics.json；請先核對，再開始面試。回答會先保存再分析。重新練習請換新輸出名稱；接續原面試則在原本的 interview 指令最後加 `--resume`，保留相同題庫資料夾與 `--output` 紀錄路徑。

Gemini HTTP 500／502／503／504 會額外重試最多 3 次，等待約 2、4、8 秒並加隨機延遲；失敗請求及重試等待不計入面試時間。重試仍失敗時，按 Enter 重新分析已保存的回答，或輸入 `q` 保存離開。失敗回合不採用部分評分、不增加追問題數；只有新版包含 `runtime` 的紀錄支援續答。正常分析時間仍照原規則計算，尚未送出的輸入不保證能恢復。完整操作見 [面試程式說明](github-share/README.md#服務忙碌與中斷續答)。

## 4. 使用自己的 PDF

將個人檔案放進 data/，解析到 outputs/，這兩個目錄都排除於 Git 追蹤之外：

```powershell
.\.venv\Scripts\python.exe integration_review\integrated\run_text_interview.py parse data\自己的備審.pdf --output outputs\parsed-01
```

接著把 prepare 的輸入改為上一步產出的 .events.json。多份備審可依序列出多個 .events.json，但必須屬於同一學生。此倉庫不提供真實學生 PDF、解析結果、索引或問答紀錄。

## 5. 執行測試

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s integration_review\integrated -p "test_*.py"
```

不需要真實金鑰、不會發出付費 API 請求。兩個私人 PDF 回歸測試在共用版會跳過，公開虛構資料測試仍會執行。

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
