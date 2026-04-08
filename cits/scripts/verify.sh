#!/bin/bash
# CITS 検証スクリプト — コード変更後に必ず実行すること
# 使い方: bash cits/scripts/verify.sh
set -e

cd "$(git rev-parse --show-toplevel)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0

echo ""
echo "=========================================="
echo " CITS 検証スクリプト"
echo "=========================================="

# 1. Ruff lint
echo ""
echo -e "${YELLOW}[1/4] ruff check${NC}"
if ruff check cits/ 2>/dev/null; then
    echo -e "${GREEN}  ✅ ruff check パス${NC}"
else
    echo -e "${RED}  ❌ ruff check 失敗${NC}"
    FAILED=1
fi

# 2. Smoke test
echo ""
echo -e "${YELLOW}[2/4] スモークテスト${NC}"
if python cits/tests/smoke_test.py; then
    echo -e "${GREEN}  ✅ スモークテスト パス${NC}"
else
    echo -e "${RED}  ❌ スモークテスト 失敗${NC}"
    FAILED=1
fi

# 3. Unit tests
echo ""
echo -e "${YELLOW}[3/4] ユニットテスト${NC}"
if pytest cits/tests/ -v --tb=short 2>/dev/null; then
    echo -e "${GREEN}  ✅ ユニットテスト パス${NC}"
else
    echo -e "${RED}  ❌ ユニットテスト 失敗${NC}"
    FAILED=1
fi

# 4. Entry point
echo ""
echo -e "${YELLOW}[4/4] エントリーポイント確認${NC}"
if python -m cits.main --help >/dev/null 2>&1; then
    echo -e "${GREEN}  ✅ python -m cits.main --help 起動OK${NC}"
else
    echo -e "${RED}  ❌ python -m cits.main --help 起動失敗${NC}"
    FAILED=1
fi

echo ""
echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ 全検証パス — デプロイ可能${NC}"
    exit 0
else
    echo -e "${RED}⛔ 検証失敗 — 修正が必要${NC}"
    exit 1
fi
