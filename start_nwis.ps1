<#
.SYNOPSIS
    Root launcher for NWIS (Nearby Wells Intelligence System).
    Invokes scripts/start_nwis.ps1
#>

if (-not $PSScriptRoot) {
    $PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if (-not $PSScriptRoot) {
    $PSScriptRoot = (Get-Location).Path
}

& "$PSScriptRoot\scripts\start_nwis.ps1" @args
