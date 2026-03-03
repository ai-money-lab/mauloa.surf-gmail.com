---
name: nano-banana
description: Generates AI images using the nano-banana CLI (Gemini 3.1 Flash default, Pro available). Handles multi-resolution (512-4K), aspect ratios, reference images for style transfer, green screen workflow for transparent assets, cost tracking, and exact dimension control. Use when asked to "generate an image", "create a sprite", "make an asset", "generate artwork", or any image generation task for UI mockups, game assets, videos, or marketing materials.
---

# nano-banana

AI image generation CLI. Default model: Gemini 3.1 Flash Image Preview (Nano Banana 2).

## Setup (already completed)

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

## Sizes

| Size | Cost (Flash) | Cost (Pro) |
|------|-------------|------------|
| `512` | ~$0.045 | Flash only |
| `1K` | ~$0.067 | ~$0.134 |
| `2K` | ~$0.101 | ~$0.201 |
| `4K` | ~$0.151 | ~$0.302 |

## Aspect Ratios

Supported: `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `4:5`, `5:4`, `21:9`

Use `-a` flag: `nano-banana "cinematic scene" -a 16:9`

## Key Workflows

### Basic Generation

```bash
nano-banana "minimal dashboard UI with dark theme"
nano-banana "cinematic landscape" -s 2K -a 16:9
nano-banana "quick concept sketch" -s 512
```

### Model Selection

```bash
# Default (Flash - fast, cheap)
nano-banana "your prompt"

# Pro (highest quality)
nano-banana "detailed portrait" --model pro -s 2K
```

### Reference Images (Style Transfer / Editing)

```bash
# Edit existing image
nano-banana "change the background to pure white" -r dark-ui.png -o light-ui

# Style transfer - multiple references
nano-banana "combine these two styles" -r style1.png -r style2.png -o combined
```

### Transparent Assets

```bash
nano-banana "robot mascot character" -t -o mascot
nano-banana "pixel art treasure chest" -t -o chest
```

The `-t` flag automatically prompts the AI to generate on a green screen, then uses FFmpeg `colorkey` + `despill` to key out the background and remove green spill from edge pixels. Pixel-perfect transparency with no manual prompting needed.

Requires: FFmpeg and ImageMagick installed.

### Exact Dimensions

To get a specific output dimension:
1. First `-r` flag: your reference/style image
2. Last `-r` flag: blank image in target dimensions
3. Include dimensions in prompt

```bash
nano-banana "pixel art character in style of first image, 256x256" -r style.png -r blank-256x256.png -o sprite
```

## Reference Order Matters

- First reference: primary style/content source
- Additional references: secondary influences
- Last reference: controls output dimensions (if using blank image trick)

## Cost Tracking

Every generation is logged to `~/.nano-banana/costs.json`. View summary:

```bash
nano-banana --costs
```

## Use Cases

- **Landing page assets** - product mockups, UI previews
- **Image editing** - transform existing images with prompts
- **Style transfer** - combine multiple reference images
- **Marketing materials** - hero images, feature illustrations
- **UI iterations** - quickly generate variations of designs
- **Transparent assets** - icons, logos, mascots with no background
- **Game assets** - sprites, backgrounds, characters
- **Video production** - visual elements for video compositions

## Prompt Examples

```bash
# UI mockups
nano-banana "clean SaaS dashboard with analytics charts, white background"

# Widescreen cinematic
nano-banana "cyberpunk cityscape at sunset" -a 16:9 -s 2K

# Product shots with Pro quality
nano-banana "premium software product hero image" --model pro

# Quick low-res concept
nano-banana "rough sketch of a robot" -s 512

# Dark mode UI
nano-banana "Premium SaaS chat interface, dark mode, minimal, Linear-style aesthetic"

# Game assets with transparency (green screen auto-prompted)
nano-banana "pixel art treasure chest" -t -o chest

# Portrait aspect ratio
nano-banana "mobile app onboarding screen" -a 9:16
```

## Advanced Workflows

### 間取り図→フォトリアルレンダリング

2D間取り図からフォトリアリスティックなインテリアレンダリングを生成するワークフロー。

#### 手順

1. 間取り図画像（JPG/PNG）を用意
2. `-r` で間取り図を参照画像として指定
3. プロンプトでスタイル・視点を指定して生成

#### プロンプト（トップダウン俯瞰レンダリング）

```bash
nano-banana "Analyze the provided floor plan and generate a photorealistic top-down (true 90° orthographic) rendering of the entire apartment, keeping the exact same dimensions, proportions, walls, doors, windows, and furniture placement as shown. Do not change layout, scale, or orientation. Style: Modern Japanese (Japandi) light natural wood, warm neutral tones (beige, off-white, soft gray), minimalist furniture, clean lines, built-in cabinetry, stone or microcement surfaces, matte black accents, soft natural daylight. Architectural visualization style, ultra-realistic materials, no perspective distortion, no added or removed elements." -r floorplan.png -s 2K -o rendered-floorplan
```

#### カスタマイズ要素

| 要素 | デフォルト | 変更例 |
|------|-----------|--------|
| Style | Modern Japanese (Japandi) | Scandinavian, Industrial, Luxury Modern |
| 素材 | light natural wood | walnut, concrete, marble |
| 視点 | top-down (true 90° orthographic) | eye-level perspective（各部屋のパース画像） |
| 家具 | minimalist furniture | mid-century modern furniture |
| トーン | warm neutral tones | cool monochrome, warm earth tones |

#### 視点バリエーション

```bash
# トップダウン俯瞰（デフォルト）
nano-banana "...top-down (true 90° orthographic)..." -r floorplan.png -s 2K

# リビングのパース画像
nano-banana "Generate a photorealistic eye-level perspective of the living room based on this floor plan. Style: Modern Japanese (Japandi)..." -r floorplan.png -s 2K -a 16:9

# 高品質版（Proモデル）
nano-banana "..." -r floorplan.png -s 2K -m pro
```

#### 外部プラットフォーム（参考）

| プラットフォーム | 特徴 |
|-----------------|------|
| mitte.ai | カスタムAIモデル対応。間取り図アップロード→プロンプト入力で生成 |
| Rendair AI (rendair.ai) | チャットUIで自然言語編集可能 |
| Fenestra (fenestra.app) | 建築・インテリア特化。2Dプラン→空間ビジュアライゼーション変換に強い |
| Google AI Studio | Geminiモデルに直接アクセス。API利用も可能 |

> 参考元: @EHuanglu (el.cine) — X投稿 / 田中義弘 (taziku CEO)

## API Key Setup

The CLI resolves the Gemini API key in this order:
1. `--api-key` flag
2. `GEMINI_API_KEY` environment variable
3. `.env` file in current directory
4. `.env` file next to the CLI script
5. `~/.nano-banana/.env`

Get a key at: https://aistudio.google.com/apikey

## Vertex AI Mode (Claude Code Web)

In Claude Code Web environments, the direct Gemini API is blocked by TLS inspection. nano-banana automatically falls back to **Vertex AI** (`aiplatform.googleapis.com`) when a service account key is found at `~/.nano-banana/vertex-ai-key.json`.

- Model mapping: `gemini-3.1-flash-image-preview` → `gemini-2.0-flash-preview-image-generation`
- Auth: Google Cloud service account (OAuth, not API key)
- Setup: Use the `setup-vertex-ai` skill if 403 errors occur

When Vertex AI mode is active, the CLI prints:
```
Mode: Vertex AI (project-id / us-central1)
```
