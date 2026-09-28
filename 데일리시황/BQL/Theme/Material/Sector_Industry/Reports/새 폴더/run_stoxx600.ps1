param(
    [switch]$UpdateRaw,
    [switch]$Pdf,
    [switch]$Open
)

& (Join-Path $PSScriptRoot "run_sector_industry_report.ps1") -Market STOXX600 -UpdateRaw:$UpdateRaw -Pdf:$Pdf -Open:$Open
