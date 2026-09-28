param(
    [switch]$UpdateRaw,
    [switch]$Pdf,
    [switch]$Open
)

& (Join-Path $PSScriptRoot "run_sector_industry_report.ps1") -Market ALL -UpdateRaw:$UpdateRaw -Pdf:$Pdf -Open:$Open
