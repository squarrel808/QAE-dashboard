[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$InputFiles
)

$ErrorActionPreference = 'Stop'
$rawDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$bqlDir = Split-Path -Parent $rawDir
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue

if (-not $pythonCommand) {
    throw 'Python을 찾지 못했습니다. Python 3와 numpy, openpyxl, pyxlsb, xlsxwriter를 설치하세요.'
}

& $pythonCommand.Source (Join-Path $rawDir 'update_master.py') @InputFiles
if ($LASTEXITCODE -ne 0) {
    throw "Master append failed with exit code $LASTEXITCODE"
}

$master = Join-Path $rawDir 'BQuant_Master.xlsx'
$dashboardRoot = Join-Path $bqlDir 'Dashbaord'
$euroDir = Join-Path $dashboardRoot '유로존_dashboard'
$topixDir = Join-Path $dashboardRoot 'TOPIX_dashboard'
$usDir = Join-Path $dashboardRoot 'US_dashboard'
$aiDir = Join-Path $bqlDir 'Theme\Material\AI'
$top10Dir = Join-Path $bqlDir 'Theme\Material\Top10_Down10'

& $pythonCommand.Source (Join-Path $dashboardRoot 'build_regional_dashboards.py') --region all $master
if ($LASTEXITCODE -ne 0) {
    throw "Regional dashboards build failed with exit code $LASTEXITCODE"
}

$aiOutput = @(& $pythonCommand.Source (Join-Path $aiDir 'build_sp500_ai_value_chain.py') $master)
if ($LASTEXITCODE -ne 0) {
    throw "AI dashboard build failed with exit code $LASTEXITCODE"
}
$aiOutputLine = $aiOutput | Where-Object { $_ -is [string] -and $_.StartsWith('output=') } | Select-Object -Last 1
$aiOutputPath = if ($aiOutputLine) { $aiOutputLine.Substring('output='.Length) } else { '(see AI runner output)' }

& (Join-Path $top10Dir 'run_top10_update.ps1') $master
if ($LASTEXITCODE -ne 0) {
    throw "Top10/Down10 build failed with exit code $LASTEXITCODE"
}

Write-Host "완료"
Write-Host "Master: $master"
Write-Host "Market dashboard: $(Join-Path $euroDir 'Market_Rotation_Dashboard_17_Indices.html')"
Write-Host "TOPIX dashboard: $(Join-Path $topixDir 'TOPIX_Rotation_Dashboard.html')"
Write-Host "US dashboard: $(Join-Path $usDir 'US_Rotation_Dashboard.html')"
Write-Host "AI dashboard: $aiOutputPath"
Write-Host "Top10 pointer: $(Join-Path $top10Dir 'latest_outputs.json')"
