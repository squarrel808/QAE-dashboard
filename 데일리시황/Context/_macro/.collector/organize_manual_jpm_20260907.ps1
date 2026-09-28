$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskOutput = Join-Path $taskRoot 'outdated\JPM'
$taskRows = Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'manual_jpm_20260907.tsv') -Delimiter "`t" -Encoding UTF8
New-Item -ItemType Directory -Path $taskOutput -Force | Out-Null
$taskResults = foreach ($taskRow in $taskRows) {
    $taskSource = Join-Path 'C:\Users\infomax\Downloads' ($taskRow.id + '.pdf')
    $taskTitle = ($taskRow.title -replace '[<>:"/\\|?*\x00-\x1f]', '_') -replace '\s+', ' '
    if ($taskTitle.Length -gt 100) { $taskTitle = $taskTitle.Substring(0, 100) }
    $taskFilename = $taskRow.publication_date + '_' + $taskTitle.Trim().TrimEnd('.') + '__' + $taskRow.id + '.pdf'
    $taskDestination = Join-Path $taskOutput $taskFilename
    $taskBytes = [IO.File]::ReadAllBytes($taskSource)
    if ($taskBytes.Length -lt 1024 -or [Text.Encoding]::ASCII.GetString($taskBytes, 0, 5) -ne '%PDF-') { throw "Invalid PDF header: $taskSource" }
    $taskTailOffset = [Math]::Max(0, $taskBytes.Length - 4096)
    if (-not [Text.Encoding]::ASCII.GetString($taskBytes, $taskTailOffset, $taskBytes.Length - $taskTailOffset).Contains('%%EOF')) { throw "Missing PDF EOF: $taskSource" }
    $taskHash = (Get-FileHash -LiteralPath $taskSource -Algorithm SHA256).Hash
    if (Test-Path -LiteralPath $taskDestination) {
        if ((Get-FileHash -LiteralPath $taskDestination -Algorithm SHA256).Hash -ne $taskHash) { throw "Different file exists: $taskDestination" }
        $taskStatus = 'verified_existing'
    } else {
        [IO.File]::Copy($taskSource, $taskDestination, $false)
        $taskStatus = 'downloaded'
    }
    if ((Get-FileHash -LiteralPath $taskDestination -Algorithm SHA256).Hash -ne $taskHash) { throw "Copy checksum mismatch: $taskDestination" }
    [pscustomobject]@{
        house = 'JPM'; id = $taskRow.id; publication_date = $taskRow.publication_date
        title = $taskRow.title; source_url = ('https://markets.jpmorgan.com/research/content/' + $taskRow.id)
        original_download = $taskSource; saved_path = $taskDestination
        bytes = $taskBytes.Length; sha256 = $taskHash; status = $taskStatus
    }
}
$taskManifest = Join-Path $PSScriptRoot 'manual_jpm_20260907_manifest.csv'
$taskResults | Export-Csv -LiteralPath $taskManifest -NoTypeInformation -Encoding UTF8
[pscustomobject]@{ count = @($taskResults).Count; bytes = ($taskResults | Measure-Object -Property bytes -Sum).Sum; output = $taskOutput; manifest = $taskManifest; statuses = @($taskResults | Group-Object status | Select-Object Name,Count) } | ConvertTo-Json -Depth 4
