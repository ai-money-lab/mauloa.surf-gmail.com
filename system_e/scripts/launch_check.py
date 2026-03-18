"""System E — Launch Readiness Checker.

Run before going live to verify all prerequisites are met.

Usage:
    PYTHONPATH=. python system_e/scripts/launch_check.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"
SKIP = "\033[90mSKIP\033[0m"


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = PASS if ok else FAIL
    suffix = f" — {detail}" if detail else ""
    print(f"  [{status}] {label}{suffix}")
    return ok


def warn(label: str, detail: str = ""):
    suffix = f" — {detail}" if detail else ""
    print(f"  [{WARN}] {label}{suffix}")


def main():
    print("=" * 60)
    print(" System E — Launch Readiness Check")
    print("=" * 60)
    results = []

    # ─── 1. Config files ───
    print("\n1. Configuration Files")
    config_yaml = PROJECT_ROOT / "config" / "config.yaml"
    results.append(check("config/config.yaml exists", config_yaml.exists()))

    char_config = PROJECT_ROOT / "system_e" / "character_config.yaml"
    results.append(check("character_config.yaml exists", char_config.exists()))

    brand_strategy = PROJECT_ROOT / "system_e" / "brand_partnership_strategy.yaml"
    results.append(check("brand_partnership_strategy.yaml exists", brand_strategy.exists()))

    # ─── 2. API Keys ───
    print("\n2. API Keys")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    results.append(check("ANTHROPIC_API_KEY", bool(anthropic_key), "Required for content generation"))

    x_keys = all([
        os.getenv("X_API_KEY"),
        os.getenv("X_API_SECRET_KEY"),
        os.getenv("X_ACCESS_TOKEN"),
        os.getenv("X_ACCESS_TOKEN_SECRET"),
    ])
    results.append(check("X API credentials (4 keys)", x_keys, "Required for posting"))

    line_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    if not line_token:
        warn("LINE_CHANNEL_ACCESS_TOKEN", "Optional but recommended for notifications")
    else:
        results.append(check("LINE_CHANNEL_ACCESS_TOKEN", True))

    # ─── 3. Image Generation Backend ───
    print("\n3. Image Generation Backend")
    import yaml
    config = {}
    if config_yaml.exists():
        with open(config_yaml, encoding="utf-8") as f:
            config = yaml.safe_load(f)

    provider = config.get("system_e", {}).get("image_provider", "unknown")
    print(f"  Provider: {provider}")

    runpod_pod_id = os.getenv("RUNPOD_POD_ID", "")
    runpod_endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID", "")
    runpod_api_key = os.getenv("RUNPOD_API_KEY", "")
    fal_key = os.getenv("FAL_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")

    if provider == "comfyui_pod":
        results.append(check("RUNPOD_API_KEY", bool(runpod_api_key)))
        results.append(check("RUNPOD_POD_ID", bool(runpod_pod_id), "GPU Pod ID for ComfyUI"))
    elif provider == "runpod":
        results.append(check("RUNPOD_API_KEY", bool(runpod_api_key)))
        results.append(check("RUNPOD_ENDPOINT_ID", bool(runpod_endpoint_id), "Serverless endpoint"))
    elif provider == "fal_ai":
        results.append(check("FAL_API_KEY", bool(fal_key)))
    else:
        warn(f"Unknown provider: {provider}")

    # Fallback options
    has_any_image = bool(runpod_pod_id or runpod_endpoint_id or fal_key or gemini_key)
    results.append(check("At least one image backend available", has_any_image))

    if gemini_key:
        check("GEMINI_API_KEY (Imagen fallback)", True)

    # ─── 4. Python modules ───
    print("\n4. Python Modules")
    try:
        from system_e.content_generator import ContentGenerator  # noqa: F401
        results.append(check("ContentGenerator imports OK", True))
    except Exception as e:
        results.append(check("ContentGenerator", False, str(e)))

    try:
        from system_e.image_pipeline import ImagePipeline
        pipeline = ImagePipeline()
        results.append(check(
            f"ImagePipeline ({pipeline.provider})",
            True,
            f"enabled={pipeline.enabled}",
        ))
    except Exception as e:
        results.append(check("ImagePipeline", False, str(e)))

    try:
        from system_e.posting_scheduler import PostingScheduler  # noqa: F401
        results.append(check("PostingScheduler imports OK", True))
    except Exception as e:
        results.append(check("PostingScheduler", False, str(e)))

    try:
        from system_e.fanvue_manager import FanvueManager  # noqa: F401
        results.append(check("FanvueManager imports OK", True))
    except Exception as e:
        results.append(check("FanvueManager", False, str(e)))

    try:
        from system_e.analytics import Analytics  # noqa: F401
        results.append(check("Analytics imports OK", True))
    except Exception as e:
        results.append(check("Analytics", False, str(e)))

    try:
        from system_e.daily_pipeline import SystemEPipeline  # noqa: F401
        results.append(check("SystemEPipeline imports OK", True))
    except Exception as e:
        results.append(check("SystemEPipeline", False, str(e)))

    # ─── 5. Data directories ───
    print("\n5. Data Directories")
    data_dirs = [
        "data/system_e",
        "data/system_e/images",
        "data/system_e/generated",
        "data/system_e/analytics",
        "data/system_e/fanvue",
    ]
    for d in data_dirs:
        path = PROJECT_ROOT / d
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            check(d, True, "created")
        else:
            check(d, True)

    # ─── 6. Character config validation ───
    print("\n6. Character Config Validation")
    if char_config.exists():
        with open(char_config, encoding="utf-8") as f:
            char = yaml.safe_load(f)

        character = char.get("character", {})
        results.append(check("Character name set", bool(character.get("name")), character.get("name", "")))
        results.append(check("Character tagline set", bool(character.get("tagline"))))

        voice = character.get("content_voice", {})
        results.append(check("Content voice defined", bool(voice.get("tone"))))
        results.append(check("Banned topics listed", len(voice.get("banned_topics", [])) > 0))

        disclosure = char.get("disclosure", {})
        results.append(check("AI disclosure configured", bool(disclosure.get("bio_text"))))

        scenes = char.get("image_generation", {}).get("scene_categories", {})
        results.append(check(f"Scene categories: {len(scenes)}", len(scenes) >= 3))

    # ─── 7. System E config ───
    print("\n7. System E Config")
    se = config.get("system_e", {})
    results.append(check("System E enabled", se.get("enabled", False)))
    results.append(check(f"Posts per day: {se.get('posts_per_day')}", se.get("posts_per_day", 0) > 0))
    results.append(check(
        f"Post times: {se.get('post_times_jst')}",
        len(se.get("post_times_jst", [])) > 0,
    ))

    x_account = se.get("x_account", "")
    if not x_account:
        warn("x_account not set", "Set dedicated X account handle in config.yaml")
    else:
        check(f"X account: @{x_account}", True)

    ref_image = se.get("reference_image_url", "")
    if not ref_image:
        warn("reference_image_url not set", "Optional but improves character consistency")

    # ─── 8. GitHub Actions ───
    print("\n8. GitHub Actions")
    workflow = PROJECT_ROOT / ".github" / "workflows" / "system-e-pipeline.yml"
    results.append(check("system-e-pipeline.yml exists", workflow.exists()))

    # ─── Summary ───
    passed = sum(results)
    total = len(results)
    failed = total - passed
    print("\n" + "=" * 60)
    print(f" Results: {passed}/{total} passed", end="")
    if failed > 0:
        print(f" ({failed} FAILED)")
    else:
        print(" — ALL CLEAR!")
    print("=" * 60)

    if failed > 0:
        print("\n Next steps: Fix the FAIL items above before launching.")
        print(" WARNings are optional but recommended.")
    else:
        print("\n System E is ready to launch!")
        print(" Run:  make system-e  (or trigger GitHub Actions)")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
