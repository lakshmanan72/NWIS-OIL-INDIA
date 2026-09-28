<#
.SYNOPSIS
    Starts the NWIS React/Vite Frontend on http://127.0.0.1:5173
.DESCRIPTION
    Checks if port 5173 is occupied, reports the process if blocked,
    and runs the Vite dev server with strictPort enabled.
#>

$ErrorActionPreference = "Stop"
if (-not $PSScriptRoot) {
    $PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if (-not $PSScriptRoot) {
    $PSScriptRoot = (Get-Location).Path
}
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendDir = Join-Path $ProjectRoot "frontend"
Set-Location $FrontendDir

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "NWIS - Starting Frontend Dev Server" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Verify Node and npm availability
try {
    $nodeVersion = node --version 2>&1
    $npmVersion = npm --version 2>&1
    Write-Host "[OK] Node: $nodeVersion" -ForegroundColor Green
    Write-Host "[OK] npm:  $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Node.js or npm is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# 2. Verify node_modules
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "[WARNING] frontend/node_modules not found. Running npm install..." -ForegroundColor Yellow
    npm install
}

# 3. Check if Port 5173 is already in use
$port = 5173
$conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue

if ($conn) {
    $pidOccupied = $conn[0].OwningProcess
    $procName = "Unknown"
    $procPath = "Unknown"
    try {
        $p = Get-Process -Id $pidOccupied -ErrorAction SilentlyContinue
        if ($p) {
            $procName = $p.ProcessName
            $procPath = $p.Path
        }
    } catch {}

    Write-Host ""
    Write-Host "[WARNING] Port $port is already in use!" -ForegroundColor Yellow
    Write-Host "  PID:          $pidOccupied" -ForegroundColor Yellow
    Write-Host "  Process:      $procName" -ForegroundColor Yellow
    Write-Host "  Path:         $procPath" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Vite strictPort is enabled. NWIS will NOT silently switch to 5174." -ForegroundColor White
    Write-Host ""
    Write-Host "To find this process manually, run:" -ForegroundColor White
    Write-Host "  netstat -ano | findstr :$port" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To safely terminate this process, run:" -ForegroundColor White
    Write-Host "  Stop-Process -Id $pidOccupied -Force" -ForegroundColor Cyan
    Write-Host "  # or in CMD: taskkill /PID $pidOccupied /F" -ForegroundColor Gray
    Write-Host ""
    Write-Host "NWIS will NOT kill processes automatically." -ForegroundColor Yellow
    exit 1
}

Write-Host "[OK] Port $port is free." -ForegroundColor Green
Write-Host ""
Write-Host "Starting NWIS Frontend..." -ForegroundColor Cyan
Write-Host "  URL:     http://127.0.0.1:5173" -ForegroundColor White
Write-Host "  Target:  http://127.0.0.1:8000 (Backend Proxy)" -ForegroundColor White
Write-Host ""

npm run dev
