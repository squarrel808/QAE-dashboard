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
$euroDir = Join-Path $bqlDir '유로존_dashboard'
$aiDir = Join-Path $bqlDir 'Theme\AI'
$top10Dir = Join-Path $bqlDir 'Theme\Top10_Down10'

& $pythonCommand.Source (Join-Path $euroDir 'build_market_rotation_dashboard.py') $master
if ($LASTEXITCODE -ne 0) {
    throw "Market dashboard build failed with exit code $LASTEXITCODE"
}

& $pythonCommand.Source (Join-Path $aiDir 'build_sp500_ai_value_chain.py') --output (Join-Path $aiDir 'SP500_AI_Value_Chain_Rotation.html') $master
if ($LASTEXITCODE -ne 0) {
    throw "AI dashboard build failed with exit code $LASTEXITCODE"
}

& (Join-Path $top10Dir 'run_top10_update.ps1') $master
if ($LASTEXITCODE -ne 0) {
    throw "Top10/Down10 build failed with exit code $LASTEXITCODE"
}

Write-Host "완료"
Write-Host "Master: $master"
Write-Host "Market dashboard: $(Join-Path $euroDir 'Market_Rotation_Dashboard_17_Indices.html')"
Write-Host "AI dashboard: $(Join-Path $aiDir 'SP500_AI_Value_Chain_Rotation.html')"
Write-Host "Top10 pointer: $(Join-Path $top10Dir 'output\latest_outputs.json')"

