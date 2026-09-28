param(
    [ValidateSet("ALL", "STOXX600", "TOPIX")]
    [string]$Market = "ALL",
    [switch]$UpdateRaw,
    [switch]$Pdf,
    [switch]$Open
)

& (Join-Path $PSScriptRoot "run_sector_industry_report.ps1") -Market $Market -UpdateRaw:$UpdateRaw -Pdf:$Pdf -Open:$Open

