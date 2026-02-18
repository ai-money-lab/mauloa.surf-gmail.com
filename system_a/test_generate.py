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

    from system_a.generate_and_post import generate_post, quality_check_patterns

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
        post_type = p.get("post_type", "?") if isinstance(p, dict) else "?"
        char_count = p.get("char_count", "?") if isinstance(p, dict) else "?"
        cta = p.get("cta_type", "?") if isinstance(p, dict) else "?"
        label = key.replace("pattern_", "").upper()
        print(f"\n--- Pattern {label} ({post_type}, {char_count}字, CTA={cta}) ---")
        if isinstance(text, list):
            for i, t in enumerate(text, 1):
                print(f"  [{i}] {t}")
        else:
            print(f"  {text}")

    # Step 2: Quality check
    print("\n" + "=" * 60)
    print("Quality Check (threshold=80)")
    print("=" * 60)
    checked = quality_check_patterns(result)
    for p in checked:
        label = p["key"].replace("pattern_", "").upper()
        status = "PASS" if p["passed"] else "FAIL"
        print(f"  {label}: score={p['quality_score']} {status}")

    best = checked[0]
    print(f"\nBest: {best['key']} (score={best['quality_score']})")
    print(f"Text: {best['text']}")

    logger.info("=== Test Complete (no post made) ===")


if __name__ == "__main__":
    main()
