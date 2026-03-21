# ═══════════════════════════════════════════════════════════
# Riena LoRA Training Pipeline — Windows PowerShell版
#
# 使い方:
#   1. このファイルをローカルにコピー
#   2. PowerShellで実行:
#      .\run_lora_pipeline_windows.ps1
#
# 前提:
#   - Python 3.10+ インストール済み
#   - pip install requests python-dotenv
#   - .env に GEMINI_API_KEY または FAL_API_KEY を設定済み
# ═══════════════════════════════════════════════════════════

# ─── UTF-8出力設定（文字化け防止） ───
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

$ErrorActionPreference = "Stop"

# ─── Pythonコマンド検出（Windowsではpython、Linux/macではpython3） ───
$PythonCmd = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } elseif (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { Write-Host "ERROR: Python が見つかりません。Python 3.10+ をインストールしてください。" -ForegroundColor Red; exit 1 }
Write-Host "Python: $PythonCmd ($(& $PythonCmd --version 2>&1))" -ForegroundColor Gray

# ─── プロジェクトルートに移動 ───
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $ProjectRoot
Write-Host "Project root: $ProjectRoot" -ForegroundColor Cyan

# ─── .envファイル読み込み ───
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^([^#][^=]+)=(.+)$") {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
    Write-Host ".env loaded" -ForegroundColor Green
}

# ─── API Key確認 ───
$geminiKey = [Environment]::GetEnvironmentVariable("GEMINI_API_KEY", "Process")
$falKey = [Environment]::GetEnvironmentVariable("FAL_API_KEY", "Process")
$runpodKey = [Environment]::GetEnvironmentVariable("RUNPOD_API_KEY", "Process")
$podId = [Environment]::GetEnvironmentVariable("RUNPOD_POD_ID", "Process")

Write-Host ""
Write-Host "=== API Keys ===" -ForegroundColor Yellow
Write-Host "GEMINI_API_KEY: $(if ($geminiKey) { 'SET' } else { 'NOT SET' })"
Write-Host "FAL_API_KEY:    $(if ($falKey) { 'SET' } else { 'NOT SET' })"
Write-Host "RUNPOD_API_KEY: $(if ($runpodKey) { 'SET' } else { 'NOT SET' })"
Write-Host "RUNPOD_POD_ID:  $(if ($podId) { $podId } else { 'NOT SET' })"
Write-Host ""

# ─── バックエンド選択 ───
Write-Host "=== バックエンド選択 ===" -ForegroundColor Yellow
Write-Host "1. RunPod ComfyUI Pod (Pod起動中のみ)"
Write-Host "2. Gemini Imagen API"
Write-Host "3. FAL.ai Flux Pro"
Write-Host "4. ドライラン (プロンプト確認のみ)"
$choice = Read-Host "選択 (1-4)"

$backendFlag = switch ($choice) {
    "1" { "--runpod" }
    "2" { "" }  # default = Imagen
    "3" { "--fal" }
    "4" { "--dry-run" }
    default { "--runpod" }
}

# ─── 全シーン定義 ───
$scenes = @(
    "portrait_warm",
    "selfie_natural",
    "workout_power",
    "bikini_pool",
    "evening_intimate",
    "tokyo_golden",
    "lora_front_neutral",
    "lora_threequarter_left",
    "lora_threequarter_right",
    "lora_profile_left",
    "lora_full_body_casual",
    "lora_full_body_dress",
    "lora_bikini_beach",
    "lora_gym_mirror",
    "lora_seated_cafe",
    "lora_back_view_sporty"
)

$countPerScene = 2

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Riena LoRA Training Images — Batch Generator" -ForegroundColor Cyan
Write-Host "  Scenes: $($scenes.Count)" -ForegroundColor Cyan
Write-Host "  Count per scene: $countPerScene" -ForegroundColor Cyan
Write-Host "  Total expected: $($scenes.Count * $countPerScene) images" -ForegroundColor Cyan
Write-Host "  Backend: $backendFlag" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

$totalOk = 0
$totalFail = 0

foreach ($scene in $scenes) {
    Write-Host "--- Generating: $scene ($countPerScene images) ---" -ForegroundColor Yellow

    $args = @("system_e/generate_riena_face.py", "--scene", $scene, "--count", $countPerScene)
    if ($backendFlag -eq "--dry-run") {
        $args = @("system_e/generate_riena_face.py", "--dry-run", "--scene", $scene)
    } elseif ($backendFlag) {
        $args += $backendFlag
    }

    try {
        & $PythonCmd @args
        if ($LASTEXITCODE -eq 0) { $totalOk++ } else { $totalFail++ }
    } catch {
        Write-Host "  Error: $_" -ForegroundColor Red
        $totalFail++
    }

    # Rate limit対策
    if ($backendFlag -ne "--dry-run") {
        Start-Sleep -Seconds 3
    }
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  DONE" -ForegroundColor Green
Write-Host "  OK: $totalOk scenes" -ForegroundColor Green
Write-Host "  Failed: $totalFail scenes" -ForegroundColor Red
Write-Host "  Images in: data\system_e\images\" -ForegroundColor Green
Write-Host ""
Write-Host "  === 次のステップ ===" -ForegroundColor Yellow
Write-Host "  1. data\system_e\images\ の画像を確認、悪いものは削除"
Write-Host "  2. 良い画像を data\system_e\lora_training\images\ に移動:"
Write-Host "     Move-Item data\system_e\images\riena_*.* data\system_e\lora_training\images\"
Write-Host "  3. LoRA学習前処理:"
Write-Host "     python system_e\scripts\train_lora.py prepare"
Write-Host "  4. LoRA学習実行:"
Write-Host "     python system_e\scripts\train_lora.py train"
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
