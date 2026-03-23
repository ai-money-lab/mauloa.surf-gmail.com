#!/bin/bash
set -euo pipefail

# Web環境（Claude Code on the web）のみで実行
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "=== SessionStart: 依存パッケージをインストール ==="

# Python依存パッケージ
echo "[1/3] pip install..."
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

echo "=== SessionStart: 完了 ==="
