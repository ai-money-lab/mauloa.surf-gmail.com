#!/bin/bash
set -euo pipefail

# =============================================================================
# nano-banana installer for Claude Code
#
# Usage:
#   bash .claude/install-nano-banana.sh
#
# What it does:
#   1. Creates SessionStart hook (auto-setup on web sessions)
#   2. Installs nano-banana skill (image generation)
#   3. Installs setup-vertex-ai skill (403 error fix)
#   4. Creates nano-banana source code
#   5. Configures .gitignore for secrets
#
# After running:
#   - Start a new Claude Code Web session → nano-banana auto-installs
#   - Ask Claude to "generate an image" → it uses nano-banana
#   - If 403 error → use /setup-vertex-ai skill
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🍌 nano-banana installer for Claude Code"
echo "========================================="

# -----------------------------------------------------------------------------
# 1. Create directory structure
# -----------------------------------------------------------------------------
echo "[1/6] Creating directory structure..."
mkdir -p "$PROJECT_DIR/.claude/hooks"
mkdir -p "$PROJECT_DIR/.claude/skills/nano-banana"
mkdir -p "$PROJECT_DIR/.claude/skills/setup-vertex-ai"
mkdir -p "$PROJECT_DIR/.claude/secrets"
mkdir -p "$PROJECT_DIR/tools/nano-banana-2/src"

# -----------------------------------------------------------------------------
# 2. Create nano-banana source code
# -----------------------------------------------------------------------------
echo "[2/6] Creating nano-banana source..."

cat > "$PROJECT_DIR/tools/nano-banana-2/package.json" << 'PKGEOF'
{
  "name": "nano-banana-2",
  "version": "2.0.0",
  "description": "AI image generation CLI powered by Gemini. Multi-model, multi-resolution (512-4K), aspect ratios, cost tracking, green screen transparency, reference images.",
  "type": "module",
  "bin": {
    "nano-banana": "./src/cli.ts"
  },
  "scripts": {
    "start": "bun run src/cli.ts"
  },
  "keywords": ["ai", "image-generation", "gemini", "cli", "claude-code"],
  "license": "MIT",
  "dependencies": {
    "@google/genai": "^1.34.0"
  }
}
PKGEOF

# nano-banana CLI source is large - download from the existing installation
# or copy from repository if available
if [ -f "$PROJECT_DIR/tools/nano-banana-2/src/cli.ts" ]; then
  echo "  nano-banana source already exists, skipping"
else
  echo "  ⚠ nano-banana source (tools/nano-banana-2/src/cli.ts) needs to be added manually"
  echo "  Copy from an existing installation or from the nano-banana-2 package"
fi

# -----------------------------------------------------------------------------
# 3. Create SessionStart hook
# -----------------------------------------------------------------------------
echo "[3/6] Creating SessionStart hook..."

# settings.json
if [ ! -f "$PROJECT_DIR/.claude/settings.json" ]; then
  cat > "$PROJECT_DIR/.claude/settings.json" << 'SETEOF'
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/session-start.sh"
          }
        ]
      }
    ]
  }
}
SETEOF
else
  echo "  settings.json already exists, skipping (add hook manually if needed)"
fi

# session-start.sh - only create nano-banana section if not present
if [ ! -f "$PROJECT_DIR/.claude/hooks/session-start.sh" ]; then
  cat > "$PROJECT_DIR/.claude/hooks/session-start.sh" << 'SSEOF'
#!/bin/bash
set -euo pipefail

# Web環境（Claude Code on the web）のみで実行
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "=== SessionStart: セットアップ ==="

# nano-banana セットアップ
echo "[1/1] nano-banana setup..."
bash "$CLAUDE_PROJECT_DIR/.claude/hooks/setup-nano-banana.sh"

echo "=== SessionStart: 完了 ==="
SSEOF
  chmod +x "$PROJECT_DIR/.claude/hooks/session-start.sh"
fi

# setup-nano-banana.sh
cat > "$PROJECT_DIR/.claude/hooks/setup-nano-banana.sh" << 'NBEOF'
#!/bin/bash
set -euo pipefail

NANO_BANANA_DIR="$CLAUDE_PROJECT_DIR/tools/nano-banana-2"
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
NANO_BANANA_SRC="/root/.bun/install/global/node_modules/nano-banana-2/src/cli.ts"
if [ -f "$NANO_BANANA_SRC" ]; then
  if ! grep -q "VERTEX_MODEL_MAP" "$NANO_BANANA_SRC" 2>/dev/null; then
    echo "[nano-banana] Vertex AI パッチを適用中..."
    sed -i '/^const DEFAULT_MODEL/i\
// Vertex AI uses different model names\
const VERTEX_MODEL_MAP: Record<string, string> = {\
  "gemini-3.1-flash-image-preview": "gemini-2.0-flash-preview-image-generation",\
  "gemini-3-pro-image-preview": "gemini-2.0-flash-preview-image-generation",\
};\
' "$NANO_BANANA_SRC"

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

    sed -i 's/tools: \[{ googleSearch: {} }\],//' "$NANO_BANANA_SRC"
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

# 10. PATH にbunを追加
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  grep -q 'bun/bin' "$CLAUDE_ENV_FILE" 2>/dev/null || \
    echo 'export PATH="/root/.bun/bin:$PATH"' >> "$CLAUDE_ENV_FILE"
fi

# 11. 動作確認
if command -v nano-banana &>/dev/null; then
  echo "[nano-banana] セットアップ完了 ✓"
else
  echo "[nano-banana] 警告: コマンドが見つかりません。PATHを確認してください"
fi
NBEOF
chmod +x "$PROJECT_DIR/.claude/hooks/setup-nano-banana.sh"

# -----------------------------------------------------------------------------
# 4. Create skills
# -----------------------------------------------------------------------------
echo "[4/6] Creating skills..."

cat > "$PROJECT_DIR/.claude/skills/nano-banana/SKILL.md" << 'SKILLEOF'
---
name: nano-banana
description: Generates AI images using the nano-banana CLI (Gemini 3.1 Flash default, Pro available). Handles multi-resolution (512-4K), aspect ratios, reference images for style transfer, green screen workflow for transparent assets, cost tracking, and exact dimension control. Use when asked to "generate an image", "create a sprite", "make an asset", "generate artwork", or any image generation task for UI mockups, game assets, videos, or marketing materials.
---

# nano-banana

AI image generation CLI. Default model: Gemini 3.1 Flash Image Preview (Nano Banana 2).

## Setup (auto-configured by SessionStart hook)

The CLI is installed at `~/tools/nano-banana-2` and linked globally via `bun link`.
API key config: `~/.nano-banana/.env` (set GEMINI_API_KEY=your_key)

## Quick Reference

- Command: `nano-banana "prompt" [options]`
- Default: 1K resolution, Flash model, current directory

## Core Options

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | `nano-gen-{timestamp}` | Output filename (no extension) |
| `-s, --size` | `1K` | Image size: `512`, `1K`, `2K`, or `4K` |
| `-a, --aspect` | model default | Aspect ratio: `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, etc. |
| `-m, --model` | `flash` | Model: `flash`/`nb2`, `pro`/`nb-pro`, or any model ID |
| `-d, --dir` | current directory | Output directory |
| `-r, --ref` | - | Reference image (can use multiple times) |
| `-t, --transparent` | - | Generate on green screen, remove background (FFmpeg) |
| `--api-key` | - | Gemini API key (overrides env/file) |
| `--costs` | - | Show cost summary |

## Models

| Alias | Model | Use When |
|-------|-------|----------|
| `flash`, `nb2` | Gemini 3.1 Flash | Default. Fast, cheap (~$0.067/1K image) |
| `pro`, `nb-pro` | Gemini 3 Pro | Highest quality needed (~$0.134/1K image) |

## Key Workflows

```bash
# Basic generation
nano-banana "minimal dashboard UI with dark theme"

# High resolution widescreen
nano-banana "cinematic landscape" -s 2K -a 16:9

# Reference image editing
nano-banana "change the background to white" -r dark-ui.png -o light-ui

# Transparent assets (auto green screen)
nano-banana "robot mascot character" -t -o mascot

# Pro quality
nano-banana "detailed portrait" --model pro -s 2K
```

## Vertex AI Mode (Claude Code Web)

In Claude Code Web environments, the direct Gemini API is blocked by TLS inspection. nano-banana automatically falls back to **Vertex AI** when a service account key is found at `~/.nano-banana/vertex-ai-key.json`.

- Setup: Use the `setup-vertex-ai` skill if 403 errors occur
- When active, the CLI prints: `Mode: Vertex AI (project-id / us-central1)`

## API Key Setup

1. `--api-key` flag
2. `GEMINI_API_KEY` environment variable
3. `.env` file in current directory
4. `~/.nano-banana/.env`

Get a key at: https://aistudio.google.com/apikey
SKILLEOF

cat > "$PROJECT_DIR/.claude/skills/setup-vertex-ai/SKILL.md" << 'VSKILLEOF'
---
name: setup-vertex-ai
description: Sets up Vertex AI authentication for nano-banana in Claude Code Web environments where the direct Gemini API (generativelanguage.googleapis.com) is blocked by TLS inspection. Configures service account, patches nano-banana to use aiplatform.googleapis.com, and verifies image generation works. Use when nano-banana returns 403 errors, or when setting up a new Claude Code Web session for image generation.
---

# Setup Vertex AI for nano-banana

Configures nano-banana to use Vertex AI instead of the direct Gemini API which is blocked in Claude Code Web sandbox environments.

## When to Use

- nano-banana returns **403 Forbidden** errors
- Setting up a **new Google Cloud project** for image generation

## Setup Steps

### 1. Google Cloud Project Setup (User Action Required)

Guide the user through:

1. **Enable Vertex AI API**:
   `https://console.cloud.google.com/apis/library/aiplatform.googleapis.com?project=PROJECT_ID`

2. **Create Service Account**:
   `https://console.cloud.google.com/iam-admin/serviceaccounts?project=PROJECT_ID`
   - Name: `nano-banana`, Role: **Vertex AI ユーザー**

3. **Create JSON Key**: Click service account → Keys tab → Add Key → JSON

### 2. Save Service Account Key

```bash
cat > ~/.nano-banana/vertex-ai-key.json << 'KEYEOF'
{paste JSON here}
KEYEOF
chmod 600 ~/.nano-banana/vertex-ai-key.json
mkdir -p $CLAUDE_PROJECT_DIR/.claude/secrets
cp ~/.nano-banana/vertex-ai-key.json $CLAUDE_PROJECT_DIR/.claude/secrets/vertex-ai-key.json
```

### 3. Verify

```bash
nano-banana "test image: blue sky with clouds" -s 1K -o vertex-test
```

## How It Works

- Proxy blocks `generativelanguage.googleapis.com` → 403
- `aiplatform.googleapis.com` (Vertex AI) is NOT blocked
- `@google/genai` SDK supports `vertexai: true` mode
- Service account provides OAuth authentication
- SessionStart hook auto-patches nano-banana on each session
VSKILLEOF

# -----------------------------------------------------------------------------
# 5. Update .gitignore
# -----------------------------------------------------------------------------
echo "[5/6] Updating .gitignore..."
if [ -f "$PROJECT_DIR/.gitignore" ]; then
  grep -q '.claude/secrets/' "$PROJECT_DIR/.gitignore" || \
    echo '.claude/secrets/' >> "$PROJECT_DIR/.gitignore"
else
  echo '.claude/secrets/' > "$PROJECT_DIR/.gitignore"
fi

# -----------------------------------------------------------------------------
# 6. Summary
# -----------------------------------------------------------------------------
echo "[6/6] Done!"
echo ""
echo "========================================="
echo "🍌 nano-banana installed for Claude Code"
echo "========================================="
echo ""
echo "Files created:"
echo "  .claude/settings.json          - SessionStart hook config"
echo "  .claude/hooks/session-start.sh - Auto-setup on web sessions"
echo "  .claude/hooks/setup-nano-banana.sh - nano-banana installer"
echo "  .claude/skills/nano-banana/    - Image generation skill"
echo "  .claude/skills/setup-vertex-ai/ - Vertex AI fallback skill"
echo "  tools/nano-banana-2/           - CLI source"
echo ""
echo "Next steps:"
echo "  1. Add nano-banana CLI source to tools/nano-banana-2/src/cli.ts"
echo "  2. Set your Gemini API key:"
echo "     echo 'GEMINI_API_KEY=your_key' > ~/.nano-banana/.env"
echo "  3. If in Claude Code Web (403 errors), use /setup-vertex-ai"
echo "  4. Commit and push: git add .claude tools && git commit -m 'feat: add nano-banana'"
echo ""
