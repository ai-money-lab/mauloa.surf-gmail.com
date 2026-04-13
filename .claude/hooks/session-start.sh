#!/bin/bash
set -euo pipefail

# Web環境（Claude Code on the web）のみで実行
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "=== SessionStart: 依存パッケージをインストール ==="

# Python依存パッケージ
echo "[1/4] pip install..."
pip install -r "$CLAUDE_PROJECT_DIR/requirements.txt" --quiet

# CITS依存パッケージ (pytest環境にも追加)
echo "[2/4] cits deps install..."
pip install -r "$CLAUDE_PROJECT_DIR/cits/requirements.txt" --quiet 2>/dev/null || true
# pytest が uv tool 管理の場合、依存パッケージを追加
if command -v uv &>/dev/null && uv tool list 2>/dev/null | grep -q pytest; then
  uv tool install pytest --force \
    --with requests --with pandas --with anthropic --with yfinance \
    --with ta --with pyyaml --with beautifulsoup4 --with lxml --with pydantic \
    --quiet 2>/dev/null || true
fi

# ruff (linter)
echo "[3/4] ruff install..."
pip install ruff --quiet

# Node.js依存パッケージ（MCP Server用）
echo "[4/4] npm install..."
cd "$CLAUDE_PROJECT_DIR"
npm install --no-fund --no-audit 2>/dev/null || true

# PYTHONPATHをセッションに設定
echo "export PYTHONPATH=\"$CLAUDE_PROJECT_DIR:\${PYTHONPATH:-}\"" >> "$CLAUDE_ENV_FILE"

# CITS スモークテスト（バックグラウンド検証）
echo "[CITS] スモークテスト実行..."
cd "$CLAUDE_PROJECT_DIR"
python cits/tests/smoke_test.py 2>/dev/null && echo "[CITS] ✅ スモークテスト完了" || echo "[CITS] ⚠ スモークテスト失敗"

echo "=== SessionStart: 完了 ==="

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 【絶対ルール — セッション開始時に必ず読め】
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║      CITS 絶対ルール（2026-04-13制定）               ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║ ① VPS確認 = vps_status.jsonに実行ログが届いた時のみ ║"
echo "║ ② commands.json投入だけでは「完了」と言わない        ║"
echo "║ ③ 第三者が再現できる手順書＋実行ログを必ず提示       ║"
echo "║ ④ 未確認項目を先に列挙してから作業開始               ║"
echo "║ ⑤ 本番前にpaper mode / dry-runで発注テスト必須       ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║ ❌ 「動くはず」「登録されているはず」は禁止           ║"
echo "║ ❌ ログなしの「確認完了」報告は禁止                   ║"
echo "║ ✅ 証拠（実行ログ）を出して初めて「完了」と言える      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# VPS最終応答確認
VPS_STATUS="$CLAUDE_PROJECT_DIR/cits/data/vps_status.json"
if [ -f "$VPS_STATUS" ]; then
  LAST_TS=$(python3 -c "import json; d=json.load(open('$VPS_STATUS')); print(d.get('timestamp','不明'))" 2>/dev/null || echo "読み取り失敗")
  echo "[VPS] 最終応答: $LAST_TS"
  echo "[VPS] ⚠ これが古い場合、vps_agentが停止している可能性あり"
else
  echo "[VPS] ⚠ vps_status.json が見つかりません — VPS状態不明"
fi
echo ""
