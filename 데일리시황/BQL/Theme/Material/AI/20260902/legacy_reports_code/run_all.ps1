param([switch]$UpdateRaw,[switch]$UseExistingData,[switch]$Pdf,[switch]$Open)
& (Join-Path $PSScriptRoot 'run_ai_report.ps1') -Period ALL -UpdateRaw:$UpdateRaw -UseExistingData:$UseExistingData -Pdf:$Pdf -Open:$Open
