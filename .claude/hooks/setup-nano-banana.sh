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

# 8. Vertex AI パッチ適用（Claude Code Web 環境用）
# generativelanguage.googleapis.com がブロックされるため Vertex AI 経由に切り替え
NANO_BANANA_CLI="$(bun pm ls -g 2>/dev/null | grep nano-banana | head -1 | sed 's/.*─ //' || true)"
NANO_BANANA_SRC="/root/.bun/install/global/node_modules/nano-banana-2/src/cli.ts"
if [ -f "$NANO_BANANA_SRC" ]; then
  # Vertex AI モデルマッピングが未追加なら追加
  if ! grep -q "VERTEX_MODEL_MAP" "$NANO_BANANA_SRC" 2>/dev/null; then
    echo "[nano-banana] Vertex AI パッチを適用中..."
    # sed で Vertex AI 対応パッチを適用
    # 1. モデルマッピング追加
    sed -i '/^const DEFAULT_MODEL/i\
// Vertex AI uses different model names\
const VERTEX_MODEL_MAP: Record<string, string> = {\
  "gemini-3.1-flash-image-preview": "gemini-2.0-flash-preview-image-generation",\
  "gemini-3-pro-image-preview": "gemini-2.0-flash-preview-image-generation",\
};\
' "$NANO_BANANA_SRC"

    # 2. GoogleGenAI 初期化を Vertex AI 対応に変更
    sed -i '/const ai = new GoogleGenAI({ apiKey });/c\
  // Check for Vertex AI service account key\
  const vertexKeyPath = process.env.GOOGLE_APPLICATION_CREDENTIALS\
    || join(homedir(), ".nano-banana", "vertex-ai-key.json");\
  const useVertexAI = existsSync(vertexKeyPath);\
\
  let ai: GoogleGenAI;\
  if (useVertexAI) {\
    const keyData = JSON.parse(readFileSync(vertexKeyPath, "utf-8"));\
    const project = keyData.project_id;\
    const location = process.env.VERTEX_AI_LOCATION || "us-central1";\
    process.env.GOOGLE_APPLICATION_CREDENTIALS = vertexKeyPath;\
    ai = new GoogleGenAI({ vertexai: true, project, location });\
    console.log(`\\x1b[90mMode: Vertex AI (${project} / ${location})\\x1b[0m`);\
  } else {\
    const ai_key = options.apiKey || process.env.GEMINI_API_KEY;\
    ai = new GoogleGenAI({ apiKey: ai_key });\
  }' "$NANO_BANANA_SRC"

    # 3. config から Vertex AI 非対応の設定を除外
    sed -i 's/tools: \[{ googleSearch: {} }\],//' "$NANO_BANANA_SRC"

    # 4. モデル名マッピング
    sed -i 's/const modelName = options.model;/const modelName = (typeof useVertexAI !== "undefined" \&\& useVertexAI) ? (VERTEX_MODEL_MAP[options.model] || options.model) : options.model;/' "$NANO_BANANA_SRC"

    echo "[nano-banana] Vertex AI パッチ適用完了 ✓"
  fi
fi

# 9. Vertex AI サービスアカウントキーの配置
VERTEX_KEY_SRC="$CLAUDE_PROJECT_DIR/.claude/secrets/vertex-ai-key.json"
VERTEX_KEY_DST="$NANO_BANANA_ENV_DIR/vertex-ai-key.json"
if [ -f "$VERTEX_KEY_SRC" ] && [ ! -f "$VERTEX_KEY_DST" ]; then
  mkdir -p "$NANO_BANANA_ENV_DIR"
  cp "$VERTEX_KEY_SRC" "$VERTEX_KEY_DST"
  chmod 600 "$VERTEX_KEY_DST"
  echo "[nano-banana] Vertex AI キーを配置しました ✓"
fi

# 10. PATH にbunを追加（セッション全体で使えるように）
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
