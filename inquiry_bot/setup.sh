#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
# ROCKEDGE 問い合わせBot — ワンコマンド自動セットアップ
# ═══════════════════════════════════════════════════════════
#
# 使い方:
#   chmod +x inquiry_bot/setup.sh
#   ./inquiry_bot/setup.sh
#
# このスクリプトが自動でやること:
#   1. Python依存パッケージのインストール
#   2. .envファイルの作成（テンプレートから）
#   3. 必要なディレクトリの作成
#   4. セットアップチェック実行
#   5. crontab登録（日次レポート等）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() { echo -e "${BLUE}[STEP]${NC} $1"; }
print_ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_err()  { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo "═══════════════════════════════════════════════════"
echo " ROCKEDGE 問い合わせBot — 自動セットアップ"
echo "═══════════════════════════════════════════════════"
echo ""

# ─── 1. Python依存パッケージ ───
print_step "Python依存パッケージをインストール中..."
if command -v pip3 &> /dev/null; then
    pip3 install -r "$PROJECT_ROOT/requirements.txt" -q 2>/dev/null && \
        print_ok "依存パッケージ インストール完了" || \
        print_warn "一部パッケージのインストールに問題あり（続行）"
elif command -v pip &> /dev/null; then
    pip install -r "$PROJECT_ROOT/requirements.txt" -q 2>/dev/null && \
        print_ok "依存パッケージ インストール完了" || \
        print_warn "一部パッケージのインストールに問題あり（続行）"
else
    print_err "pip が見つかりません。Pythonを先にインストールしてください。"
    exit 1
fi

# ─── 2. .envファイル ───
print_step ".envファイルを確認中..."
ENV_FILE="$PROJECT_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    print_ok ".env は既に存在します"
else
    cp "$PROJECT_ROOT/config/.env.example" "$ENV_FILE"
    print_ok ".env をテンプレートから作成しました"
    print_warn "→ $ENV_FILE を編集してAPIキーを設定してください"
fi

# ─── 3. 必要ディレクトリ ───
print_step "データディレクトリを作成中..."
mkdir -p "$PROJECT_ROOT/data/inquiry_bot_logs"
mkdir -p "$PROJECT_ROOT/reports/inquiry_bot"
print_ok "ディレクトリ作成完了"

# ─── 4. APIキー確認（対話式） ───
echo ""
print_step "APIキーの設定を確認します..."

# ANTHROPIC_API_KEY
if grep -q '^ANTHROPIC_API_KEY=.\+' "$ENV_FILE" 2>/dev/null; then
    print_ok "ANTHROPIC_API_KEY: 設定済み"
else
    echo ""
    echo -e "  ${YELLOW}ANTHROPIC_API_KEY が未設定です。${NC}"
    echo "  https://console.anthropic.com/settings/keys で取得できます。"
    read -rp "  APIキーを入力（後で設定する場合はEnter）: " api_key
    if [ -n "$api_key" ]; then
        sed -i "s/^ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=$api_key/" "$ENV_FILE"
        print_ok "ANTHROPIC_API_KEY を設定しました"
    else
        print_warn "後で .env に手動設定してください"
    fi
fi

# LINE_CHANNEL_SECRET
if grep -q '^LINE_CHANNEL_SECRET=.\+' "$ENV_FILE" 2>/dev/null; then
    print_ok "LINE_CHANNEL_SECRET: 設定済み"
else
    print_warn "LINE_CHANNEL_SECRET: 未設定（LINE連携する場合は後で設定）"
fi

# LINE_CHANNEL_ACCESS_TOKEN
if grep -q '^LINE_CHANNEL_ACCESS_TOKEN=.\+' "$ENV_FILE" 2>/dev/null; then
    print_ok "LINE_CHANNEL_ACCESS_TOKEN: 設定済み"
else
    print_warn "LINE_CHANNEL_ACCESS_TOKEN: 未設定（LINE連携する場合は後で設定）"
fi

# ─── 5. crontab登録 ───
echo ""
print_step "定期タスクを確認中..."

# 日次レポートのcronエントリ
CRON_ENTRY="0 21 * * * cd $PROJECT_ROOT && python -m inquiry_bot.scheduler daily_report"
CRON_HEALTH="*/5 * * * * cd $PROJECT_ROOT && python -m inquiry_bot.scheduler health_check"

if crontab -l 2>/dev/null | grep -q "inquiry_bot.scheduler"; then
    print_ok "crontab: 問い合わせBot定期タスク登録済み"
else
    read -rp "  定期タスク（日次レポート・ヘルスチェック）をcrontabに登録しますか？ (y/N): " yn
    if [ "$yn" = "y" ] || [ "$yn" = "Y" ]; then
        (crontab -l 2>/dev/null; echo "# ═══ 問い合わせBot 定期タスク ═══"; echo "$CRON_ENTRY"; echo "$CRON_HEALTH") | crontab -
        print_ok "crontab に登録しました"
    else
        print_warn "手動で登録する場合: crontab -e で以下を追加"
        echo "    $CRON_ENTRY"
        echo "    $CRON_HEALTH"
    fi
fi

# ─── 6. セットアップチェック ───
echo ""
print_step "セットアップチェックを実行..."
echo ""
cd "$PROJECT_ROOT"
python -m inquiry_bot.check_setup 2>/dev/null || true

# ─── 完了 ───
echo ""
echo "═══════════════════════════════════════════════════"
echo -e " ${GREEN}セットアップ完了！${NC}"
echo ""
echo " 次のステップ:"
echo "   1. テスト:    python -m inquiry_bot.test_local"
echo "   2. 起動:      make bot-start"
echo "   3. デプロイ:  make deploy-render"
echo "═══════════════════════════════════════════════════"
