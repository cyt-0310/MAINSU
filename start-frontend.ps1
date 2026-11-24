# 啟動 MAINSU 前端（React + Vite）
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8445
)

$ErrorActionPreference = 'Stop'
$frontend = Join-Path $PSScriptRoot 'MAINSU_web'
$node = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $node) {
    throw '找不到 Node.js。請安裝 Node.js LTS，重新開啟 PowerShell 後再執行。'
}

Push-Location $frontend
try {
    $vite = Join-Path $frontend 'node_modules\vite\bin\vite.js'
    $rootVite = Join-Path $PSScriptRoot 'node_modules\vite\bin\vite.js'
    if (-not (Test-Path -LiteralPath $vite) -and (Test-Path -LiteralPath $rootVite)) {
        $vite = $rootVite
    }
    if (-not (Test-Path -LiteralPath $vite)) {
        $pnpm = Get-Command pnpm.cmd,pnpm.exe -ErrorAction SilentlyContinue | Select-Object -First 1
        $npx = Get-Command npx.cmd -ErrorAction SilentlyContinue
        Write-Host '第一次執行：安裝前端套件……'
        if ($pnpm) {
            & $pnpm.Source install --frozen-lockfile
        } elseif ($npx) {
            & $npx.Source -y pnpm@10 install --frozen-lockfile
        } else {
            throw '找不到 pnpm 或 npx。請安裝包含 npm 的 Node.js LTS，重新開啟 PowerShell 後再執行。'
        }
        if ($LASTEXITCODE -ne 0) {
            throw "安裝前端套件失敗（結束代碼 $LASTEXITCODE）。"
        }
    }

    & $node.Source $vite --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) {
        throw "前端啟動失敗（結束代碼 $LASTEXITCODE）。"
    }
} finally {
    Pop-Location
}
