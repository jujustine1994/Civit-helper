$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
$pythonPath = Join-Path $env:USERPROFILE 'venvs\CivitHelper\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'CivitHelper Python environment missing.' }
& $pythonPath (Join-Path $projectPath 'app.py') schedule-xml
if ($LASTEXITCODE -ne 0) { throw 'Failed to generate task XML.' }
$xmlPath = Join-Path $projectPath 'runtime\schedule.xml'
[xml]$taskDocument = Get-Content -LiteralPath $xmlPath -Raw
$taskName = 'CivitHelper_Daily'
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    $owned = @($existing.Actions | Where-Object { $_.Arguments -like ('*' + (Join-Path $projectPath 'app.py') + '*') })
    if ($owned.Count -eq 0) { throw 'Task name already exists and belongs to another program. No task changed.' }
}
Register-ScheduledTask -TaskName $taskName -Xml $taskDocument.OuterXml -Force | Out-Null
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State
Get-ScheduledTaskInfo -TaskName $taskName | Select-Object NextRunTime,LastRunTime,LastTaskResult
