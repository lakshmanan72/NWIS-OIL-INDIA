<#
.SYNOPSIS
    Comprehensive startup launcher for NWIS (Backend + Frontend).
.DESCRIPTION
    Validates Python, Node, dependencies, and ports 8000 & 5173.
    If ports are free, launches both services in dedicated terminals.
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
Set-Location $ProjectRoot

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "NWIS - NEARBY WELLS INTELLIGENCE SYSTEM" -ForegroundColor Cyan
Write-Host "Local Development Startup Verifier & Launcher" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python
Write-Host "[1/6] Checking Python runtime..." -ForegroundColor Cyan
try {
    $pythonVersion = python --version 2>&1
    Write-Host "      [OK] Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "      [ERROR] Python is not installed or not found in PATH." -ForegroundColor Red
    exit 1
}

# 2. Check Node & npm
Write-Host "[2/6] Checking Node.js and npm..." -ForegroundColor Cyan
try {
    $nodeVersion = node --version 2>&1
    $npmVersion = npm --version 2>&1
    Write-Host "      [OK] Node: $nodeVersion" -ForegroundColor Green
    Write-Host "      [OK] npm:  $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "      [ERROR] Node.js or npm is not installed or not found in PATH." -ForegroundColor Red
    exit 1
}

# 3. Check Backend Dependencies
Write-Host "[3/6] Checking Backend Python dependencies..." -ForegroundColor Cyan
try {
    $checkDeps = python -c "import fastapi, uvicorn, pydantic; print('OK')" 2>&1
    if ($checkDeps -match "OK") {
        Write-Host "      [OK] FastAPI, Uvicorn, Pydantic available." -ForegroundColor Green
    } else {
        Write-Host "      [WARNING] Backend dependencies check returned: $checkDeps" -ForegroundColor Yellow
    }
} catch {
    Write-Host "      [ERROR] Missing required Python packages (fastapi/uvicorn)." -ForegroundColor Red
    Write-Host "      Run: pip install -r backend/requirements.txt" -ForegroundColor Yellow
    exit 1
}

# 4. Check Frontend Dependencies
Write-Host "[4/6] Checking Frontend npm dependencies..." -ForegroundColor Cyan
if (Test-Path (Join-Path $FrontendDir "node_modules")) {
    Write-Host "      [OK] frontend/node_modules present." -ForegroundColor Green
} else {
    Write-Host "      [WARNING] frontend/node_modules missing! Installing..." -ForegroundColor Yellow
    Push-Location $FrontendDir
    npm install
    Pop-Location
}

# 5. Check Port 8000 (Backend)
Write-Host "[5/6] Checking Port 8000 (Backend)..." -ForegroundColor Cyan
$port8000Conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
$backendRunning = $false

if ($port8000Conn) {
    $backendRunning = $true
    $pid8000 = $port8000Conn[0].OwningProcess
    $name8000 = "Unknown"
    $path8000 = "Unknown"
    try {
        $p = Get-Process -Id $pid8000 -ErrorAction SilentlyContinue
        if ($p) { $name8000 = $p.ProcessName; $path8000 = $p.Path }
    } catch {}

    Write-Host "      [ALREADY RUNNING] Port 8000 is occupied (PID: $pid8000, Process: $name8000)." -ForegroundColor Yellow
    Write-Host "      -> Backend service is already running. A duplicate server will not be started." -ForegroundColor Yellow
} else {
    Write-Host "      [OK] Port 8000 is free." -ForegroundColor Green
}

# 6. Check Port 5173 (Frontend)
Write-Host "[6/6] Checking Port 5173 (Frontend)..." -ForegroundColor Cyan
$port5173Conn = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
$frontendRunning = $false

if ($port5173Conn) {
    $frontendRunning = $true
    $pid5173 = $port5173Conn[0].OwningProcess
    $name5173 = "Unknown"
    $path5173 = "Unknown"
    try {
        $p = Get-Process -Id $pid5173 -ErrorAction SilentlyContinue
        if ($p) { $name5173 = $p.ProcessName; $path5173 = $p.Path }
    } catch {}

    Write-Host "      [ALREADY RUNNING] Port 5173 is occupied (PID: $pid5173, Process: $name5173)." -ForegroundColor Yellow
    Write-Host "      -> Frontend service is already running. A duplicate server will not be started." -ForegroundColor Yellow
} else {
    Write-Host "      [OK] Port 5173 is free." -ForegroundColor Green
}

# Launch any service not already running
Write-Host ""
$backendScript = Join-Path $PSScriptRoot "start_backend.ps1"
$frontendScript = Join-Path $PSScriptRoot "start_frontend.ps1"

if (-not $backendRunning) {
    Write-Host "Launching persistent NWIS Backend process..." -ForegroundColor Cyan
    $backendProc = Start-Process powershell.exe -WorkingDirectory $ProjectRoot -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$backendScript`"" -PassThru
    
    # Wait for Backend to start listening
    Write-Host "Waiting for Backend to start listening on http://127.0.0.1:8000..." -ForegroundColor Cyan
    $backendReady = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        if ($backendProc.HasExited) {
            Write-Host "      [ERROR] Backend child process exited immediately (ExitCode: $($backendProc.ExitCode))." -ForegroundColor Red
            Write-Host "      Stdout/Stderr is preserved in the backend PowerShell window." -ForegroundColor Yellow
            exit 1
        }
        $conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
        if ($conn) {
            $backendReady = $true
            break
        }
    }
    if (-not $backendReady) {
        Write-Host "      [ERROR] Backend failed to start listening on port 8000 within timeout." -ForegroundColor Red
        exit 1
    }
    Write-Host "      [OK] Backend is listening on port 8000." -ForegroundColor Green
}

if (-not $frontendRunning) {
    Write-Host "Launching persistent NWIS Frontend process..." -ForegroundColor Cyan
    $frontendProc = Start-Process powershell.exe -WorkingDirectory $FrontendDir -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$frontendScript`"" -PassThru
    
    # Wait for Frontend to start listening
    Write-Host "Waiting for Frontend to start listening on http://127.0.0.1:5173..." -ForegroundColor Cyan
    $frontendReady = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        if ($frontendProc.HasExited) {
            Write-Host "      [ERROR] Frontend child process exited immediately (ExitCode: $($frontendProc.ExitCode))." -ForegroundColor Red
            Write-Host "      Stdout/Stderr is preserved in the frontend PowerShell window." -ForegroundColor Yellow
            exit 1
        }
        $conn = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
        if ($conn) {
            $frontendReady = $true
            break
        }
    }
    if (-not $frontendReady) {
        Write-Host "      [ERROR] Frontend failed to start listening on port 5173 within timeout." -ForegroundColor Red
        exit 1
    }
    Write-Host "      [OK] Frontend is listening on port 5173." -ForegroundColor Green
}

# Verify Endpoints
Write-Host ""
Write-Host "Verifying service endpoints..." -ForegroundColor Cyan
try {
    $backendRes = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 5
    if ($backendRes.StatusCode -eq 200) {
        Write-Host "  [OK] Backend /health: HTTP 200" -ForegroundColor Green
    }
} catch {
    Write-Host "  [WARNING] Backend /health check returned: $_" -ForegroundColor Yellow
}

try {
    $frontendRes = Invoke-WebRequest -Uri "http://127.0.0.1:5173/" -UseBasicParsing -TimeoutSec 5
    if ($frontendRes.StatusCode -eq 200) {
        Write-Host "  [OK] Frontend /: HTTP 200" -ForegroundColor Green
    }
} catch {
    Write-Host "  [WARNING] Frontend / check returned: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "NWIS SERVICES RUNNING" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "NWIS BACKEND:   http://127.0.0.1:8000" -ForegroundColor White
Write-Host "NWIS FRONTEND:  http://127.0.0.1:5173" -ForegroundColor White
Write-Host "HEALTH:         http://127.0.0.1:8000/health" -ForegroundColor White
Write-Host "READINESS:      http://127.0.0.1:8000/api/ready" -ForegroundColor White
Write-Host "SWAGGER DOCS:   http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Advisory: NWIS is a decision-support system. Autonomous rig control is prohibited." -ForegroundColor Gray

