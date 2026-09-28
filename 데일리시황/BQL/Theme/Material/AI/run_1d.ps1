param([ValidatePattern('^\d{8}$')][string]$DateTag,[switch]$UpdateRaw,[switch]$UseExistingData,[switch]$Pdf,[switch]$Open)
$params = @{ Period='1D'; UpdateRaw=$UpdateRaw; UseExistingData=$UseExistingData; Pdf=$Pdf; Open=$Open }
if ($DateTag) { $params.DateTag = $DateTag }
& (Join-Path $PSScriptRoot 'run_ai_report.ps1') @params
