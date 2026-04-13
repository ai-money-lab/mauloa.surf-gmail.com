#!/bin/bash
# PreCommit hook: コミット前にフル検証を実行
set -euo pipefail
cd "$CLAUDE_PROJECT_DIR"

echo "=== PreCommit: フル検証開始 ==="

# 1. ruff check (cits/ 全体)
echo "[1/3] ruff check cits/..."
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
echo "[2/3] smoke_test..."
if [ -f "cits/tests/smoke_test.py" ]; then
    SMOKE_OUT=$(python cits/tests/smoke_test.py 2>&1) || {
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

# 3. VPS関連ファイル変更チェック
echo "[3/3] VPS変更チェック..."
STAGED=$(git diff --cached --name-only 2>/dev/null || true)

# commands.json が変更された場合 → VPS確認を要求
if echo "$STAGED" | grep -q "commands.json"; then
    VPS_STATUS="$CLAUDE_PROJECT_DIR/cits/data/vps_status.json"
    if [ -f "$VPS_STATUS" ]; then
        LAST_TS=$(python3 -c "import json; d=json.load(open('$VPS_STATUS')); print(d.get('timestamp',''))" 2>/dev/null || echo "")
        echo "  ⚠ commands.json が変更されています"
        echo "  ⚠ VPS最終応答: $LAST_TS"
        echo "  ⚠ コミット後、vps_status.jsonに実行結果が届いたことを必ず確認すること"
    fi
fi

# bat/watchdog/vps_agent 変更 → VPS動作確認を要求
if echo "$STAGED" | grep -qE "(run_|watchdog|vps_agent|live_trader)"; then
    echo "  ⚠ VPS実行ファイルが変更されています"
    echo "  ⚠ 必須: VPS上で実際に動作確認し、vps_status.jsonでログを確認すること"
    echo "  ⚠ ログなしの「完了」報告は禁止（絶対ルール①②）"
fi

echo "  ✓ VPS変更チェック完了"
echo "=== PreCommit: 検証完了 ✓ ==="
