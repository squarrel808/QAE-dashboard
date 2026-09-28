[CmdletBinding()]
param(
    [ValidateSet('1D','1W','1M3M','ALL')]
    [string]$Period = 'ALL',
    [switch]$UpdateRaw,
    [switch]$UseExistingData,
    [switch]$Pdf,
    [switch]$Open
)

$ErrorActionPreference = 'Stop'
$reportsRoot = $PSScriptRoot
$bqlRoot = (Resolve-Path (Join-Path $reportsRoot '..\..\..')).Path
$datasetScript = Join-Path $bqlRoot 'Theme\output\build_report_datasets.py'
$datasetDir = Join-Path $bqlRoot 'Theme\output\AI_Rotation'
$rawUpdater = Join-Path $bqlRoot 'Rawfile\update_all.ps1'
$generator = Join-Path $reportsRoot 'generate_ai_period_report.js'
$outputDir = Join-Path $reportsRoot 'output'

if ($UpdateRaw) {
    Write-Host '[1/3] Daily_Input을 Master에 병합합니다.' -ForegroundColor Cyan
    & $rawUpdater
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) { throw 'python 실행 파일을 찾을 수 없습니다.' }

if (-not $UseExistingData) {
    Write-Host '[2/3] 최신 유효 거래일 기준 1D·1W·1M·3M 계산 데이터를 만듭니다.' -ForegroundColor Cyan
    & $pythonCommand.Source $datasetScript --ai-only
}

$json = Get-ChildItem -LiteralPath $datasetDir -Filter 'US_AI_Value_Chain_Data_*.json' -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $json) { throw "AI 계산 JSON이 없습니다: $datasetDir" }

$bundledNode = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
$bundledModules = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
if (Test-Path -LiteralPath $bundledNode) {
    $node = $bundledNode
    if (Test-Path -LiteralPath $bundledModules) { $env:NODE_PATH = $bundledModules }
} else {
    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
    if (-not $nodeCommand) { throw 'node 실행 파일을 찾을 수 없습니다.' }
    $node = $nodeCommand.Source
}

$periods = if ($Period -eq 'ALL') { @('1D','1W','1M3M') } else { @($Period) }
$created = @()
Write-Host '[3/3] Word 보고서를 생성합니다.' -ForegroundColor Cyan
foreach ($item in $periods) {
    $result = & $node $generator --data $json.FullName --period $item --output-dir $outputDir
    if ($LASTEXITCODE -ne 0) { throw "$item 보고서 생성 실패" }
    $reportPath = ($result | Select-Object -Last 1).Trim()
    $created += $reportPath
    Write-Host "완료: $reportPath" -ForegroundColor Green
    if ($Pdf) {
        $pdfPath = [System.IO.Path]::ChangeExtension($reportPath, '.pdf')
        $word = New-Object -ComObject Word.Application
        $word.Visible = $false
        $word.DisplayAlerts = 0
        try {
            $document = $word.Documents.Open($reportPath, $false, $true)
            $document.ExportAsFixedFormat($pdfPath, 17)
            $document.Close(0)
        } finally {
            $word.Quit()
            [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
        }
        $created += $pdfPath
        Write-Host "PDF 완료: $pdfPath" -ForegroundColor Green
    }
    if ($Open) { Start-Process -FilePath $reportPath }
}

Write-Output $created
