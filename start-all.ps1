# 一鍵啟動 MAINSU：開兩個視窗分別跑後端與前端，再打開網頁
# 用法：在 MAINSU-main 資料夾執行  powershell -ExecutionPolicy Bypass -File .\start-all.ps1
$here = $PSScriptRoot
Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $here 'start-backend.ps1')
Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $here 'start-frontend.ps1')
Write-Host '已開啟後端與前端視窗；約 15 秒後自動打開網頁。要停止時，關掉那兩個視窗即可。'
Start-Sleep -Seconds 15
Start-Process 'http://localhost:8443'
