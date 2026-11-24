# 啟動 MAINSU 後端（Python API，http://127.0.0.1:8000）
# 用法：在 MAINSU-main 資料夾執行  powershell -ExecutionPolicy Bypass -File .\start-backend.ps1
$ErrorActionPreference = 'Stop'
$root = Join-Path $PSScriptRoot 'github-share'
$app = Join-Path $root 'integration_review\integrated'
$venv = Join-Path $root '.venv'
$py = Join-Path $venv 'Scripts\python.exe'

if (-not (Test-Path $py)) {
    Write-Host '第一次執行：建立 Python 3.12 虛擬環境並安裝套件（PDF 解析套件較大，需要幾分鐘）……'
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3.12 -m venv $venv } else { python -m venv $venv }
    & $py -m pip install --upgrade pip
}

& $py -c 'import starlette, uvicorn, python_multipart, pypdfium2, openai, docling, sentence_transformers'
if ($LASTEXITCODE -ne 0) {
    & $py -m pip install -r (Join-Path $app 'requirements-ai.txt') -r (Join-Path $app 'requirements-web.txt') -r (Join-Path $root 'docling_pdf\requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw '後端套件安裝失敗。' }
}

# 讀取用 [Environment]::SetEnvironmentVariable(..., 'User') 存過的設定（Neon 連線字串、Gemini 金鑰）
foreach ($name in 'GEMINI_API_KEY', 'OPENAI_API_KEY', 'OPENAI_MODEL', 'LLM_PROVIDER', 'GEMINI_MODEL', 'LLM_FALLBACK') {
    if (-not (Get-Item "env:$name" -ErrorAction SilentlyContinue)) {
        $saved = [Environment]::GetEnvironmentVariable($name, 'User')
        if ($saved) { Set-Item "env:$name" $saved }
    }
}
if ($env:LLM_FALLBACK -eq 'openai' -and $env:OPENAI_API_KEY -and $env:OPENAI_MODEL) { Write-Host "Gemini 忙碌時會自動改用 OpenAI（$($env:OPENAI_MODEL)）" }

if (-not $env:LLM_PROVIDER) { $env:LLM_PROVIDER = 'gemini' }
if (-not $env:GEMINI_TRANSPORT) { $env:GEMINI_TRANSPORT = 'rest' }
if (-not $env:GEMINI_MODEL) { $env:GEMINI_MODEL = 'gemini-3.5-flash-lite' }
if ($env:LLM_PROVIDER -eq 'gemini' -and -not $env:GEMINI_API_KEY) {
    Write-Host '尚未設定 GEMINI_API_KEY。可以先提交備審，設定金鑰並重啟後可重新分析原檔。'
}

Write-Host '後端啟動中：http://127.0.0.1:8000  （按 Ctrl+C 停止）'
& $py -m uvicorn api_server:app --app-dir $app --host 127.0.0.1 --port 8000
