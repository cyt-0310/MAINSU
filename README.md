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

## 資料存放（Neon 資料庫）

所有資料都以 Neon 為準，所以任何一台電腦執行 `start-all.ps1`、登入同一個帳號，看到的內容都一樣。
每台電腦都要設定同一個 `NEON_DATABASE_URL`（一次性，存在 Windows 使用者環境變數，不放進專案）：

```powershell
[Environment]::SetEnvironmentVariable('NEON_DATABASE_URL', (Get-Clipboard).Trim(), 'User')
```

| 資料 | 資料表 |
|---|---|
| 帳號、登入狀態、重設密碼驗證碼 | `users`、`auth_sessions`、`password_reset_codes` |
| 面試報告與申請校系（網頁端） | `user_app_state` |
| 備審 PDF、解析結果、題庫與檢索資料 | `web_portfolio_files`（程式：`web_store.py`；JSON 以 gzip 壓縮） |
| 面試過程紀錄 | `web_interview_records` |

- `MAINSU-upload/github-share/web_data/` 只是本機副本：檔案寫入後立刻上傳，讀取前若資料庫有較新的版本就先下載。可以整個刪掉，需要時會自動從資料庫取回。
- 備審分析在上傳的那台電腦執行，每分鐘回報一次進度；其他電腦超過 15 分鐘沒收到進度才會顯示「分析已中斷」。
- 舊版只存在本機、但已標記擁有者的備審與面試，該帳號登入後會自動上傳一次。
- Neon 免費版有 0.5 GB 空間。
- 不要提交金鑰、真實備審或問答紀錄；`web_data/` 和 `outputs/` 都已列入 `.gitignore`。

## 忘記密碼（Gmail 寄驗證碼）

需要一個開了兩步驟驗證的 Gmail 帳號，並建立「應用程式密碼」（Google 帳戶 → 安全性 → 應用程式密碼）。
複製應用程式密碼後，在 PowerShell 執行（存在 Windows 使用者環境變數，不放進專案）：

```powershell
[Environment]::SetEnvironmentVariable('MAINSU_SMTP_USER', '你的帳號@gmail.com', 'User')
[Environment]::SetEnvironmentVariable('MAINSU_SMTP_PASSWORD', (Get-Clipboard).Trim(), 'User')
```

設定後重新執行 `start-backend.ps1`。驗證碼 15 分鐘內有效、可試 5 次、每分鐘最多寄一次；重設成功會登出所有電腦。

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

## 帳號（註冊／登入）

帳號存在 Neon 的 `users`，登入狀態存在 `auth_sessions`（30 天，瀏覽器只拿到 HttpOnly cookie，資料庫存它的 SHA-256）。
程式在 `integration_review/integrated/web_auth.py`，需要 `NEON_DATABASE_URL`。

- 密碼以 scrypt 雜湊後儲存，不會存明碼。
- 面試報告與申請校系會同步到 `user_app_state`，在別台電腦登入後自動載回。
- 登出會清除這台電腦上的個人資料。
- 備審與面試都綁定帳號：每個人只看得到、只能取用自己的；同一校系每個帳號各能上傳一次。未登入的請求一律回 401。
- 備審與面試都存在 Neon（見下方「資料存放」），換電腦登入也看得到。
- 綁定前上傳、沒有記錄擁有者的舊備審與舊面試，任何帳號都看不到。

| 方法 | 路徑 | 說明 |
|---|---|---|
| POST | `/api/auth/register` | `{name, email, password}` 註冊並登入 |
| POST | `/api/auth/login` | `{email, password}` 登入 |
| POST | `/api/auth/logout` | 登出 |
| GET／PATCH | `/api/auth/me` | 目前使用者／修改姓名 `{name}` |
| POST | `/api/auth/password` | `{currentPassword, newPassword}` 變更密碼，並登出其他電腦 |
| POST | `/api/auth/forgot` | `{email}` 寄出 6 位數驗證碼（不論信箱是否註冊，回應都一樣） |
| POST | `/api/auth/reset` | `{email, code, newPassword}` 用驗證碼重設密碼並登入 |
| GET | `/api/me/state` | 取得同步的報告與校系 |
| PUT | `/api/me/state/{reports\|targets}` | `{value: [...]}` 上傳同步資料 |

## 尚未串接（仍為介面展示）

總覽、申請資料、帳號設定中的「刪除帳號」，以及免費版面試／報告。語音、攝影機、口語表達與面部分析在後端沒有對應功能，目前只支援文字作答。
