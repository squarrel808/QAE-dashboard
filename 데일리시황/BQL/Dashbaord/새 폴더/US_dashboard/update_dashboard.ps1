[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$dashboardDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$dashboardRoot = Split-Path -Parent $dashboardDir
$bqlDir = Split-Path -Parent $dashboardRoot
$builder = Join-Path $dashboardRoot 'build_regional_dashboards.py'
$master = Join-Path $bqlDir 'Rawfile\BQuant_Master.xlsx'

python $builder --region us $master
if ($LASTEXITCODE -ne 0) { throw "US dashboard build failed with exit code $LASTEXITCODE" }
