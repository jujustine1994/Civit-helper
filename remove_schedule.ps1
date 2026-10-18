$ErrorActionPreference = 'Stop'
$task = Get-ScheduledTask -TaskName 'CivitHelper_Daily' -ErrorAction SilentlyContinue
if ($task) {
    $expectedPath = Join-Path $PSScriptRoot 'app.py'
    $owned = @($task.Actions | Where-Object { $_.Arguments -like ('*' + $expectedPath + '*') })
    if ($owned.Count -eq 0) { throw 'Task belongs to another program. No task changed.' }
    Unregister-ScheduledTask -TaskName 'CivitHelper_Daily' -Confirm:$false
}
