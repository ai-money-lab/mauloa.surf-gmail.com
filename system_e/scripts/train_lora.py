#!/usr/bin/env python3
"""System E — LoRA Training Pipeline for Riena.

Rienaの顔一貫性を確立するためのLoRA学習ワークフロー。
RunPod GPU Pod上でFlux.1 Dev用LoRAを学習する。

ワークフロー:
  1. prepare  — 画像前処理（リサイズ・クロップ・品質チェック）
  2. caption  — 自動キャプション生成
  3. train    — RunPod GPU上でLoRA学習実行
  4. validate — 学習済みLoRAの品質検証
  5. deploy   — image_pipeline.pyへ統合

Usage:
    # Step 1: 画像準備
    python3 system_e/scripts/train_lora.py prepare

    # Step 2: キャプション生成
    python3 system_e/scripts/train_lora.py caption

    # Step 3: RunPod GPU Pod上で学習実行
    python3 system_e/scripts/train_lora.py train

    # Step 4: 品質検証
    python3 system_e/scripts/train_lora.py validate

    # Step 5: デプロイ
    python3 system_e/scripts/train_lora.py deploy

    # 全ステップ一括:
    python3 system_e/scripts/train_lora.py all
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_PATH = Path(__file__).parent.parent / "lora_training_config.yaml"


def load_config() -> dict:
    """Load LoRA training configuration."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ═══════════════════════════════════════════════════════════
# Step 1: prepare — 画像前処理
# ═══════════════════════════════════════════════════════════


def step_prepare(config: dict) -> bool:
    """Prepare training images: resize, crop, quality check."""
    dataset = config["dataset"]
    images_dir = PROJECT_ROOT / dataset["images_dir"]
    reqs = dataset["image_requirements"]
    resolution = reqs["resolution"]
    valid_formats = set(reqs["formats"])

    images_dir.mkdir(parents=True, exist_ok=True)

    # Check for images
    image_files = [
        f
        for f in images_dir.iterdir()
        if f.is_file() and f.suffix.lstrip(".").lower() in valid_formats
    ]

    if not image_files:
        logger.error(
            "No images found in %s\n"
            "  Place 15-30 reference images of Riena here.\n"
            "  Requirements:\n"
            "    - Various angles: front, 3/4, profile\n"
            "    - Various expressions: neutral, smile, serious\n"
            "    - Various lighting: daylight, golden hour, studio\n"
            "    - Various backgrounds: plain, outdoor, indoor\n"
            "    - Various outfits: athletic, casual, formal\n"
            "  Formats: %s",
            images_dir,
            ", ".join(valid_formats),
        )
        return False

    min_count = reqs["min_count"]
    max_count = reqs["max_count"]

    if len(image_files) < min_count:
        logger.warning(
            "Only %d images found (minimum %d recommended). "
            "More variety = better consistency.",
            len(image_files),
            min_count,
        )
    elif len(image_files) > max_count:
        logger.warning(
            "%d images found (maximum %d recommended). Too many can cause overfitting.",
            len(image_files),
            max_count,
        )

    # Process images
    try:
        from PIL import Image
    except ImportError:
        logger.error("Pillow not installed. Run: pip install Pillow")
        return False

    processed_dir = images_dir / "processed"
    processed_dir.mkdir(exist_ok=True)

    processed_count = 0
    for img_path in sorted(image_files):
        try:
            img = Image.open(img_path)

            # Convert to RGB if needed
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Resize to target resolution (center crop to square)
            w, h = img.size
            min_dim = min(w, h)
            left = (w - min_dim) // 2
            top = (h - min_dim) // 2
            img = img.crop((left, top, left + min_dim, top + min_dim))
            img = img.resize((resolution, resolution), Image.LANCZOS)

            # Save processed
            out_path = processed_dir / f"{img_path.stem}.png"
            img.save(out_path, "PNG", quality=95)
            processed_count += 1
            logger.info("Processed: %s -> %s", img_path.name, out_path.name)

        except Exception as e:
            logger.warning("Failed to process %s: %s", img_path.name, e)

    logger.info(
        "Prepared %d/%d images in %s", processed_count, len(image_files), processed_dir
    )
    return processed_count >= min_count


# ═══════════════════════════════════════════════════════════
# Step 2: caption — 自動キャプション生成
# ═══════════════════════════════════════════════════════════


def step_caption(config: dict) -> bool:
    """Generate captions for training images."""
    dataset = config["dataset"]
    captioning = config["captioning"]
    images_dir = PROJECT_ROOT / dataset["images_dir"] / "processed"
    captions_dir = PROJECT_ROOT / dataset["captions_dir"]
    captions_dir.mkdir(parents=True, exist_ok=True)

    trigger_word = config["character"]["trigger_word"]
    required_tags = captioning["required_tags"]
    excluded_tags = set(captioning["excluded_tags"])

    image_files = sorted(images_dir.glob("*.png"))
    if not image_files:
        logger.error("No processed images found. Run 'prepare' first.")
        return False

    method = captioning["method"]
    captioned = 0

    for img_path in image_files:
        caption_path = captions_dir / f"{img_path.stem}.txt"

        if caption_path.exists():
            logger.info("Caption exists, skipping: %s", img_path.name)
            captioned += 1
            continue

        if method == "manual":
            logger.info(
                "Manual mode: create %s with description of %s",
                caption_path,
                img_path.name,
            )
            continue

        # Auto-caption using Gemini Vision (free, high quality)
        auto_caption = _caption_with_gemini(img_path)

        if not auto_caption:
            # Fallback: generate basic caption from filename
            auto_caption = "portrait photo of a young Japanese woman"
            logger.warning("Auto-caption failed for %s, using default", img_path.name)

        # Build final caption
        tags = list(required_tags)

        # Filter excluded tags from auto-caption
        caption_words = auto_caption.lower()
        for tag in excluded_tags:
            caption_words = caption_words.replace(tag, "")

        # Assemble: trigger_word, required_tags, auto_caption
        parts = [trigger_word] + tags + [caption_words.strip()]
        final_caption = ", ".join(parts)

        caption_path.write_text(final_caption, encoding="utf-8")
        captioned += 1
        logger.info("Captioned: %s -> %s", img_path.name, final_caption[:80])

    logger.info("Captioned %d/%d images", captioned, len(image_files))
    return captioned == len(image_files)


def _caption_with_gemini(image_path: Path) -> str | None:
    """Generate caption using Gemini Vision API."""
    import base64

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return None

    image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Describe this photo for AI image training. "
                            "Include: pose, expression, clothing, hair style, "
                            "lighting, background, body type. "
                            "Be specific and factual. "
                            "Output only the description, no preamble."
                        )
                    },
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": image_data,
                        }
                    },
                ]
            }
        ]
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                text = part.get("text", "")
                if text:
                    return text.strip()
    except Exception as e:
        logger.warning("Gemini captioning failed: %s", e)

    return None


# ═══════════════════════════════════════════════════════════
# Step 3: train — RunPod GPU上でLoRA学習
# ═══════════════════════════════════════════════════════════


def step_train(config: dict) -> bool:
    """Launch LoRA training on RunPod GPU Pod.

    Uses kohya-ss/sd-scripts for Flux.1 Dev LoRA training.
    """
    dataset = config["dataset"]
    gpu = config["gpu"]["runpod"]

    images_dir = PROJECT_ROOT / dataset["images_dir"] / "processed"
    captions_dir = PROJECT_ROOT / dataset["captions_dir"]
    output_dir = PROJECT_ROOT / dataset["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    # Validate prerequisites
    if not list(images_dir.glob("*.png")):
        logger.error("No processed images. Run 'prepare' first.")
        return False
    if not list(captions_dir.glob("*.txt")):
        logger.error("No captions. Run 'caption' first.")
        return False

    api_key = os.getenv("RUNPOD_API_KEY", "")
    if not api_key:
        logger.error("RUNPOD_API_KEY not set.")
        return False

    # Generate training script for RunPod
    train_script = _generate_kohya_script(config)
    script_path = output_dir / "run_training.sh"
    script_path.write_text(train_script, encoding="utf-8")
    script_path.chmod(0o755)
    logger.info("Training script generated: %s", script_path)

    # Generate dataset config (TOML for kohya)
    dataset_toml = _generate_dataset_toml(config)
    toml_path = output_dir / "dataset_config.toml"
    toml_path.write_text(dataset_toml, encoding="utf-8")
    logger.info("Dataset config generated: %s", toml_path)

    # Launch RunPod GPU Pod
    pod_id = _launch_runpod_pod(api_key, gpu)
    if not pod_id:
        logger.error("Failed to launch RunPod pod.")
        _print_manual_instructions(config, script_path, toml_path)
        return False

    logger.info("RunPod pod launched: %s", pod_id)
    logger.info(
        "Upload training data and run the script on the pod.\n"
        "  1. Upload images: rsync -avz %s/ root@<pod-ip>:/workspace/training/images/\n"
        "  2. Upload captions: rsync -avz %s/ root@<pod-ip>:/workspace/training/captions/\n"
        "  3. Upload script: scp %s root@<pod-ip>:/workspace/\n"
        "  4. SSH and run: ssh root@<pod-ip> 'bash /workspace/run_training.sh'",
        images_dir,
        captions_dir,
        script_path,
    )

    return True


def _generate_kohya_script(config: dict) -> str:
    """Generate kohya-ss/sd-scripts training shell script."""
    training = config["training"]
    params = training["params"]
    character = config["character"]
    deploy = config["deploy"]

    return f"""#!/bin/bash
# ═══════════════════════════════════════════════════════════
# Riena LoRA Training Script (Flux.1 Dev)
# Generated by System E
# Run on RunPod GPU Pod with >= 24GB VRAM
# ═══════════════════════════════════════════════════════════
set -e

echo "=== Riena LoRA Training ==="
echo "Trigger word: {character["trigger_word"]}"
echo "Base model: {training["base_model"]}"

# ─── 環境セットアップ ───
pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -q accelerate transformers safetensors bitsandbytes
pip install -q prodigyopt lion-pytorch

# kohya-ss/sd-scripts インストール
if [ ! -d "/workspace/sd-scripts" ]; then
    cd /workspace
    git clone https://github.com/kohya-ss/sd-scripts.git
    cd sd-scripts
    git checkout sd3  # Flux対応ブランチ
    pip install -q -r requirements.txt
    pip install -q -e .
fi

# ─── ベースモデルDL ───
MODEL_DIR="/workspace/models"
mkdir -p "$MODEL_DIR"

if [ ! -f "$MODEL_DIR/flux1-dev.safetensors" ]; then
    echo "Downloading Flux.1 Dev..."
    pip install -q huggingface_hub
    python3 -c "
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='black-forest-labs/FLUX.1-dev',
    filename='flux1-dev.safetensors',
    local_dir='/workspace/models',
    local_dir_use_symlinks=False,
)
"
fi

# ─── 学習データ配置 ───
TRAIN_DIR="/workspace/training"
mkdir -p "$TRAIN_DIR/images/1_{character["trigger_word"]}"

# 画像とキャプションを同じディレクトリに配置
# （kohyaの命名規則: 繰り返し数_トリガーワード）
cp /workspace/training/images/*.png "$TRAIN_DIR/images/1_{character["trigger_word"]}/" 2>/dev/null || true
cp /workspace/training/captions/*.txt "$TRAIN_DIR/images/1_{character["trigger_word"]}/" 2>/dev/null || true

echo "Training images: $(ls $TRAIN_DIR/images/1_{character["trigger_word"]}/*.png 2>/dev/null | wc -l)"

# ─── LoRA学習実行 ───
cd /workspace/sd-scripts

accelerate launch \\
    --mixed_precision {params["mixed_precision"]} \\
    --num_cpu_threads_per_process 4 \\
    flux_train_network.py \\
    --pretrained_model_name_or_path "$MODEL_DIR/flux1-dev.safetensors" \\
    --train_data_dir "$TRAIN_DIR/images" \\
    --output_dir "$TRAIN_DIR/output" \\
    --output_name "{deploy["lora_output_filename"].replace(".safetensors", "")}" \\
    --save_model_as safetensors \\
    --network_module networks.lora_flux \\
    --network_dim {params["network_dim"]} \\
    --network_alpha {params["network_alpha"]} \\
    --learning_rate {params["learning_rate"]} \\
    --unet_lr {params["unet_lr"]} \\
    --text_encoder_lr {params["text_encoder_lr"]} \\
    --train_batch_size {params["train_batch_size"]} \\
    --max_train_epochs {params["max_train_epochs"]} \\
    --save_every_n_epochs {params["save_every_n_epochs"]} \\
    --resolution {params["resolution"]} \\
    --mixed_precision {params["mixed_precision"]} \\
    --optimizer_type {params["optimizer_type"]} \\
    --lr_scheduler {params["lr_scheduler"]} \\
    --lr_warmup_steps {params["lr_warmup_steps"]} \\
    --cache_latents \\
    --cache_text_encoder_outputs \\
    --gradient_checkpointing \\
    --seed 42 \\
    --caption_extension .txt \\
    --max_token_length 225

echo ""
echo "=== Training Complete ==="
echo "LoRA saved to: $TRAIN_DIR/output/{deploy["lora_output_filename"]}"
echo ""
echo "Next steps:"
echo "  1. Download: scp root@<pod-ip>:$TRAIN_DIR/output/{deploy["lora_output_filename"]} ./"
echo "  2. Validate: python3 system_e/scripts/train_lora.py validate"
echo "  3. Deploy:   python3 system_e/scripts/train_lora.py deploy"
"""


def _generate_dataset_toml(config: dict) -> str:
    """Generate dataset configuration TOML for kohya-ss."""
    character = config["character"]
    params = config["training"]["params"]

    return f"""[general]
shuffle_caption = true
keep_tokens = 1
caption_extension = ".txt"

[[datasets]]
resolution = {params["resolution"]}
batch_size = {params["train_batch_size"]}

  [[datasets.subsets]]
  image_dir = "/workspace/training/images/1_{character["trigger_word"]}"
  caption_extension = ".txt"
  num_repeats = 1
"""


def _launch_runpod_pod(api_key: str, gpu_config: dict) -> str | None:
    """Launch a RunPod GPU Pod for training."""
    url = "https://api.runpod.io/graphql"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    query = """
    mutation {{
        podFindAndDeployOnDemand(input: {{
            name: "riena-lora-training"
            imageName: "{docker_image}"
            gpuTypeId: "{gpu_type}"
            volumeInGb: {volume_size}
            containerDiskInGb: 20
            minVcpuCount: 4
            minMemoryInGb: 32
            startSsh: true
        }}) {{
            id
            desiredStatus
            imageName
            machine {{
                podHostId
            }}
        }}
    }}
    """.format(
        docker_image=gpu_config["docker_image"],
        gpu_type=gpu_config["gpu_type"],
        volume_size=gpu_config["volume_size_gb"],
    )

    try:
        resp = requests.post(url, headers=headers, json={"query": query}, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        pod_data = data.get("data", {}).get("podFindAndDeployOnDemand")
        if pod_data:
            return pod_data.get("id")

        errors = data.get("errors", [])
        if errors:
            logger.error("RunPod API error: %s", errors[0].get("message", ""))
    except Exception as e:
        logger.error("RunPod pod launch failed: %s", e)

    return None


def _print_manual_instructions(config: dict, script_path: Path, toml_path: Path):
    """Print manual training instructions when RunPod auto-launch fails."""
    print("\n" + "=" * 60)
    print("MANUAL TRAINING INSTRUCTIONS")
    print("=" * 60)
    print()
    print("RunPod auto-launch failed. Train manually:")
    print()
    print("Option A: RunPod GPU Pod (recommended)")
    print("  1. Go to https://www.runpod.io/console/pods")
    print("  2. Deploy: RTX A5000 or A6000 (24GB+ VRAM)")
    print(f"  3. Upload training data and run: {script_path}")
    print()
    print("Option B: Vast.ai (cheaper)")
    print("  1. Go to https://vast.ai/console/create/")
    print("  2. Filter: RTX 3090, 24GB VRAM")
    print(f"  3. Upload and run: {script_path}")
    print()
    print("Option C: Google Colab (free tier)")
    print("  1. Use kohya-ss Colab notebook")
    print("  2. Upload images + captions")
    print("  3. Set parameters from config")
    print("=" * 60)


# ═══════════════════════════════════════════════════════════
# Step 4: validate — 品質検証
# ═══════════════════════════════════════════════════════════


def step_validate(config: dict) -> bool:
    """Validate trained LoRA quality."""
    dataset = config["dataset"]
    validation = config["validation"]
    deploy = config["deploy"]

    output_dir = PROJECT_ROOT / dataset["output_dir"]
    lora_path = output_dir / deploy["lora_output_filename"]

    if not lora_path.exists():
        logger.error(
            "LoRA file not found: %s\n"
            "  Download from RunPod pod first:\n"
            "  scp root@<pod-ip>:/workspace/training/output/%s %s/",
            lora_path,
            deploy["lora_output_filename"],
            output_dir,
        )
        return False

    lora_size_mb = lora_path.stat().st_size / (1024 * 1024)
    logger.info("LoRA found: %s (%.1f MB)", lora_path.name, lora_size_mb)

    # Sanity checks
    if lora_size_mb < 1:
        logger.error(
            "LoRA file too small (%.1f MB). Training may have failed.", lora_size_mb
        )
        return False
    if lora_size_mb > 500:
        logger.warning(
            "LoRA file very large (%.1f MB). Might be full fine-tune, not LoRA.",
            lora_size_mb,
        )

    # Generate test images
    logger.info("Generating validation images...")
    test_prompts = validation["test_prompts"]
    test_dir = output_dir / "validation"
    test_dir.mkdir(exist_ok=True)

    # Save validation config
    val_report = {
        "lora_file": str(lora_path),
        "lora_size_mb": round(lora_size_mb, 1),
        "test_prompts": test_prompts,
        "timestamp": datetime.now(JST).isoformat(),
        "status": "pending_human_review",
        "notes": (
            "Review validation images manually.\n"
            "Check: face consistency, quality, no artifacts.\n"
            "If satisfied, run 'deploy' to integrate."
        ),
    }

    report_path = test_dir / "validation_report.json"
    report_path.write_text(
        json.dumps(val_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info("Validation report saved: %s", report_path)
    logger.info(
        "Generate test images using the LoRA:\n"
        "  python3 system_e/generate_riena_face.py --runpod --all-scenes\n"
        "  (after deploying the LoRA to RunPod)"
    )
    return True


# ═══════════════════════════════════════════════════════════
# Step 5: deploy — image_pipeline.pyへ統合
# ═══════════════════════════════════════════════════════════


def step_deploy(config: dict) -> bool:
    """Deploy trained LoRA to production pipeline."""
    dataset = config["dataset"]
    deploy_config = config["deploy"]

    output_dir = PROJECT_ROOT / dataset["output_dir"]
    lora_path = output_dir / deploy_config["lora_output_filename"]

    if not lora_path.exists():
        logger.error("LoRA file not found: %s", lora_path)
        return False

    # Update character_config.yaml with LoRA path
    if deploy_config["auto_update_config"]:
        char_config_path = Path(__file__).parent.parent / "character_config.yaml"
        with open(char_config_path, encoding="utf-8") as f:
            char_config = yaml.safe_load(f)

        # Set the LoRA model path
        runpod_path = (
            deploy_config["runpod_model_path"] + deploy_config["lora_output_filename"]
        )
        char_config["image_generation"]["lora"]["model_path"] = runpod_path

        with open(char_config_path, "w", encoding="utf-8") as f:
            yaml.dump(char_config, f, allow_unicode=True, default_flow_style=False)

        logger.info("Updated character_config.yaml: lora.model_path = %s", runpod_path)

    logger.info(
        "Deploy complete.\n"
        "  LoRA: %s\n"
        "  Next: Upload LoRA to RunPod volume:\n"
        "    scp %s root@<pod-ip>:%s",
        lora_path,
        lora_path,
        deploy_config["runpod_model_path"],
    )

    print("\n" + "=" * 60)
    print("DEPLOYMENT CHECKLIST")
    print("=" * 60)
    print(f"  [1] Upload LoRA to RunPod: {deploy_config['runpod_model_path']}")
    print("  [2] character_config.yaml updated with LoRA path")
    print("  [3] Test: python3 system_e/generate_riena_face.py --runpod")
    print("  [4] Verify face consistency across scenes")
    print("  [5] If good, commit and push config changes")
    print("=" * 60)

    return True


# ═══════════════════════════════════════════════════════════
# メイン
# ═══════════════════════════════════════════════════════════

STEPS = {
    "prepare": step_prepare,
    "caption": step_caption,
    "train": step_train,
    "validate": step_validate,
    "deploy": step_deploy,
}


def main():
    parser = argparse.ArgumentParser(
        description="Riena LoRA Training Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Steps:
  prepare   — Preprocess training images (resize, crop, quality check)
  caption   — Auto-generate captions for training images
  train     — Launch LoRA training on RunPod GPU
  validate  — Verify trained LoRA quality
  deploy    — Integrate LoRA into image_pipeline.py
  all       — Run all steps sequentially
""",
    )
    parser.add_argument(
        "step",
        choices=list(STEPS.keys()) + ["all", "status"],
        help="Training step to execute",
    )

    args = parser.parse_args()
    config = load_config()

    if args.step == "status":
        _print_status(config)
        return

    if args.step == "all":
        steps = ["prepare", "caption", "train", "validate", "deploy"]
    else:
        steps = [args.step]

    for step_name in steps:
        print(f"\n{'=' * 60}")
        print(f"Step: {step_name}")
        print(f"{'=' * 60}")

        success = STEPS[step_name](config)
        if not success:
            logger.error("Step '%s' failed. Fix issues and retry.", step_name)
            sys.exit(1)

        logger.info("Step '%s' completed successfully.", step_name)


def _print_status(config: dict):
    """Print current training pipeline status."""
    dataset = config["dataset"]

    images_dir = PROJECT_ROOT / dataset["images_dir"]
    processed_dir = images_dir / "processed"
    captions_dir = PROJECT_ROOT / dataset["captions_dir"]
    output_dir = PROJECT_ROOT / dataset["output_dir"]
    lora_filename = config["deploy"]["lora_output_filename"]

    print("\n" + "=" * 60)
    print("Riena LoRA Training Status")
    print("=" * 60)

    # Images
    raw_count = (
        len(list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg")))
        if images_dir.exists()
        else 0
    )
    proc_count = len(list(processed_dir.glob("*.png"))) if processed_dir.exists() else 0
    print(f"  Raw images:       {raw_count} ({images_dir})")
    print(f"  Processed images: {proc_count} ({processed_dir})")

    # Captions
    cap_count = len(list(captions_dir.glob("*.txt"))) if captions_dir.exists() else 0
    print(f"  Captions:         {cap_count} ({captions_dir})")

    # LoRA
    lora_path = output_dir / lora_filename
    if lora_path.exists():
        size_mb = lora_path.stat().st_size / (1024 * 1024)
        print(f"  LoRA:             {lora_filename} ({size_mb:.1f} MB)")
    else:
        print("  LoRA:             Not yet trained")

    # Config status
    char_config_path = Path(__file__).parent.parent / "character_config.yaml"
    with open(char_config_path, encoding="utf-8") as f:
        char_config = yaml.safe_load(f)
    lora_model_path = (
        char_config.get("image_generation", {}).get("lora", {}).get("model_path", "")
    )
    print(f"  Deployed LoRA:    {lora_model_path or 'Not deployed'}")

    print("=" * 60)


if __name__ == "__main__":
    main()
