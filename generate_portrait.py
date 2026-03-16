#!/usr/bin/env python3
"""Generate realistic portrait images using Nano Banana 2 (Gemini Imagen).

Usage:
    # List all available prompt templates
    python generate_portrait.py --list

    # Generate with default template (bedroom_morning, 3:4)
    python generate_portrait.py

    # Generate with a specific template
    python generate_portrait.py --id mirror_selfie

    # Generate with custom aspect ratio
    python generate_portrait.py --id cafe_window --aspect 9:16

    # Generate all 10 templates at once
    python generate_portrait.py --all

    # Use a completely custom prompt
    python generate_portrait.py --custom "Vertical portrait image (3:4). ..."
"""

import argparse
import logging
import sys

from core.image_generator import ImageGenerator
from core.portrait_prompts import PORTRAIT_PROMPTS, get_prompt, list_prompts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Generate realistic portrait images with Nano Banana 2"
    )
    parser.add_argument(
        "--list", action="store_true", help="List all available prompt templates"
    )
    parser.add_argument(
        "--id", default="bedroom_morning", help="Prompt template ID (default: bedroom_morning)"
    )
    parser.add_argument(
        "--aspect", default="3:4", help="Aspect ratio (default: 3:4)"
    )
    parser.add_argument(
        "--extra", default="", help="Additional prompt text to append"
    )
    parser.add_argument(
        "--all", action="store_true", help="Generate images for all 10 templates"
    )
    parser.add_argument(
        "--custom", type=str, help="Use a completely custom prompt instead of a template"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print prompt without generating"
    )

    args = parser.parse_args()

    if args.list:
        print("\n📸 Available portrait prompt templates:\n")
        for i, p in enumerate(PORTRAIT_PROMPTS, 1):
            print(f"  {i:2d}. {p['id']:20s}  {p['name']}")
        print(f"\nTotal: {len(PORTRAIT_PROMPTS)} templates")
        return

    gen = ImageGenerator()
    if not gen.enabled and not args.dry_run:
        logger.error("GEMINI_API_KEY is not set. Export it or add to config/.env")
        sys.exit(1)

    if args.custom:
        prompts_to_run = [("custom", args.custom)]
    elif args.all:
        prompts_to_run = [
            (p["id"], get_prompt(p["id"], aspect=args.aspect, extra=args.extra))
            for p in PORTRAIT_PROMPTS
        ]
    else:
        prompts_to_run = [(args.id, get_prompt(args.id, aspect=args.aspect, extra=args.extra))]

    results = []
    for prompt_id, prompt in prompts_to_run:
        print(f"\n--- [{prompt_id}] ---")
        if args.dry_run:
            print(f"PROMPT: {prompt}")
            continue

        logger.info("Generating: %s", prompt_id)
        path = gen.generate_image(prompt)
        if path:
            print(f"Saved: {path}")
            results.append(path)
        else:
            print("Failed to generate image.")

    if results:
        print(f"\nGenerated {len(results)} image(s).")


if __name__ == "__main__":
    main()
