$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$pythonPath = 'C:\Users\infomax\AppData\Local\Programs\Python\Python313\python.exe'
foreach ($name in @('QAE대시보드갱신','QAE Vercel 2300')) {
    $task = Get-ScheduledTask -TaskName $name
    $backup = Join-Path $workspace ('logs\' + $name + '-before-modules-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.xml')
    Export-ScheduledTask -TaskName $name | Set-Content -LiteralPath $backup -Encoding Unicode
    $action = New-ScheduledTaskAction -Execute $pythonPath -Argument ('-X utf8 -u "' + (Join-Path $workspace 'run_qae.py') + '" /scheduled') -WorkingDirectory $workspace
    $settings = $task.Settings
    $settings.StartWhenAvailable = $true
    Set-ScheduledTask -TaskName $name -Action $action -Settings $settings | Out-Null
    $updated = Get-ScheduledTask -TaskName $name
    $info = $updated | Get-ScheduledTaskInfo
    [pscustomobject]@{Name=$name; Arguments=$updated.Actions.Arguments; NextRun=$info.NextRunTime; StartWhenAvailable=$updated.Settings.StartWhenAvailable; State=[string]$updated.State}
}
# Upstream collection tasks retain their existing settings and owner permissions.
