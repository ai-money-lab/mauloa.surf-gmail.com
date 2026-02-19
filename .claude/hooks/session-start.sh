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

# ruff (linter)
echo "[2/3] ruff install..."
pip install ruff --quiet

# Node.js依存パッケージ（MCP Server用）
echo "[3/3] npm install..."
cd "$CLAUDE_PROJECT_DIR"
npm install --no-fund --no-audit 2>/dev/null || true

# PYTHONPATHをセッションに設定
echo "export PYTHONPATH=\"$CLAUDE_PROJECT_DIR:\${PYTHONPATH:-}\"" >> "$CLAUDE_ENV_FILE"

echo "=== SessionStart: 完了 ==="
