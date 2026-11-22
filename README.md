# MAINSU：備審個人化文字面試（前端＋後端）

| 資料夾 | 內容 |
|---|---|
| `MAINSU_web/` | 前端：React + Vite + Tailwind 網站 |
| `MAINSU-upload/github-share/` | 後端：Python 3.12，PDF 解析、RAG、題庫、Gemini 評分與追問 |
| `MAINSU-upload/github-share/integration_review/integrated/api_server.py` | 串接兩邊的 HTTP API（FastAPI） |

## 串接流程

```
網站「備審資料」上傳 PDF ──► POST /api/projects/{id}/files
         「開始分析」     ──► parse_pdf.py 解析 → ai_services.prepare 建索引與題庫（背景執行，網頁每 2 秒更新狀態）
網站「備審分析」         ◄── events.structured.json、topics.json
網站「模擬面試」文字作答 ──► InterviewSession（相關度、完整度、重述、追問）
網站「面試報告」         ◄── 面試紀錄 snapshot
```

開發時前端的 `/api` 由 Vite 自動轉送到 `http://127.0.0.1:8000`（設定在 `MAINSU_web/vite.config.ts`）。

## 啟動（Windows PowerShell，開兩個視窗）

在 `MAINSU-main` 資料夾：

```powershell
# 視窗 1：後端。第一次會建立 .venv 並安裝套件；會提示貼上自己的 Gemini 金鑰
powershell -ExecutionPolicy Bypass -File .\start-backend.ps1

# 視窗 2：前端
powershell -ExecutionPolicy Bypass -File .\start-frontend.ps1
```

開啟 http://localhost:8443 → 「備審資料」→ 先按 **使用虛構範例** 測試整個流程 → 「查看分析結果」→「前往面試準備」→「開始面試」。

- 第一次分析與第一次面試需要下載嵌入／相關度模型，會比較久。
- PDF 解析（Docling + EasyOCR）較慢，一份 PDF 可能需要數分鐘。
- 作答：輸入文字後按 **Enter 送出**，**Shift + Enter 換行**；時間到會自動送出目前文字。

## 資料與隱私

上傳的 PDF、解析結果、題庫與面試紀錄都存在 `MAINSU-upload/github-share/web_data/`，已列入 `.gitignore`。
不要提交金鑰、真實備審或問答紀錄。`outputs/` 裡現有的真實解析檔也已排除，請勿上傳到 GitHub。

## Neon 資料庫同步（選用）

設定 `NEON_DATABASE_URL` 後（一次性，存在 Windows 使用者環境變數，不放進專案）：

```powershell
[Environment]::SetEnvironmentVariable('NEON_DATABASE_URL', (Get-Clipboard).Trim(), 'User')
```

後端會在背景把結果寫進 Neon（程式在 `integration_review/integrated/neon_store.py`）：

| 時機 | 寫入的表格 |
|---|---|
| 分析完成 | `portfolios`、`documents`、`document_blocks`、`events`、`event_sources`、`retrieval_chunks`（含向量） |
| 開始面試／每答一題 | `interview_sessions`、`interview_units`、`interview_questions`、`answers`、`evaluations`、`completeness_items`、`consistency_findings` |
| 面試結束 | 以上更新＋`reports` |

- 本機 `web_data/` 仍是主要資料；Neon 寫入失敗不會中斷分析或面試，網頁會顯示「Neon 同步失敗」。
- 網站還沒有登入功能，所以使用預設使用者「示範使用者」與校系（`MAINSU_SCHOOL_NAME`，預設「未指定學校」＋ settings.json 的科系）。
- 每次分析會新增一筆 `portfolios`；同一場面試重複同步時會覆寫該場資料，不會重複新增。
- 尚未寫入：`question_bank`、`speech_metrics`、`face_events`、`free_usage_records`（文字版沒有對應資料）。

## API 一覽

| 方法 | 路徑 | 說明 |
|---|---|---|
| GET | `/api/health` | 模型服務與金鑰是否設定 |
| POST | `/api/projects` | 建立備審專案 |
| GET | `/api/projects/{id}` | 狀態、檔案；完成後含事件與題庫 |
| POST | `/api/projects/{id}/files` | 上傳 PDF（≤ 5MB） |
| DELETE | `/api/projects/{id}/files/{fileId}` | 移除 PDF |
| POST | `/api/projects/{id}/analyze` | 解析＋產生題庫（背景） |
| POST | `/api/projects/{id}/demo` | 改用虛構範例分析 |
| POST | `/api/projects/{id}/interviews` | 開始面試，回傳第一題 |
| POST | `/api/interviews/{sid}/answer` | 送出回答 `{answer, timed_out}`，回傳分析與下一題 |
| POST | `/api/interviews/{sid}/end` | 提前結束 |
| GET | `/api/interviews/{sid}/report` | 面試報告 |

分析回答時若模型服務出錯，後端會還原狀態，網頁可直接「重新送出」，不會重複記錄。

## 尚未串接（仍為介面展示）

總覽、申請資料、面試紀錄列表、帳號設定、登入註冊，以及免費版面試／報告。語音、攝影機、口語表達與面部分析在後端沒有對應功能，目前只支援文字作答。
