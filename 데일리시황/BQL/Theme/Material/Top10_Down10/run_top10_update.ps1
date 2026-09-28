[CmdletBinding()]
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$SourceFiles,
    [Parameter()]
    [string]$BqlRoot,
    [Parameter()]
    [string]$OutputRoot,
    [Parameter()]
    [string]$MaterialOutputRoot
)

$ErrorActionPreference = 'Stop'

function Write-JsonAtomic {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [object]$Value
    )
    $temporary = "$Path.tmp"
    $json = $Value | ConvertTo-Json -Depth 20
    [IO.File]::WriteAllText(
        $temporary,
        $json + [Environment]::NewLine,
        [Text.UTF8Encoding]::new($false)
    )
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Installed location: BQL\Theme\Material\Top10_Down10.
$bqlDir = if ($BqlRoot) {
    (Resolve-Path -LiteralPath $BqlRoot).Path
} else {
    (Resolve-Path (Join-Path $scriptDir '..\..\..')).Path
}
$materialRoot = if ($MaterialOutputRoot) {
    [IO.Path]::GetFullPath($MaterialOutputRoot)
} else {
    $scriptDir
}
$publishRoot = if ($OutputRoot) {
    [IO.Path]::GetFullPath($OutputRoot)
} else {
    Join-Path $bqlDir 'Theme\output'
}
# The installed scripts derive BQL from their own location. Avoid relaying the
# Korean filesystem path through an environment variable, which can be decoded
# with the wrong console code page on some Windows hosts.
Remove-Item Env:BQL_THEME_ROOT -ErrorAction SilentlyContinue
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

$computeArguments = @(
    (Join-Path $scriptDir 'compute_10d_rankings.py')
)
if ($SourceFiles) {
    $computeArguments += $SourceFiles
}
$computeArguments += @('--material-root', $materialRoot)

& $pythonCommand.Source @computeArguments
if ($LASTEXITCODE -ne 0) {
    throw "Top10/Down10 calculation failed with exit code $LASTEXITCODE"
}

$latestRanking = Join-Path $materialRoot 'Market_10D_Rankings_latest.json'
if (-not (Test-Path -LiteralPath $latestRanking)) {
    throw "Ranking pointer was not created: $latestRanking"
}
$rankingData = Get-Content -LiteralPath $latestRanking -Raw -Encoding UTF8 | ConvertFrom-Json
$asOf = @($rankingData.SPX.latest, $rankingData.SHSZ300.latest, $rankingData.SXXP.latest) |
    Sort-Object -Descending |
    Select-Object -First 1
$tag = ([string]$asOf).Replace('-', '')
if ($tag -notmatch '^\d{8}$') {
    throw "Invalid as-of date in ranking JSON: $asOf"
}

$materialDateDir = Join-Path $materialRoot $tag
$datedRanking = Join-Path $materialDateDir "Market_10D_Rankings_$tag.json"
$publishDateDir = Join-Path $publishRoot $tag
foreach ($category in @('AI', 'Sector_Industry', 'Top10_Down10')) {
    New-Item -ItemType Directory -Path (Join-Path $publishDateDir $category) -Force | Out-Null
}
$publishDir = Join-Path $publishDateDir 'Top10_Down10'
if (-not (Test-Path -LiteralPath $datedRanking)) {
    throw "Dated ranking JSON was not created: $datedRanking"
}

& $pythonCommand.Source (Join-Path $scriptDir 'build_market_10d_outputs.py') `
    --data $datedRanking `
    --material-root $materialRoot `
    --material-dir $materialDateDir `
    --publish-root $publishRoot `
    --publish-dir $publishDir
if ($LASTEXITCODE -ne 0) {
    throw "Top10/Down10 workbook build failed with exit code $LASTEXITCODE"
}

$datedManifest = Join-Path $materialDateDir 'manifest.json'
if (-not (Test-Path -LiteralPath $datedManifest)) {
    throw "Dated manifest was not created: $datedManifest"
}
$manifest = Get-Content -LiteralPath $datedManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$wordGenerated = $false

if ($nodeExecutable) {
    & $nodeExecutable `
        (Join-Path $scriptDir 'build_market_10d_report.js') `
        $manifest.datedEnriched `
        $manifest.docx `
        $manifest.chartDir
    if ($LASTEXITCODE -ne 0) {
        throw "Top10/Down10 Word report build failed with exit code $LASTEXITCODE"
    }
    if (-not (Test-Path -LiteralPath $manifest.docx)) {
        throw "Word report was not created: $($manifest.docx)"
    }
    $wordGenerated = $true
} else {
    Write-Warning 'Node.js를 찾지 못해 Word 보고서는 건너뛰었습니다. JSON, 차트, Excel은 생성됐습니다.'
}

& $pythonCommand.Source `
    (Join-Path $scriptDir 'validate_market_10d_workbook.py') `
    $manifest.workbook `
    --manifest $datedManifest
if ($LASTEXITCODE -ne 0) {
    throw "Top10/Down10 workbook validation failed with exit code $LASTEXITCODE"
}

$manifest | Add-Member -NotePropertyName status -NotePropertyValue $(if ($wordGenerated) { 'complete' } else { 'partial' }) -Force
$manifest | Add-Member -NotePropertyName workbookValidated -NotePropertyValue $true -Force
$manifest | Add-Member -NotePropertyName wordGenerated -NotePropertyValue $wordGenerated -Force
$manifest | Add-Member -NotePropertyName completedAt -NotePropertyValue (Get-Date).ToString('o') -Force
Write-JsonAtomic -Path $datedManifest -Value $manifest
$latestManifest = Join-Path $materialRoot 'latest_outputs.json'
Write-JsonAtomic -Path $latestManifest -Value $manifest

Write-Host "완료: $latestManifest"
Write-Host "계산·차트: $materialDateDir"
Write-Host "최종 산출물: $publishDir"
