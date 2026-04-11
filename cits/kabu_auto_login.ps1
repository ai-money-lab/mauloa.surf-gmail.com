# kabuStation Auto-Login Script v3
# Safe restart + login. Runs via Task Scheduler in interactive session.

$kabuPath = "C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe"
$apiPassword = "hiroki0380"
$logFile = "C:\cits\logs\kabu_login.log"

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts $msg" | Out-File -Append -FilePath $logFile -Encoding UTF8
    Write-Host "$ts $msg"
}

# Step 1: Check if API already works
try {
    $body = @{ APIPassword = $apiPassword } | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "http://localhost:18080/kabusapi/token" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 5
    if ($r.Token) {
        Log "API already OK. No action needed."
        exit 0
    }
} catch {
    Log "API not ready. Proceeding with restart+login."
}

# Step 2: Kill kabuStation and restart fresh
Log "Stopping kabuStation..."
Stop-Process -Name "KabuS" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 10

Log "Starting kabuStation..."
Start-Process $kabuPath
Start-Sleep -Seconds 60
Log "Waiting for login window..."

# Step 3: Activate window and enter password
$wsh = New-Object -ComObject WScript.Shell
Start-Sleep -Seconds 5

$names = @("kabu", "KABU", "KabuS")
$activated = $false
foreach ($name in $names) {
    if ($wsh.AppActivate($name)) {
        $activated = $true
        Log "Window activated with name: $name"
        break
    }
}

if ($activated) {
    Start-Sleep -Seconds 3
    # Login window: Tab to password field, type password, Enter
    $wsh.SendKeys("{TAB}")
    Start-Sleep -Milliseconds 500
    $wsh.SendKeys($apiPassword)
    Start-Sleep -Milliseconds 500
    $wsh.SendKeys("{ENTER}")
    Log "Password entered. Waiting 30s for login..."
    Start-Sleep -Seconds 30

    # Handle possible update/dialog popups
    $wsh.SendKeys("{ENTER}")
    Start-Sleep -Seconds 5
} else {
    Log "WARNING: Could not activate any kabuStation window."
}

# Step 4: Verify
$ok = $false
for ($i = 1; $i -le 5; $i++) {
    try {
        $body = @{ APIPassword = $apiPassword } | ConvertTo-Json
        $r = Invoke-RestMethod -Uri "http://localhost:18080/kabusapi/token" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 5
        if ($r.Token) {
            Log "LOGIN SUCCESS on attempt $i."
            $ok = $true
            break
        }
    } catch {
        Log "Verify attempt $i failed."
        Start-Sleep -Seconds 10
    }
}

if (-not $ok) {
    Log "FAILED: Could not login after restart. Needs manual intervention."
    exit 1
}

exit 0
