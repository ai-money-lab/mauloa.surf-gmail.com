#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════
# HIROKI AI Empire — Divine Skills Installer
# Claude Code カスタムスキル一括セットアップ
# ═══════════════════════════════════════════════════════════

COMMANDS_DIR=".claude/commands"

echo ""
echo "═══════════════════════════════════════════════════"
echo " HIROKI AI Empire — Divine Skills"
echo " 神がかりスキルをインストール中..."
echo "═══════════════════════════════════════════════════"
echo ""

mkdir -p "$COMMANDS_DIR"

count=$(find "$COMMANDS_DIR" -name "*.md" 2>/dev/null | wc -l)

echo " インストール済みスキル: ${count}個"
echo ""
echo " 使えるスキル一覧:"
echo " ─────────────────────────────────────────────────"
echo ""

for f in "$COMMANDS_DIR"/*.md; do
  [ -f "$f" ] || continue
  name=$(basename "$f" .md)
  desc=$(head -1 "$f" | sed 's/^# *//')
  printf "   /%s\t— %s\n" "$name" "$desc"
done

echo ""
echo " ─────────────────────────────────────────────────"
echo ""
echo " 使い方: Claude Codeで /<スキル名> を入力"
echo ""
echo "═══════════════════════════════════════════════════"
echo " Divine Skills セットアップ完了"
echo "═══════════════════════════════════════════════════"
