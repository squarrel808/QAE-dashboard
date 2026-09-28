[CmdletBinding()]
param(
    [ValidateSet("1D", "5D", "Daily", "Weekly")]
    [string]$Period = "1D",

    [ValidateSet("ALL", "STOXX600", "TOPIX")]
    [string]$Market = "ALL",

    [datetime]$AsOf = (Get-Date).Date.AddDays(-1),

    [ValidateRange(1, 8)]
    [int]$TopN = 8,

    [switch]$SkipMasterUpdate,

    [switch]$AllowMixedAsOf
)

$ErrorActionPreference = "Stop"

$themeDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$bqlDir = Split-Path -Parent $themeDir
$rawDir = Join-Path $bqlDir "Rawfile"
$master = Join-Path $rawDir "BQuant_Master.xlsx"
$builder = Join-Path $themeDir "Sector_Industry\Reports\build_sector_snapshot.py"
$outputDir = Join-Path $themeDir "output\Sector_Industry"
$python = (Get-Command python -ErrorAction Stop).Source

$periodKey = switch ($Period.ToUpperInvariant()) {
    "DAILY" { "1D" }
    "WEEKLY" { "5D" }
    default { $Period.ToUpperInvariant() }
}

if (-not $SkipMasterUpdate) {
    & $python (Join-Path $rawDir "update_master.py")
    if ($LASTEXITCODE -ne 0) {
        throw "BQuant Master update failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path -LiteralPath $master)) {
    throw "BQuant Master workbook not found: $master"
}
if (-not (Test-Path -LiteralPath $builder)) {
    throw "Sector snapshot builder not found: $builder"
}

$builderArgs = @(
    $builder,
    "--period", $periodKey,
    "--market", $Market,
    "--master", $master,
    "--output-dir", $outputDir,
    "--as-of", $AsOf.ToString("yyyy-MM-dd"),
    "--top-n", $TopN
)
if ($AllowMixedAsOf) {
    $builderArgs += "--allow-mixed-as-of"
}

& $python @builderArgs
if ($LASTEXITCODE -ne 0) {
    throw "Sector snapshot build failed with exit code $LASTEXITCODE"
}

Write-Host "완료: $periodKey / $Market"
Write-Host "요청 기준일: $($AsOf.ToString('yyyy-MM-dd'))"
Write-Host "산출물: $outputDir"
