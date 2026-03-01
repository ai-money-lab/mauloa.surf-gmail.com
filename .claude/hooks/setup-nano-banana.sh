#!/bin/bash
set -euo pipefail

# nano-banana セットアップスクリプト（完全自動版）
# session-start.sh から呼び出される
#
# リポジトリ内に Vertex AI 対応済みの CLI ソースを同梱しているため、
# ランタイムパッチ (sed) は不要。インストール → リンク → キー配置 のみ。

REPO_NANO_DIR="$CLAUDE_PROJECT_DIR/tools/nano-banana-2"
NANO_BANANA_ENV_DIR="/root/.nano-banana"

echo "[nano-banana] セットアップ開始..."

# 1. リポジトリ内にソースが存在するか確認
if [ ! -f "$REPO_NANO_DIR/package.json" ]; then
  echo "[nano-banana] ソースが見つかりません: $REPO_NANO_DIR"
  echo "[nano-banana] スキップします"
  exit 0
fi

# 2. bun がインストールされているか確認
if ! command -v bun &>/dev/null; then
  echo "[nano-banana] bun をインストール中..."
  curl -fsSL https://bun.sh/install | bash
  export PATH="/root/.bun/bin:$PATH"
fi

# 3. 依存パッケージをインストール
if [ ! -d "$REPO_NANO_DIR/node_modules" ]; then
  echo "[nano-banana] 依存パッケージをインストール中..."
  cd "$REPO_NANO_DIR"
  bun install --frozen-lockfile 2>/dev/null || bun install
fi

# 4. グローバルリンクを作成（nano-banana コマンドを使えるようにする）
if ! command -v nano-banana &>/dev/null; then
  echo "[nano-banana] グローバルリンクを作成中..."
  cd "$REPO_NANO_DIR"
  bun link 2>/dev/null || true
fi

# 5. Vertex AI サービスアカウントキーの配置
VERTEX_KEY_SRC="$CLAUDE_PROJECT_DIR/.claude/secrets/vertex-ai-key.json"
VERTEX_KEY_DST="$NANO_BANANA_ENV_DIR/vertex-ai-key.json"
if [ -f "$VERTEX_KEY_SRC" ] && [ ! -f "$VERTEX_KEY_DST" ]; then
  mkdir -p "$NANO_BANANA_ENV_DIR"
  cp "$VERTEX_KEY_SRC" "$VERTEX_KEY_DST"
  chmod 600 "$VERTEX_KEY_DST"
  echo "[nano-banana] Vertex AI キーを配置しました"
fi

# 6. API キー設定ファイルを確認（Vertex AI キーがない場合のフォールバック）
if [ ! -f "$VERTEX_KEY_DST" ] && [ ! -f "$NANO_BANANA_ENV_DIR/.env" ]; then
  mkdir -p "$NANO_BANANA_ENV_DIR"
  if [ -n "${GEMINI_API_KEY:-}" ]; then
    echo "GEMINI_API_KEY=$GEMINI_API_KEY" > "$NANO_BANANA_ENV_DIR/.env"
    echo "[nano-banana] 環境変数からAPIキーを設定しました"
  fi
fi

# 7. PATH に bun を追加（セッション全体で使えるように）
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  grep -q 'bun/bin' "$CLAUDE_ENV_FILE" 2>/dev/null || \
    echo 'export PATH="/root/.bun/bin:$PATH"' >> "$CLAUDE_ENV_FILE"
fi

# 8. 動作確認
if command -v nano-banana &>/dev/null; then
  echo "[nano-banana] セットアップ完了 ✓"
else
  echo "[nano-banana] 警告: コマンドが見つかりません。PATHを確認してください"
fi
