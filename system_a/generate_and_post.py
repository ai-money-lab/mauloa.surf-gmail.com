"""Generate a post with Claude API, quality-check it, and post to X.

Usage:
    # Generate + quality check + post (full auto)
    python -m system_a.generate_and_post

    # Generate + quality check only (no posting)
    python -m system_a.generate_and_post --dry-run

    # Specify a pillar (1-5)
    python -m system_a.generate_and_post --pillar 5

    # Post a specific text directly (skip generation)
    python -m system_a.generate_and_post --text "投稿したいテキスト"
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from core.claude_client import ClaudeClient
from core.quality_checker import QualityChecker
from system_a.auto_post import AutoPoster
from system_a.theme_rotator import ThemeRotator

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"
DATA_DIR = BASE_DIR / "data" / "system_a" / "generated"


def generate_post(pillar: int = None) -> dict:
    """Generate a post using Claude API + Pipeline 3 prompt."""
    claude = ClaudeClient()
    rotator = ThemeRotator()

    theme = rotator.select_theme(target_pillar=pillar)
    if not theme:
        logger.error("No theme available")
        sys.exit(1)

    logger.info(
        "Theme: pillar %d (%s) / %s",
        theme["pillar_number"], theme["pillar_name"], theme["sub_theme"],
    )

    prompt_template = (PROMPTS_DIR / "ai_original.txt").read_text(encoding="utf-8")
    prompt = (
        prompt_template
        .replace("{pillar_number}", str(theme["pillar_number"]))
        .replace("{pillar_name}", theme["pillar_name"])
        .replace("{sub_theme}", theme["sub_theme"])
    )

    logger.info("Generating 3 patterns with Claude API...")
    result = claude.generate_json(prompt, temperature=0.9)
    result["pipeline"] = "P3"
    result["theme"] = theme

    # Record theme usage
    rotator.record_usage(theme["pillar_number"], theme["sub_theme"])

    # Save to file
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(JST)
    filename = now.strftime("%Y-%m-%d_%H%M%S") + ".json"
    out_path = DATA_DIR / filename
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved generation: %s", out_path)

    return result


def select_best_pattern(result: dict) -> dict:
    """Run quality check on A/B/C and return the best one."""
    claude = ClaudeClient()
    checker = QualityChecker(claude)

    patterns = []
    for key in ["pattern_a", "pattern_b", "pattern_c"]:
        p = result.get(key)
        if not p:
            continue
        text = p.get("text", p) if isinstance(p, dict) else p
        if isinstance(text, list):
            text = "\n\n".join(text)
        patterns.append({
            "key": key,
            "text": str(text),
            "format": p.get("format", "single") if isinstance(p, dict) else "single",
            "data": p,
        })

    if not patterns:
        logger.error("No patterns found in generation result")
        sys.exit(1)

    best = None
    best_score = -1

    for p in patterns:
        logger.info("Quality checking %s...", p["key"])
        qr = checker.check(
            profile="x_post",
            content=p["text"],
            context=f"Pipeline: P3, Pillar: {result.get('pillar', '?')}",
        )
        score = qr.get("total_score", 0)
        verdict = qr.get("result", "unknown")
        logger.info("  %s: score=%d, result=%s", p["key"], score, verdict)

        if score > best_score:
            best_score = score
            best = {**p, "quality_score": score, "quality_result": qr}

    logger.info("Best pattern: %s (score=%d)", best["key"], best_score)
    return best


def post_to_x(text: str, pillar: int = 0, pipeline: str = "P3", pattern: str = "A") -> dict:
    """Post text to X via AutoPoster."""
    poster = AutoPoster()

    if isinstance(text, list):
        logger.info("Posting thread (%d tweets)...", len(text))
        result = poster.post_thread(text)
    else:
        logger.info("Posting single tweet...")
        result = poster.post_tweet(text)

    return result


def main():
    parser = argparse.ArgumentParser(description="Generate and post to X")
    parser.add_argument("--dry-run", action="store_true", help="Generate only, no posting")
    parser.add_argument("--pillar", type=int, choices=[1, 2, 3, 4, 5], help="Target pillar")
    parser.add_argument("--text", type=str, help="Post specific text (skip generation)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Direct text posting
    if args.text:
        if args.dry_run:
            logger.info("[DRY RUN] Would post: %s", args.text)
            return
        result = post_to_x(args.text)
        tweet_id = result.get("data", {}).get("id", "unknown")
        logger.info("Posted! https://x.com/HirokiMiyao/status/%s", tweet_id)
        return

    # Full pipeline: Generate -> QC -> Post
    logger.info("=== Generate & Post Pipeline ===")

    # Step 1: Generate
    result = generate_post(pillar=args.pillar)
    pillar = result.get("pillar", result.get("theme", {}).get("pillar_number", "?"))
    sub_theme = result.get("sub_theme", result.get("theme", {}).get("sub_theme", "?"))
    logger.info("Generated for pillar %s / %s", pillar, sub_theme)

    # Step 2: Quality check & select best
    best = select_best_pattern(result)
    logger.info("Selected: %s (score=%d)", best["key"], best["quality_score"])
    logger.info("Text: %s", best["text"][:100] + "..." if len(best["text"]) > 100 else best["text"])

    threshold = 84
    if best["quality_score"] < threshold:
        logger.warning(
            "Quality score %d < threshold %d. Post may not meet standards.",
            best["quality_score"], threshold,
        )

    if args.dry_run:
        logger.info("[DRY RUN] Would post the above text.")
        print("\n--- Generated Post ---")
        print(best["text"])
        print(f"\nPillar: {pillar} / Theme: {sub_theme}")
        print(f"Pattern: {best['key']} / Score: {best['quality_score']}")
        return

    # Step 3: Post to X
    post_text = best["data"].get("text", best["text"]) if isinstance(best["data"], dict) else best["text"]
    post_result = post_to_x(post_text, pillar=pillar, pipeline="P3", pattern=best["key"])

    if isinstance(post_result, list):
        tweet_id = post_result[0].get("data", {}).get("id", "unknown") if post_result else "unknown"
    else:
        tweet_id = post_result.get("data", {}).get("id", "unknown")

    logger.info("Posted! https://x.com/HirokiMiyao/status/%s", tweet_id)
    logger.info("=== Complete ===")


if __name__ == "__main__":
    main()
