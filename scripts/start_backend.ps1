<#
.SYNOPSIS
    Starts the NWIS FastAPI Backend on http://127.0.0.1:8000
.DESCRIPTION
    Checks if port 8000 is occupied, reports the process if blocked,
    and runs the canonical Uvicorn server as a single PowerShell command.
#>

$ErrorActionPreference = "Stop"
if (-not $PSScriptRoot) {
    $PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if (-not $PSScriptRoot) {
    $PSScriptRoot = (Get-Location).Path
}
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "NWIS - Starting Backend Server" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Verify Python availability
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# 2. Check if Port 8000 is already in use
$port = 8000
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
    Write-Host "[WARNING] Port $port is already in use or blocked!" -ForegroundColor Yellow
    Write-Host "  PID:          $pidOccupied" -ForegroundColor Yellow
    Write-Host "  Process:      $procName" -ForegroundColor Yellow
    Write-Host "  Path:         $procPath" -ForegroundColor Yellow
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
Write-Host "Starting NWIS Backend..." -ForegroundColor Cyan
Write-Host "  URL:     http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  Health:  http://127.0.0.1:8000/health" -ForegroundColor White
Write-Host "  Docs:    http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host ""

# Canonical single command execution
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
