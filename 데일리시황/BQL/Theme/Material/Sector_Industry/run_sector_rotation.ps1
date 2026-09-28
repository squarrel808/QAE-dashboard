[CmdletBinding()]
param(
    [ValidateSet("1D", "5D", "Daily", "Weekly")]
    [string]$Period = "1D",

    [ValidateSet("ALL", "STOXX600", "TOPIX")]
    [string]$Market = "ALL",

    [datetime]$AsOf = (Get-Date).Date.AddDays(-1),

    [ValidateRange(1, 8)]
    [int]$TopN = 8,

    [Alias("SkipUpdate")]
    [switch]$SkipMasterUpdate,

    [switch]$AllowMixedAsOf
)

$ErrorActionPreference = "Stop"

# Installed location: Theme\Material\Sector_Industry\run_sector_rotation.ps1
$categoryDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$materialDir = Split-Path -Parent $categoryDir
$themeDir = Split-Path -Parent $materialDir
$bqlDir = Split-Path -Parent $themeDir
$rawDir = Join-Path $bqlDir "Rawfile"
$master = Join-Path $rawDir "BQuant_Master.xlsx"
$builder = Join-Path $categoryDir "Reports\build_sector_snapshot.py"
$outputRoot = Join-Path $themeDir "output"
$materialRoot = $categoryDir
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
    "--output-root", $outputRoot,
    "--material-root", $materialRoot,
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

if ($periodKey -eq "1D" -and $Market -in @("ALL", "TOPIX")) {
    $topixDailyRunner = Join-Path $categoryDir "Reports\run_topix_daily_report.ps1"
    if (-not (Test-Path -LiteralPath $topixDailyRunner -PathType Leaf)) {
        throw "TOPIX daily report runner not found: $topixDailyRunner"
    }
    & $topixDailyRunner
}

Write-Host "완료: $periodKey / $Market"
Write-Host "요청 기준일: $($AsOf.ToString('yyyy-MM-dd'))"
Write-Host "결과 루트: $outputRoot"
Write-Host "계산 자료: $materialRoot"
