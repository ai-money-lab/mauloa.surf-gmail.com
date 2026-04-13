#!/bin/bash
# PostToolUse hook: Edit/Write後に変更されたPythonファイルをruffで即チェック
# TOOL_INPUT にファイルパスが含まれる
set -euo pipefail

# cits/ 配下のPythonファイル変更のみ対象
FILE_PATH=$(echo "$TOOL_INPUT" | grep -oP '"file_path"\s*:\s*"([^"]*)"' | head -1 | sed 's/.*"\([^"]*\)"/\1/' || true)

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# cits配下のPythonファイルのみ
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
ERRORS=$(ruff check "$FILE_PATH" 2>&1) || true
if [ -n "$ERRORS" ]; then
    echo "⚠️ ruff check 検出 ($FILE_PATH):"
    echo "$ERRORS"
    echo ""
    echo "→ 修正してから次に進んでください"
fi

# VPS関連ファイルの変更を検出 → 絶対ルールを表示
case "$FILE_PATH" in
    */vps_agent*|*/watchdog*|*/live_trader*|*/run_*.bat|*/position_monitor*)
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "⚠ VPS実行ファイルを変更しました"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "絶対ルール確認:"
        echo "  ① pushしたらvps_status.jsonで実行ログを必ず確認"
        echo "  ② ログなしに「動いています」と言わない"
        echo "  ⑤ 本番前にpaper mode / dry-runで動作確認"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ;;
esac
