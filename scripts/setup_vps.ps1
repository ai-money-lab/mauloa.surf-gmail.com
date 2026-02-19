# === Windows VPS セットアップスクリプト ===
# PowerShell を「管理者として実行」してから実行してください
#
# 使い方:
#   cd C:\mauloa
#   powershell -ExecutionPolicy Bypass -File scripts\setup_vps.ps1

$ProjectDir = Split-Path -Parent $PSScriptRoot
Write-Host "=== X Auto Post Setup ===" -ForegroundColor Cyan
Write-Host "Project: $ProjectDir"

# --- 1. Python venv ---
Write-Host "`n[1/3] Python venv setup..." -ForegroundColor Yellow
if (-not (Test-Path "$ProjectDir\venv")) {
    python -m venv "$ProjectDir\venv"
}
& "$ProjectDir\venv\Scripts\pip.exe" install -q anthropic requests requests-oauthlib python-dotenv pyyaml gspread google-auth beautifulsoup4 lxml pandas
Write-Host "  Done." -ForegroundColor Green

# --- 2. logs dir ---
Write-Host "`n[2/3] Creating logs directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$ProjectDir\logs" | Out-Null
Write-Host "  Done." -ForegroundColor Green

# --- 3. Task Scheduler ---
Write-Host "`n[3/3] Registering scheduled tasks..." -ForegroundColor Yellow

$BatPath = "$ProjectDir\scripts\x_auto_post.bat"
$TaskTimes = @("07:00", "12:00", "19:00")

foreach ($Time in $TaskTimes) {
    $TaskName = "X_AutoPost_$($Time.Replace(':', ''))"
    $Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatPath`"" -WorkingDirectory $ProjectDir
    $Trigger = New-ScheduledTaskTrigger -Daily -At $Time
    $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd

    # Remove existing task if any
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "X auto post at $Time JST" | Out-Null
    Write-Host "  Registered: $TaskName ($Time JST)" -ForegroundColor Green
}

Write-Host "`n=== Setup Complete ===" -ForegroundColor Cyan
Write-Host @"

Registered tasks:
  - X_AutoPost_0700  (07:00 JST)
  - X_AutoPost_1200  (12:00 JST)
  - X_AutoPost_1900  (19:00 JST)

To verify:
  taskschd.msc  (Task Scheduler GUI)

To test manually:
  scripts\x_auto_post.bat

Logs:
  logs\x_auto_post.log
"@
