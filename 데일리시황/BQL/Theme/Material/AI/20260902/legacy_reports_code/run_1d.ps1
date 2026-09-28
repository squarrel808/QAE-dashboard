param([switch]$UpdateRaw,[switch]$UseExistingData,[switch]$Pdf,[switch]$Open)
& (Join-Path $PSScriptRoot 'run_ai_report.ps1') -Period 1D -UpdateRaw:$UpdateRaw -UseExistingData:$UseExistingData -Pdf:$Pdf -Open:$Open
