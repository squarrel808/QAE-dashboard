[CmdletBinding()]
param(
    [ValidateSet('1D','1W','1M3M','ALL')]
    [string]$Period = 'ALL',

    [ValidatePattern('^\d{8}$')]
    [string]$DateTag,

    [switch]$UpdateRaw,
    [switch]$UseExistingData,
    [switch]$Pdf,
    [switch]$Open
)

$ErrorActionPreference = 'Stop'

$aiRoot = $PSScriptRoot
$materialRoot = (Resolve-Path (Join-Path $aiRoot '..')).Path
$themeRoot = (Resolve-Path (Join-Path $materialRoot '..')).Path
$bqlRoot = (Resolve-Path (Join-Path $themeRoot '..')).Path
$datasetScript = Join-Path $materialRoot 'build_report_datasets.py'
$rawUpdater = Join-Path $bqlRoot 'Rawfile\update_all.ps1'
$generator = Join-Path $aiRoot 'generate_ai_period_report.js'
$outputRoot = Join-Path $themeRoot 'output'
$master = Join-Path $bqlRoot 'Rawfile\BQuant_Master.xlsx'

foreach ($requiredPath in @($datasetScript, $generator, $master)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "필수 파일을 찾을 수 없습니다: $requiredPath"
    }
}

if ($UpdateRaw) {
    if (-not (Test-Path -LiteralPath $rawUpdater)) {
        throw "원자료 갱신 실행 파일을 찾을 수 없습니다: $rawUpdater"
    }
    Write-Host '[1/3] Daily_Input을 기존 BQL Rawfile Master에 병합합니다.' -ForegroundColor Cyan
    & $rawUpdater
    if (-not $?) { throw 'BQuant Master 갱신에 실패했습니다.' }
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) { throw 'python 실행 파일을 찾을 수 없습니다.' }

$json = $null
if (-not $UseExistingData) {
    Write-Host '[2/3] 최신 유효 거래일 기준 계산 데이터를 날짜별 Material 폴더에 만듭니다.' -ForegroundColor Cyan
    $datasetOutput = @(
        & $pythonCommand.Source $datasetScript --ai-only --master $master --material-root $materialRoot
    )
    if ($LASTEXITCODE -ne 0) { throw "AI 계산 데이터 생성 실패: exit code $LASTEXITCODE" }

    $latestDataPointer = Join-Path $aiRoot 'latest_data.json'
    if (-not (Test-Path -LiteralPath $latestDataPointer -PathType Leaf)) {
        throw "AI latest data pointer가 생성되지 않았습니다: $latestDataPointer"
    }
    $pointer = Get-Content -LiteralPath $latestDataPointer -Raw | ConvertFrom-Json
    $jsonPath = [string]$pointer.json
    $json = Get-Item -LiteralPath $jsonPath -ErrorAction Stop
} else {
    if ($DateTag) {
        $datasetDir = Join-Path $aiRoot $DateTag
    } else {
        $latestDateDir = Get-ChildItem -LiteralPath $aiRoot -Directory |
            Where-Object { $_.Name -match '^\d{8}$' } |
            Sort-Object Name -Descending |
            Select-Object -First 1
        if (-not $latestDateDir) {
            throw "날짜별 AI 계산 데이터 폴더가 없습니다: $aiRoot"
        }
        $datasetDir = $latestDateDir.FullName
    }

    $json = Get-ChildItem -LiteralPath $datasetDir -Filter 'US_AI_Value_Chain_Data_*.json' -File |
        Sort-Object Name -Descending |
        Select-Object -First 1
    if (-not $json) { throw "AI 계산 JSON이 없습니다: $datasetDir" }
}

$dataMeta = Get-Content -Raw -LiteralPath $json.FullName | ConvertFrom-Json
$asOf = [string]$dataMeta.meta.asOf
$dataDateTag = $asOf.Replace('-', '')
if ($dataDateTag -notmatch '^\d{8}$') {
    throw "AI 계산 JSON의 meta.asOf 값이 올바르지 않습니다: $asOf"
}
if ($DateTag -and $DateTag -ne $dataDateTag) {
    throw "요청 날짜($DateTag)와 계산 JSON 기준일($dataDateTag)이 다릅니다: $($json.FullName)"
}

$outputDateDir = Join-Path $outputRoot $dataDateTag
foreach ($category in @('AI', 'Sector_Industry', 'Top10_Down10')) {
    New-Item -ItemType Directory -Path (Join-Path $outputDateDir $category) -Force | Out-Null
}
$outputDir = Join-Path $outputDateDir 'AI'

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
Write-Host '[3/3] 날짜별 output/AI 폴더에 Word 보고서를 생성합니다.' -ForegroundColor Cyan
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

Write-Host "계산 자료: $($json.Directory.FullName)" -ForegroundColor DarkGray
Write-Host "최종 결과: $outputDir" -ForegroundColor DarkGray
Write-Output $created
