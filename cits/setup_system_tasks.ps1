# ================================================================
# CITS Bootstrap -- Re-register all tasks as SYSTEM + start agent
# Run ONCE from VPS web console or PowerShell (Admin):
#   powershell -ExecutionPolicy Bypass -File C:\cits\repo\cits\setup_system_tasks.ps1
# ================================================================

$ErrorActionPreference = "Continue"
$REPO = "C:\cits\repo"
$VENV = "C:\cits\venv\Scripts"

Write-Host "=== CITS Bootstrap $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" -ForegroundColor Cyan

# Pull latest code
Write-Host "`n[1] git pull..." -ForegroundColor Yellow
Set-Location $REPO
& git pull --quiet 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "    git pull OK" -ForegroundColor Green
} else {
    Write-Host "    git pull failed (continuing with existing code)" -ForegroundColor Red
}

# Register all SYSTEM background tasks
Write-Host "`n[2] Registering SYSTEM tasks..." -ForegroundColor Yellow

$tasks = @(
    @{
        name = "CITS_Watchdog"
        args = @("/Create","/TN","CITS_Watchdog","/RU","SYSTEM","/TR","C:\cits\repo\cits\run_watchdog.bat","/SC","MINUTE","/MO","5","/RL","HIGHEST","/F")
    },
    @{
        name = "CITS_VPSAgent"
        args = @("/Create","/TN","CITS_VPSAgent","/RU","SYSTEM","/TR","C:\cits\repo\cits\run_agent.bat","/SC","ONSTART","/DELAY","0002:00","/RL","HIGHEST","/F")
    },
    @{
        name = "CITS_StartupRecovery"
        args = @("/Create","/TN","CITS_StartupRecovery","/RU","SYSTEM","/TR","C:\cits\repo\cits\run_morning.bat","/SC","ONSTART","/DELAY","0005:00","/RL","HIGHEST","/F")
    },
    @{
        name = "CITS_LiveTrader"
        args = @("/Create","/TN","CITS_LiveTrader","/RU","SYSTEM","/TR","C:\cits\repo\cits\run_morning.bat","/SC","DAILY","/ST","08:30","/D","MON,TUE,WED,THU,FRI","/RL","HIGHEST","/F")
    },
    @{
        name = "CITS_PositionMonitor"
        args = @("/Create","/TN","CITS_PositionMonitor","/RU","SYSTEM","/TR","C:\cits\repo\cits\run_monitor.bat","/SC","MINUTE","/MO","30","/ST","09:30","/ET","15:25","/RL","HIGHEST","/F")
    },
    @{
        name = "CITS_Afternoon"
        args = @("/Create","/TN","CITS_Afternoon","/RU","SYSTEM","/TR","C:\cits\repo\cits\run_afternoon.bat","/SC","DAILY","/ST","15:20","/D","MON,TUE,WED,THU,FRI","/RL","HIGHEST","/F")
    },
    @{
        name = "CITS_Prefetch"
        args = @("/Create","/TN","CITS_Prefetch","/RU","SYSTEM","/TR","C:\cits\repo\cits\run_prefetch.bat","/SC","DAILY","/ST","14:00","/D","MON,TUE,WED,THU,FRI","/RL","HIGHEST","/F")
    },
    @{
        name = "CITS_GitRepair"
        args = @("/Create","/TN","CITS_GitRepair","/RU","SYSTEM","/TR","C:\cits\repo\cits\run_gitrepair.bat","/SC","DAILY","/ST","06:00","/D","MON,TUE,WED,THU,FRI","/RL","HIGHEST","/F")
    }
)

# GUI tasks (kabuStation needs interactive desktop -- Administrator, not SYSTEM)
$guiTasks = @(
    @{
        name = "CITS_KabuStart_IT"
        args = @("/Create","/TN","CITS_KabuStart_IT","/RU","Administrator","/TR","C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe","/SC","ONCE","/SD","12/31/2099","/ST","23:59","/IT","/F")
    },
    @{
        name = "CITS_KabuStation_Start"
        args = @("/Create","/TN","CITS_KabuStation_Start","/RU","Administrator","/TR","C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe","/SC","DAILY","/ST","08:25","/D","MON,TUE,WED,THU,FRI","/IT","/F")
    }
)

foreach ($t in $tasks) {
    $r = & schtasks @($t.args) 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    $($t.name): OK (SYSTEM)" -ForegroundColor Green
    } else {
        Write-Host "    $($t.name): FAILED -- $r" -ForegroundColor Red
    }
}

foreach ($t in $guiTasks) {
    $r = & schtasks @($t.args) 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    $($t.name): OK (Administrator/IT)" -ForegroundColor Green
    } else {
        Write-Host "    $($t.name): FAILED -- $r" -ForegroundColor Red
    }
}

# Stop any stale Python processes
Write-Host "`n[3] Stopping stale Python processes..." -ForegroundColor Yellow
& taskkill /F /IM pythonw.exe 2>$null
& taskkill /F /IM python.exe 2>$null
Start-Sleep -Seconds 2

# Start vps_agent as background process
Write-Host "`n[4] Starting vps_agent..." -ForegroundColor Yellow
$env:PYTHONPATH = $REPO
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "$VENV\pythonw.exe"
$psi.Arguments = "-m cits.scripts.vps_agent"
$psi.WorkingDirectory = $REPO
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$psi.UseShellExecute = $true
$p = [System.Diagnostics.Process]::Start($psi)
if ($p) {
    Write-Host "    vps_agent started (PID $($p.Id))" -ForegroundColor Green
} else {
    Write-Host "    vps_agent start FAILED" -ForegroundColor Red
}

# Run watchdog once immediately
Write-Host "`n[5] Running watchdog (first run)..." -ForegroundColor Yellow
$env:PYTHONPATH = $REPO
& "$VENV\python.exe" -m cits.scripts.watchdog
Write-Host "    watchdog first run done" -ForegroundColor Green

# Confirm task registrations
Write-Host "`n[6] Task registration summary:" -ForegroundColor Yellow
& schtasks /Query /FO CSV /NH 2>$null | Select-String "CITS" | ForEach-Object { Write-Host "    $_" }

Write-Host "`n=== Bootstrap COMPLETE ===" -ForegroundColor Cyan
Write-Host "vps_agent is running in the background." -ForegroundColor Green
Write-Host "CITS_Watchdog will run every 5 min as SYSTEM (persists after logoff)." -ForegroundColor Green
Write-Host "No further manual action required." -ForegroundColor Green
