#!/bin/bash
# PreCommit hook: コミット前にフル検証を実行
set -eo pipefail

# CLAUDE_PROJECT_DIR is set when invoked from Claude Code
# When invoked as git hook, determine the project dir from git
if [ -z "${CLAUDE_PROJECT_DIR:-}" ]; then
    CLAUDE_PROJECT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
fi
cd "$CLAUDE_PROJECT_DIR"

echo "=== PreCommit: フル検証開始 ==="

# 1. ruff check (cits/ 全体)
echo "[1/2] ruff check cits/..."
if ! RUFF_OUT=$(ruff check cits/ 2>&1); then
    echo "❌ ruff check 失敗:"
    echo "$RUFF_OUT"
    echo ""
    echo "→ コミット中止。lint エラーを修正してください。"
    exit 1
fi
echo "  ✓ ruff check OK"

# 2. smoke_test (import & 基本動作確認) -- direct execution, not pytest
echo "[2/2] smoke_test..."
if [ -f "cits/tests/smoke_test.py" ]; then
    if ! SMOKE_OUT=$(python cits/tests/smoke_test.py 2>&1); then
        echo "❌ smoke_test 失敗:"
        echo "$SMOKE_OUT" | tail -20
        echo ""
        echo "→ コミット中止。テストを修正してください。"
        exit 1
    fi
    echo "  ✓ smoke_test OK"
else
    echo "  ⚠ smoke_test.py が見つかりません (スキップ)"
fi

echo "=== PreCommit: 検証完了 ✓ ==="
