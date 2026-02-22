"""Generate a post with Claude API, quality-check it, and post to X.

Usage:
    # Full auto: generate + QC + post best pattern
    python -m system_a.generate_and_post

    # Interactive: generate + QC + choose pattern yourself
    python -m system_a.generate_and_post --interactive

    # Dry-run: generate + QC only (no posting)
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

from core.claude_client import ClaudeClient  # noqa: E402
from core.quality_checker import QualityChecker  # noqa: E402
from system_a.auto_post import AutoPoster  # noqa: E402
from system_a.theme_rotator import ThemeRotator  # noqa: E402

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"
DATA_DIR = BASE_DIR / "data" / "system_a" / "generated"

QUALITY_THRESHOLD = 84


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


def quality_check_patterns(result: dict) -> list:
    """Run quality check on all A/B/C patterns. Returns sorted list."""
    claude = ClaudeClient()
    checker = QualityChecker(claude)

    checked = []
    for key in ["pattern_a", "pattern_b", "pattern_c"]:
        p = result.get(key)
        if not p:
            continue
        text = p.get("text", p) if isinstance(p, dict) else p
        if isinstance(text, list):
            display_text = "\n\n".join(text)
        else:
            display_text = str(text)

        logger.info("Quality checking %s...", key)
        qr = checker.check(
            profile="x_post",
            content=display_text,
            context=f"Pipeline: P3, Pillar: {result.get('pillar', '?')}",
        )
        score = qr.get("total_score", 0)
        verdict = qr.get("result", "unknown")
        logger.info("  %s: score=%d, result=%s", key, score, verdict)

        checked.append({
            "key": key,
            "text": display_text,
            "format": p.get("format", "single") if isinstance(p, dict) else "single",
            "cta_type": p.get("cta_type", "") if isinstance(p, dict) else "",
            "data": p,
            "quality_score": score,
            "quality_result": qr,
            "passed": score >= QUALITY_THRESHOLD,
        })

    # Sort by score descending
    checked.sort(key=lambda x: x["quality_score"], reverse=True)
    return checked


def display_patterns(checked: list, pillar, sub_theme) -> None:
    """Display all patterns with scores for interactive selection."""
    print(f"\n{'=' * 60}")
    print(f"  Pillar {pillar} / {sub_theme}")
    print(f"  Threshold: {QUALITY_THRESHOLD}")
    print(f"{'=' * 60}")

    for i, p in enumerate(checked):
        status = "PASS" if p["passed"] else "FAIL"
        label = p["key"].replace("pattern_", "").upper()
        cta = p.get("cta_type", "")
        print(f"\n--- [{i+1}] Pattern {label}  (score={p['quality_score']} {status}) ---")
        if cta:
            print(f"  CTA: {cta}")
        text = p["text"]
        if isinstance(text, list):
            for j, t in enumerate(text, 1):
                print(f"  [{j}] {t}")
        else:
            # Wrap long text for readability
            print(f"  {text}")

    print(f"\n{'=' * 60}")


def interactive_select(checked: list) -> dict:
    """Let user choose which pattern to post."""
    while True:
        choice = input(f"\nどのパターンを投稿しますか？ (1-{len(checked)}, q=やめる): ").strip()
        if choice.lower() == "q":
            logger.info("Cancelled by user.")
            sys.exit(0)
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(checked):
                selected = checked[idx]
                label = selected["key"].replace("pattern_", "").upper()
                if not selected["passed"]:
                    confirm = input(
                        f"Pattern {label} はスコア{selected['quality_score']} "
                        f"(閾値{QUALITY_THRESHOLD}未満)です。投稿しますか？ (y/n): "
                    ).strip()
                    if confirm.lower() != "y":
                        continue
                return selected
        except ValueError:
            pass
        print(f"1〜{len(checked)} の数字か q を入力してください")


def post_to_x(text, pillar: int = 0, pipeline: str = "P3", pattern: str = "A") -> dict:
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
    parser.add_argument("--dry-run", action="store_true", help="Generate + QC only, no posting")
    parser.add_argument("--interactive", "-i", action="store_true", help="Choose pattern manually")
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

    # Step 2: Quality check all patterns
    checked = quality_check_patterns(result)
    if not checked:
        logger.error("No patterns generated")
        sys.exit(1)

    # Step 3: Select pattern
    if args.interactive:
        # Interactive: show all, let user choose
        display_patterns(checked, pillar, sub_theme)
        selected = interactive_select(checked)
    elif args.dry_run:
        # Dry-run: show all, don't post
        display_patterns(checked, pillar, sub_theme)
        best = checked[0]
        logger.info("[DRY RUN] Auto-select: %s (score=%d)", best["key"], best["quality_score"])
        return
    else:
        # Full auto: pick highest score that passes
        passed = [p for p in checked if p["passed"]]
        if passed:
            selected = passed[0]
        else:
            logger.warning("No pattern passed QC (threshold=%d). Using best score.", QUALITY_THRESHOLD)
            selected = checked[0]

    label = selected["key"].replace("pattern_", "").upper()
    logger.info("Selected: Pattern %s (score=%d)", label, selected["quality_score"])

    if args.dry_run:
        logger.info("[DRY RUN] Would post: %s", selected["text"][:80])
        return

    # Step 4: Post to X
    post_text = selected["data"].get("text", selected["text"]) if isinstance(selected["data"], dict) else selected["text"]
    post_result = post_to_x(post_text, pillar=pillar, pipeline="P3", pattern=label)

    if isinstance(post_result, list):
        tweet_id = post_result[0].get("data", {}).get("id", "unknown") if post_result else "unknown"
    else:
        tweet_id = post_result.get("data", {}).get("id", "unknown")

    logger.info("Posted! https://x.com/HirokiMiyao/status/%s", tweet_id)
    logger.info("=== Complete ===")


if __name__ == "__main__":
    main()
