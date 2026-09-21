$ErrorActionPreference = 'Stop'
$taskName = 'QAE Vercel 2300'
$workspace = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$batch = Join-Path $PSScriptRoot 'run_vercel_2300.bat'
if (-not (Test-Path -LiteralPath $batch)) { throw 'Nightly batch missing' }
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    $backup = Join-Path $workspace ('logs\vercel-task-before-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.xml')
    Export-ScheduledTask -TaskName $taskName | Set-Content -LiteralPath $backup -Encoding Unicode
}
$pythonPath = 'C:\Users\infomax\AppData\Local\Programs\Python\Python313\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Python runtime missing' }
# 직접 실행해야 작업 종료/시간 제한 시 BAT 아래 Python이 고아 프로세스로 남지 않는다.
$action = New-ScheduledTaskAction -Execute $pythonPath `
    -Argument ('-X utf8 -u "' + (Join-Path $workspace 'run_qae.py') + '" /nightly /nohouseviews /dataonly') -WorkingDirectory $workspace
$trigger = New-ScheduledTaskTrigger -Daily -At '23:00'
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal `
    -Settings $settings -Description 'QAE saved report summaries and web data -> GitHub -> verify live Vercel site, daily 23:00 KST.' -Force | Out-Null
$task = Get-ScheduledTask -TaskName $taskName
$info = $task | Get-ScheduledTaskInfo
[pscustomobject]@{Name=$task.TaskName; State=[string]$task.State; NextRun=$info.NextRunTime;
    Execute=$task.Actions.Execute; Arguments=$task.Actions.Arguments;
    WorkingDirectory=$task.Actions.WorkingDirectory; StartBoundary=$task.Triggers.StartBoundary;
    StartWhenAvailable=$task.Settings.StartWhenAvailable; LogonType=[string]$task.Principal.LogonType} | ConvertTo-Json
