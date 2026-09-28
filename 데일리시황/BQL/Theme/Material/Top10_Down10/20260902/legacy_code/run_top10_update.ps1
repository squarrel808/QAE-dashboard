[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$SourceFiles
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$bundledNodeRoot = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node'
$bundledNode = Join-Path $bundledNodeRoot 'bin\node.exe'
$bundledNodeModules = Join-Path $bundledNodeRoot 'node_modules'

$nodeExecutable = if ($nodeCommand) { $nodeCommand.Source } elseif (Test-Path -LiteralPath $bundledNode) { $bundledNode } else { $null }
if (Test-Path -LiteralPath $bundledNodeModules) {
    $env:NODE_PATH = $bundledNodeModules
}

if (-not $pythonCommand) {
    throw 'Python을 찾지 못했습니다. Python 3와 numpy, matplotlib, xlsxwriter, openpyxl을 설치하세요.'
}

& $pythonCommand.Source (Join-Path $scriptDir 'compute_10d_rankings.py') @SourceFiles
if ($LASTEXITCODE -ne 0) {
    throw "Top10/Down10 calculation failed with exit code $LASTEXITCODE"
}

& $pythonCommand.Source (Join-Path $scriptDir 'build_market_10d_outputs.py')
if ($LASTEXITCODE -ne 0) {
    throw "Top10/Down10 workbook build failed with exit code $LASTEXITCODE"
}

if ($nodeExecutable) {
    & $nodeExecutable (Join-Path $scriptDir 'build_market_10d_report.js')
    if ($LASTEXITCODE -ne 0) {
        throw "Top10/Down10 Word report build failed with exit code $LASTEXITCODE"
    }
} else {
    Write-Warning 'Node.js를 찾지 못해 Word 보고서는 건너뛰었습니다. JSON, 차트, Excel은 생성됐습니다.'
}

& $pythonCommand.Source (Join-Path $scriptDir 'validate_market_10d_workbook.py')
if ($LASTEXITCODE -ne 0) {
    throw "Top10/Down10 workbook validation failed with exit code $LASTEXITCODE"
}

$latestManifest = Join-Path $scriptDir 'output\latest_outputs.json'
Write-Host "완료: $latestManifest"
