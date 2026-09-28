[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$InputFiles
)

$ErrorActionPreference = 'Stop'
$dashboardDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$dashboardRoot = Split-Path -Parent $dashboardDir
$bqlDir = Split-Path -Parent $dashboardRoot
$pythonCommand = Get-Command python -ErrorAction Stop
$masterUpdater = Join-Path $bqlDir 'Rawfile\update_master.py'
$master = Join-Path $bqlDir 'Rawfile\BQuant_Master.xlsx'
$dashboardBuilder = Join-Path $dashboardRoot 'build_regional_dashboards.py'

& $pythonCommand.Source $masterUpdater @InputFiles
if ($LASTEXITCODE -ne 0) {
    throw "Master append failed with exit code $LASTEXITCODE"
}

& $pythonCommand.Source $dashboardBuilder --region europe $master
if ($LASTEXITCODE -ne 0) {
    throw "Integrated dashboard build failed with exit code $LASTEXITCODE"
}

Write-Host "Master: $master"
Write-Host "Dashboard: $(Join-Path $dashboardDir 'Market_Rotation_Dashboard_17_Indices.html')"
