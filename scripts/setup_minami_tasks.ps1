# === みなみアカウントのタスクスケジューラ登録 ===
# メインアカウントとは時間をずらして投稿するためのスケジュール設定
# PowerShell を「管理者として実行」してから実行してください
#
# 使い方:
#   cd C:\mauloa
#   powershell -ExecutionPolicy Bypass -File scripts\setup_minami_tasks.ps1

$ProjectDir = Split-Path -Parent $PSScriptRoot
Write-Host "=== みなみアカウント タスク登録 ===" -ForegroundColor Cyan
Write-Host "プロジェクト: $ProjectDir"

# --- 1. Chrome プロファイル確認 ---
Write-Host "`n[1/3] Chrome プロファイル確認..." -ForegroundColor Yellow
$ChromeProfileDir = "$ProjectDir\chrome-profiles\minami"
if (-not (Test-Path $ChromeProfileDir)) {
    Write-Host "  エラー: $ChromeProfileDir が見つかりません" -ForegroundColor Red
    Write-Host "  先に setup_minami_chrome.bat を実行してください" -ForegroundColor Red
    Write-Host "    scripts\setup_minami_chrome.bat" -ForegroundColor Yellow
    exit 1
}
Write-Host "  OK: Chrome プロファイル確認済み" -ForegroundColor Green

# --- 2. logs ディレクトリ作成 ---
Write-Host "`n[2/3] logs ディレクトリ作成..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$ProjectDir\logs" | Out-Null
Write-Host "  完了" -ForegroundColor Green

# --- 3. タスクスケジューラ登録 ---
# メインアカウント: 07:00, 12:00, 19:00
# みなみアカウント: 08:00, 13:00, 20:00 （1時間ずらして重複を回避）
Write-Host "`n[3/3] スケジュールタスク登録..." -ForegroundColor Yellow

$BatPath = "$ProjectDir\scripts\x_auto_post_minami.bat"
$TaskTimes = @("08:00", "13:00", "20:00")

foreach ($Time in $TaskTimes) {
    $TaskName = "Minami_X_AutoPost_$($Time.Replace(':', ''))"
    $Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatPath`"" -WorkingDirectory $ProjectDir
    $Trigger = New-ScheduledTaskTrigger -Daily -At $Time
    $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd

    # 既存タスクがあれば削除
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Minami X auto post at $Time JST" | Out-Null
    Write-Host "  登録完了: $TaskName ($Time JST)" -ForegroundColor Green
}

Write-Host "`n=== セットアップ完了 ===" -ForegroundColor Cyan
Write-Host @"

登録されたタスク:
  - Minami_X_AutoPost_0800  (08:00 JST)
  - Minami_X_AutoPost_1300  (13:00 JST)
  - Minami_X_AutoPost_2000  (20:00 JST)

メインアカウントのスケジュール（参考）:
  - X_AutoPost_0700  (07:00 JST)
  - X_AutoPost_1200  (12:00 JST)
  - X_AutoPost_1900  (19:00 JST)

確認方法:
  taskschd.msc  (タスクスケジューラ GUI)

手動テスト:
  scripts\x_auto_post_minami.bat

ログ:
  logs\x_auto_post_minami.log
"@
