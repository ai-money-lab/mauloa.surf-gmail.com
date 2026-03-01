#!/bin/bash
set -euo pipefail

# nano-banana セットアップスクリプト
# session-start.sh から呼び出される

NANO_BANANA_DIR="/root/tools/nano-banana-2"
NANO_BANANA_ENV_DIR="/root/.nano-banana"
NANO_BANANA_BIN="/root/.bun/bin/nano-banana"

echo "[nano-banana] セットアップ開始..."

# 1. bun がインストールされているか確認
if ! command -v bun &>/dev/null; then
  echo "[nano-banana] bun をインストール中..."
  curl -fsSL https://bun.sh/install | bash
  export PATH="/root/.bun/bin:$PATH"
fi

# 2. nano-banana ソースが存在するか確認
if [ ! -d "$NANO_BANANA_DIR" ]; then
  echo "[nano-banana] ソースが見つかりません: $NANO_BANANA_DIR"
  echo "[nano-banana] スキップします"
  exit 0
fi

# 3. 依存パッケージをインストール
if [ ! -d "$NANO_BANANA_DIR/node_modules" ]; then
  echo "[nano-banana] 依存パッケージをインストール中..."
  cd "$NANO_BANANA_DIR"
  bun install --frozen-lockfile 2>/dev/null || bun install
fi

# 4. グローバルリンクを確認・作成
if [ ! -L "$NANO_BANANA_BIN" ] || [ ! -e "$NANO_BANANA_BIN" ]; then
  echo "[nano-banana] グローバルリンクを作成中..."
  cd "$NANO_BANANA_DIR"
  bun link 2>/dev/null || true
fi

# 5. FFmpeg をインストール（透過モード用）
if ! command -v ffmpeg &>/dev/null; then
  echo "[nano-banana] FFmpeg をインストール中..."
  apt-get update -qq && apt-get install -y -qq ffmpeg >/dev/null 2>&1 || true
fi

# 6. ImageMagick をインストール（透過モード用）
if ! command -v convert &>/dev/null; then
  echo "[nano-banana] ImageMagick をインストール中..."
  apt-get update -qq && apt-get install -y -qq imagemagick >/dev/null 2>&1 || true
fi

# 7. API キー設定ファイルを確認
if [ ! -f "$NANO_BANANA_ENV_DIR/.env" ]; then
  mkdir -p "$NANO_BANANA_ENV_DIR"
  if [ -n "${GEMINI_API_KEY:-}" ]; then
    echo "GEMINI_API_KEY=$GEMINI_API_KEY" > "$NANO_BANANA_ENV_DIR/.env"
    echo "[nano-banana] 環境変数からAPIキーを設定しました"
  else
    echo "[nano-banana] 警告: APIキーが未設定です"
    echo "[nano-banana] 設定方法: echo 'GEMINI_API_KEY=your_key' > ~/.nano-banana/.env"
  fi
fi

# 8. PATH にbunを追加（セッション全体で使えるように）
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  grep -q 'bun/bin' "$CLAUDE_ENV_FILE" 2>/dev/null || \
    echo 'export PATH="/root/.bun/bin:$PATH"' >> "$CLAUDE_ENV_FILE"
fi

# 9. 動作確認
if command -v nano-banana &>/dev/null; then
  echo "[nano-banana] セットアップ完了 ✓"
else
  echo "[nano-banana] 警告: コマンドが見つかりません。PATHを確認してください"
fi
