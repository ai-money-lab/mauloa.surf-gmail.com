#!/bin/bash
# ═══════════════════════════════════════════════════════════
# Riena LoRA学習用画像 一括生成スクリプト
#
# 使い方:
#   # 1. Gemini API（Imagen）で生成:
#   GEMINI_API_KEY=your_key bash system_e/scripts/generate_lora_images.sh
#
#   # 2. FAL.ai Flux Proで生成:
#   FAL_API_KEY=your_key bash system_e/scripts/generate_lora_images.sh --fal
#
#   # 3. RunPod ComfyUIで生成（Pod起動中のみ）:
#   bash system_e/scripts/generate_lora_images.sh --runpod
#
#   # 4. ドライラン（プロンプト確認のみ）:
#   bash system_e/scripts/generate_lora_images.sh --dry-run
#
# 生成後:
#   python3 system_e/scripts/train_lora.py prepare
#   python3 system_e/scripts/train_lora.py caption
#   python3 system_e/scripts/train_lora.py train
# ═══════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR/.."

# .envファイルがあれば読み込む
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

BACKEND_FLAG="${1:---default}"
COUNT_PER_SCENE=2  # 各シーン2枚生成（ベスト1枚を選ぶ）

# 全16シーン
SCENES=(
    "portrait_warm"
    "selfie_natural"
    "workout_power"
    "bikini_pool"
    "evening_intimate"
    "tokyo_golden"
    "lora_front_neutral"
    "lora_threequarter_left"
    "lora_threequarter_right"
    "lora_profile_left"
    "lora_full_body_casual"
    "lora_full_body_dress"
    "lora_bikini_beach"
    "lora_gym_mirror"
    "lora_seated_cafe"
    "lora_back_view_sporty"
)

echo "═══════════════════════════════════════════════════════════"
echo "  Riena LoRA Training Images — Batch Generator"
echo "  Scenes: ${#SCENES[@]}"
echo "  Count per scene: $COUNT_PER_SCENE"
echo "  Total expected: $((${#SCENES[@]} * COUNT_PER_SCENE)) images"
echo "  Backend: $BACKEND_FLAG"
echo "═══════════════════════════════════════════════════════════"
echo ""

TOTAL_OK=0
TOTAL_FAIL=0

for scene in "${SCENES[@]}"; do
    echo "--- Generating: $scene ($COUNT_PER_SCENE images) ---"

    case "$BACKEND_FLAG" in
        --fal)
            python3 system_e/generate_riena_face.py --fal --scene "$scene" --count "$COUNT_PER_SCENE"
            ;;
        --runpod)
            python3 system_e/generate_riena_face.py --runpod --scene "$scene" --count "$COUNT_PER_SCENE"
            ;;
        --gemini)
            python3 system_e/generate_riena_face.py --gemini --scene "$scene" --count "$COUNT_PER_SCENE"
            ;;
        --dry-run)
            python3 system_e/generate_riena_face.py --dry-run --scene "$scene"
            ;;
        *)
            # Default: Imagen (best quality)
            python3 system_e/generate_riena_face.py --scene "$scene" --count "$COUNT_PER_SCENE"
            ;;
    esac

    STATUS=$?
    if [ $STATUS -eq 0 ]; then
        TOTAL_OK=$((TOTAL_OK + 1))
    else
        TOTAL_FAIL=$((TOTAL_FAIL + 1))
    fi

    # API rate limit対策
    if [ "$BACKEND_FLAG" != "--dry-run" ]; then
        sleep 3
    fi
done

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  DONE"
echo "  OK: $TOTAL_OK scenes"
echo "  Failed: $TOTAL_FAIL scenes"
echo "  Images in: data/system_e/images/"
echo ""
echo "  Next steps:"
echo "  1. Review images, delete bad ones"
echo "  2. Move good ones to: data/system_e/lora_training/images/"
echo "  3. Run: python3 system_e/scripts/train_lora.py prepare"
echo "  4. Run: python3 system_e/scripts/train_lora.py train"
echo "═══════════════════════════════════════════════════════════"
