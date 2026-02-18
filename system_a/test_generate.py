"""Test script: Generate a post with Claude API (dry-run, no posting).

Usage:
    python -m system_a.test_generate
    python -m system_a.test_generate --pillar 5
"""

import argparse
import json
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Test post generation")
    parser.add_argument("--pillar", type=int, choices=[1, 2, 3, 4, 5], help="Target pillar")
    args = parser.parse_args()

    from system_a.generate_and_post import generate_post, select_best_pattern

    logger.info("=== Test Generate (dry-run) ===")

    # Step 1: Generate
    result = generate_post(pillar=args.pillar)
    pillar = result.get("pillar", "?")
    sub_theme = result.get("sub_theme", "?")

    # Show all 3 patterns
    print("\n" + "=" * 60)
    print(f"Pillar {pillar}: {result.get('pillar_name', '?')}")
    print(f"Theme: {sub_theme}")
    print("=" * 60)

    for key in ["pattern_a", "pattern_b", "pattern_c"]:
        p = result.get(key)
        if not p:
            continue
        text = p.get("text", p) if isinstance(p, dict) else p
        fmt = p.get("format", "single") if isinstance(p, dict) else "single"
        print(f"\n--- {key.upper()} ({fmt}) ---")
        if isinstance(text, list):
            for i, t in enumerate(text, 1):
                print(f"  [{i}] {t}")
        else:
            print(f"  {text}")

    # Step 2: Quality check
    print("\n" + "=" * 60)
    print("Quality Check")
    print("=" * 60)
    best = select_best_pattern(result)
    print(f"\nBest: {best['key']} (score={best['quality_score']})")
    print(f"Text: {best['text']}")

    verdict = "PASS" if best["quality_score"] >= 84 else "FAIL"
    print(f"\nVerdict: {verdict} (threshold=84)")

    logger.info("=== Test Complete (no post made) ===")


if __name__ == "__main__":
    main()
