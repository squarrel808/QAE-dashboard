param(
    [ValidateSet("ALL", "STOXX600", "TOPIX")]
    [string]$Market = "ALL",
    [switch]$UpdateRaw,
    [switch]$Pdf,
    [switch]$Open
)

$ErrorActionPreference = "Stop"

$reportDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$bqlDir = (Resolve-Path (Join-Path $reportDir "..\..\..\..")).Path
$themeDir = Join-Path $bqlDir "Theme"
$master = Join-Path $bqlDir "Rawfile\BQuant_Master.xlsx"
$outputRoot = Join-Path $themeDir "output"
$materialRoot = Join-Path $themeDir "Material\Sector_Industry"

$runtimeRoot = "C:\Users\infomax\.cache\codex-runtimes\codex-primary-runtime\dependencies"
$python = Join-Path $runtimeRoot "python\python.exe"
$node = Join-Path $runtimeRoot "node\bin\node.exe"
$nodeModules = Join-Path $runtimeRoot "node\node_modules"

if (-not (Test-Path -LiteralPath $python)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}
if (-not (Test-Path -LiteralPath $node)) {
    $node = (Get-Command node -ErrorAction Stop).Source
}
if (Test-Path -LiteralPath $nodeModules) {
    $env:NODE_PATH = $nodeModules
}

if ($UpdateRaw) {
    $updateScript = Join-Path $bqlDir "Rawfile\update_all.ps1"
    & $updateScript
}

if (-not (Test-Path -LiteralPath $master)) {
    throw "BQuant Master workbook not found: $master"
}

$builder = Join-Path $reportDir "build_sector_industry_5d.py"
$generator = Join-Path $reportDir "generate_sector_industry_report.js"

$builderOutput = @(& $python $builder --master $master --output-root $outputRoot --material-root $materialRoot --market $Market --top-n 8)
if ($LASTEXITCODE -ne 0) {
    throw "Dataset build failed."
}
$jsonPath = [string]($builderOutput | Select-Object -Last 1)
if (-not (Test-Path -LiteralPath $jsonPath -PathType Leaf)) {
    throw "Calculation JSON was not created: $jsonPath"
}
$dataDir = Split-Path -Parent $jsonPath
$dateDir = Split-Path -Parent $dataDir
$dateTag = Split-Path -Leaf $dateDir
if ($dateTag -notmatch '^\d{8}$') {
    throw "Unexpected calculation date folder: $dateDir"
}
$outputDir = Join-Path (Join-Path $outputRoot $dateTag) "Sector_Industry"
foreach ($category in @("AI", "Sector_Industry", "Top10_Down10")) {
    New-Item -ItemType Directory -Path (Join-Path (Join-Path $outputRoot $dateTag) $category) -Force | Out-Null
}

$targets = if ($Market -eq "ALL") { @("STOXX600", "TOPIX") } else { @($Market) }
$documents = @()
foreach ($target in $targets) {
    & $node $generator --data $jsonPath --market $target --output-dir $outputDir
    if ($LASTEXITCODE -ne 0) {
        throw "DOCX generation failed for $target."
    }
    $documentFile = Get-ChildItem -LiteralPath (Join-Path $outputDir $target) -Filter "*.docx" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $documentFile) {
        throw "DOCX was not created in: $(Join-Path $outputDir $target)"
    }
    $documentPath = $documentFile.FullName
    $documents += $documentPath
}

if ($Pdf) {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    try {
        foreach ($documentPath in $documents) {
            $doc = $word.Documents.Open($documentPath, $false, $true)
            try {
                $pdfPath = [IO.Path]::ChangeExtension($documentPath, ".pdf")
                $doc.SaveAs([ref]$pdfPath, [ref]17)
            }
            finally {
                $doc.Close($false)
                [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc)
            }
        }
    }
    finally {
        $word.Quit()
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
        [GC]::Collect()
        [GC]::WaitForPendingFinalizers()
    }
}

if ($Open) {
    foreach ($documentPath in $documents) {
        Invoke-Item -LiteralPath $documentPath
    }
}

Write-Host "Calculation data: $jsonPath"
foreach ($documentPath in $documents) {
    Write-Host "Report: $documentPath"
}
