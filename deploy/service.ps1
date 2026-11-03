# Run bot as a Windows scheduled task (starts at boot, restarts on crash).
# Usage (PowerShell as Administrator, from anywhere):
#   .\deploy\service.ps1 install | update | start | stop | status | remove
param([Parameter(Mandatory)][ValidateSet("install","update","start","stop","status","remove")][string]$Action)

$Name = "dota-coach"
$Root = Split-Path $PSScriptRoot -Parent
$Py   = Join-Path $Root ".venv\Scripts\python.exe"

switch ($Action) {
  "install" {
    if (-not (Test-Path $Py))               { throw "No .venv. Run: py -3.12 -m venv .venv; .venv\Scripts\pip install -e ." }
    if (-not (Test-Path (Join-Path $Root ".env"))) { throw "No .env in $Root" }
    New-Item -ItemType Directory -Force (Join-Path $Root "logs") | Out-Null
    $run = Register-ScheduledTask -TaskName $Name -Force `
      -Action (New-ScheduledTaskAction -Execute "cmd.exe" -WorkingDirectory $Root `
        -Argument "/c `"$Py`" -m dota_coach.bot >> logs\bot.log 2>&1") `
      -Trigger (New-ScheduledTaskTrigger -AtStartup) `
      -Principal (New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited) `
      -Settings (New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew -StartWhenAvailable)
    Start-ScheduledTask $Name
    "Installed and started. Logs: $Root\logs\bot.log"
  }
  "update" {
    Stop-ScheduledTask $Name -ErrorAction SilentlyContinue
    git -C $Root pull --ff-only
    & $Py -m pip install -q -e $Root
    Start-ScheduledTask $Name
    "Updated and restarted."
  }
  "start"  { Start-ScheduledTask $Name }
  "stop"   { Stop-ScheduledTask $Name }
  "status" { (Get-ScheduledTask $Name).State; Get-Content (Join-Path $Root "logs\bot.log") -Tail 15 -ErrorAction SilentlyContinue }
  "remove" { Stop-ScheduledTask $Name -ErrorAction SilentlyContinue; Unregister-ScheduledTask $Name -Confirm:$false }
}
