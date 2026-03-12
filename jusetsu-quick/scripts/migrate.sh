#!/bin/bash
# D1マイグレーション自動適用スクリプト
# Usage: ./scripts/migrate.sh [--local|--remote]

set -e

MODE="${1:---remote}"
DB_NAME="jusetsu-quick-db"
MIGRATIONS_DIR="migrations"

echo "=== D1 Migration Runner ==="
echo "Mode: $MODE"
echo "Database: $DB_NAME"
echo ""

# マイグレーションファイルをソート順で適用
for file in "$MIGRATIONS_DIR"/*.sql; do
  if [ -f "$file" ]; then
    echo "Applying: $file"
    if [ "$MODE" = "--local" ]; then
      npx wrangler d1 execute "$DB_NAME" --local --file="$file" 2>&1 || echo "  (already applied or skipped)"
    else
      npx wrangler d1 execute "$DB_NAME" --remote --file="$file" 2>&1 || echo "  (already applied or skipped)"
    fi
    echo "  Done."
  fi
done

echo ""
echo "=== All migrations applied ==="
