#!/bin/bash
# PreCommit hook: コミット前にフル検証を実行
set -euo pipefail
cd "$CLAUDE_PROJECT_DIR"

echo "=== PreCommit: フル検証開始 ==="

# 1. ruff check (cits/ 全体)
echo "[1/2] ruff check cits/..."
RUFF_OUT=$(ruff check cits/ 2>&1) || true
if [ -n "$RUFF_OUT" ]; then
    echo "❌ ruff check 失敗:"
    echo "$RUFF_OUT"
    echo ""
    echo "→ コミット中止。lint エラーを修正してください。"
    exit 1
fi
echo "  ✓ ruff check OK"

# 2. smoke_test (import & 基本動作確認)
echo "[2/2] smoke_test..."
if [ -f "cits/tests/smoke_test.py" ]; then
    SMOKE_OUT=$(python -m pytest cits/tests/smoke_test.py -x -q 2>&1) || {
        echo "❌ smoke_test 失敗:"
        echo "$SMOKE_OUT"
        echo ""
        echo "→ コミット中止。テストを修正してください。"
        exit 1
    }
    echo "  ✓ smoke_test OK"
else
    echo "  ⚠ smoke_test.py が見つかりません (スキップ)"
fi

echo "=== PreCommit: 検証完了 ✓ ==="
