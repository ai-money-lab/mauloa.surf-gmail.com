#!/bin/bash
# PostToolUse hook: Edit/Write後に変更されたPythonファイルをruffで即チェック
# Claude CodeはJSON形式でhookにデータを渡す（stdin経由）
set -euo pipefail

# Read JSON from stdin (Claude Code passes hook data via stdin)
HOOK_INPUT=$(cat)

# Extract file_path from tool_input JSON
FILE_PATH=$(echo "$HOOK_INPUT" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    tool_input = data.get('tool_input', {})
    print(tool_input.get('file_path', ''))
except Exception:
    pass
" 2>/dev/null)

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# cits配下のPythonファイルのみ対象
case "$FILE_PATH" in
    */cits/*.py)
        ;;
    *)
        exit 0
        ;;
esac

if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# ruff check on the specific file
if ! command -v ruff &>/dev/null; then
    exit 0
fi

ERRORS=$(ruff check "$FILE_PATH" 2>&1) || true
if echo "$ERRORS" | grep -q "error\|^.*\.py:"; then
    echo "⚠️ ruff check 検出 ($FILE_PATH):"
    echo "$ERRORS"
    echo ""
    echo "→ 修正してから次に進んでください"
fi

exit 0
