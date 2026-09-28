<#
.SYNOPSIS
    Automated PostgreSQL + PostGIS Backup Utility for NWIS.
.DESCRIPTION
    Creates a consistent, schema-and-data backup of the NWIS database.
    Supports native pg_dump or docker-compose execution.
    Generates SHA-256 verification checksums for every backup artifact.
.PARAMETER OutputDir
    Directory path to store backup artifacts (defaults to database/backups).
.PARAMETER Database
    Target database name (default: nwis).
.PARAMETER User
    PostgreSQL user (default: nwis_admin).
.PARAMETER Host
    Database host (default: 127.0.0.1).
.PARAMETER Port
    Database port (default: 5432).
.PARAMETER UseDocker
    Run pg_dump inside running docker container 'nwis-postgres-postgis'.
#>

[CmdletBinding()]
param (
    [string]$OutputDir = "",
    [string]$Database = "nwis",
    [string]$User = "nwis_admin",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 5432,
    [switch]$UseDocker
)

$ErrorActionPreference = "Stop"

if (-not $OutputDir) {
    $scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
    if (-not $scriptDir) { $scriptDir = (Get-Location).Path }
    $OutputDir = Join-Path $scriptDir "..\database\backups"
}

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "NWIS - PostgreSQL Backup Utility" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Ensure target directory exists
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    Write-Host "[OK] Created backup directory: $OutputDir" -ForegroundColor Green
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFilename = "nwis_backup_${timestamp}.sql"
$backupPath = Join-Path $OutputDir $backupFilename

Write-Host "Target Database: $Database" -ForegroundColor White
Write-Host "Host:            $HostName : $Port" -ForegroundColor White
Write-Host "Target Artifact: $backupPath" -ForegroundColor White
Write-Host ""

# 2. Execute pg_dump
$success = $false

if ($UseDocker -or (-not (Get-Command pg_dump -ErrorAction SilentlyContinue))) {
    Write-Host "Checking Docker container 'nwis-postgres-postgis'..." -ForegroundColor Cyan
    try {
        $dockerCheck = docker ps --filter "name=nwis-postgres-postgis" --format "{{.Names}}"
        if ($dockerCheck -match "nwis-postgres-postgis") {
            Write-Host "Executing pg_dump inside docker container..." -ForegroundColor Cyan
            docker exec nwis-postgres-postgis pg_dump -U $User -d $Database --clean --if-exists --no-owner --no-privileges > $backupPath
            $success = $true
        } else {
            Write-Host "[WARNING] Docker container 'nwis-postgres-postgis' is not running." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[ERROR] Docker execution failed: $_" -ForegroundColor Red
    }
}

if (-not $success) {
    if (Get-Command pg_dump -ErrorAction SilentlyContinue) {
        Write-Host "Executing native pg_dump..." -ForegroundColor Cyan
        $env:PGPASSWORD = $env:POSTGRES_PASSWORD
        try {
            pg_dump -h $HostName -p $Port -U $User -d $Database --clean --if-exists --no-owner --no-privileges -f $backupPath
            $success = $true
        } catch {
            Write-Host "[ERROR] Native pg_dump failed: $_" -ForegroundColor Red
        }
    } else {
        Write-Host "[FALLBACK] Native pg_dump / Docker container not present. Utilizing Python schema & canonical data exporter..." -ForegroundColor Yellow
        $exportScript = Join-Path $scriptDir "export_schema_backup.py"
        try {
            python "$exportScript" "$backupPath"
            $success = $true
        } catch {
            Write-Host "[ERROR] Exporter fallback failed: $_" -ForegroundColor Red
            exit 1
        }
    }
}


# 3. Verify backup file
if (Test-Path $backupPath) {
    $fileInfo = Get-Item $backupPath
    if ($fileInfo.Length -gt 0) {
        $hash = (Get-FileHash -Path $backupPath -Algorithm SHA256).Hash
        $hashFile = "$backupPath.sha256"
        "$hash  $backupFilename" | Out-File -FilePath $hashFile -Encoding utf8

        Write-Host ""
        Write-Host "[SUCCESS] Backup completed successfully." -ForegroundColor Green
        Write-Host "  Path:     $backupPath" -ForegroundColor Green
        Write-Host "  Size:     $([math]::Round($fileInfo.Length / 1KB, 2)) KB" -ForegroundColor Green
        Write-Host "  SHA-256:  $hash" -ForegroundColor Green
        Write-Host "  Checksum: $hashFile" -ForegroundColor Green
        Write-Host "==================================================" -ForegroundColor Cyan
    } else {
        Write-Host "[ERROR] Backup file was created but is 0 bytes." -ForegroundColor Red
        Remove-Item $backupPath -Force
        exit 1
    }
} else {
    Write-Host "[ERROR] Backup artifact was not generated." -ForegroundColor Red
    exit 1
}
