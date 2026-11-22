# 啟動 MAINSU 前端（React 網站，http://localhost:8443）
# 用法：在 MAINSU-main 資料夾執行  powershell -ExecutionPolicy Bypass -File .\start-frontend.ps1
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot 'MAINSU_web')
if (-not (Test-Path 'node_modules')) {
    Write-Host '第一次執行：安裝前端套件……'
    npx -y pnpm@10 install
}
Write-Host '前端啟動中：http://localhost:8443  （/api 會自動轉給後端 http://127.0.0.1:8000）'
npx -y pnpm@10 dev
