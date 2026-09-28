[CmdletBinding()]
param(
    [string]$Data,
    [string]$Output
)

$ErrorActionPreference = 'Stop'
$reportDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$categoryDir = Split-Path -Parent $reportDir
$materialDir = Split-Path -Parent $categoryDir
$themeDir = Split-Path -Parent $materialDir
$pointer = Join-Path $categoryDir 'latest_1D.json'

if (-not $Data) {
    if (-not (Test-Path -LiteralPath $pointer -PathType Leaf)) {
        throw "TOPIX daily pointer was not found: $pointer"
    }
    $latest = Get-Content -LiteralPath $pointer -Raw -Encoding UTF8 | ConvertFrom-Json
    $Data = [string]$latest.json
}

if (-not (Test-Path -LiteralPath $Data -PathType Leaf)) {
    throw "TOPIX daily calculation JSON was not found: $Data"
}

$payload = Get-Content -LiteralPath $Data -Raw -Encoding UTF8 | ConvertFrom-Json
$topix = $payload.markets | Where-Object { $_.key -eq 'TOPIX' } | Select-Object -First 1
if ($null -eq $topix) {
    throw "TOPIX is not present in calculation JSON: $Data"
}

$dateTag = ([string]$topix.asOf).Replace('-', '')
if (-not $Output) {
    $Output = Join-Path (Join-Path (Join-Path $themeDir 'output') $dateTag) "Sector_Industry\TOPIX_섹터_산업_1D_보고서_$dateTag.docx"
}

$runtimeRoot = 'C:\Users\infomax\.cache\codex-runtimes\codex-primary-runtime\dependencies'
$node = Join-Path $runtimeRoot 'node\bin\node.exe'
$nodeModules = Join-Path $runtimeRoot 'node\node_modules'
if (-not (Test-Path -LiteralPath $node)) {
    $node = (Get-Command node -ErrorAction Stop).Source
}
if (Test-Path -LiteralPath $nodeModules) {
    $env:NODE_PATH = $nodeModules
}

$generator = Join-Path $reportDir 'generate_topix_daily_report.js'
& $node $generator --data $Data --output $Output
if ($LASTEXITCODE -ne 0) {
    throw "TOPIX daily report generation failed with exit code $LASTEXITCODE"
}

Write-Host "TOPIX daily report: $Output"
