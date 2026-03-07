"""Generate a post with Claude API, quality-check it, and post to X.

Usage:
    # 承認待ちモード（デフォルト）: 生成 + QC + LINE通知 → 承認待ち
    python -m system_a.generate_and_post

    # 承認して投稿: 承認待ちの投稿を投稿する
    python -m system_a.generate_and_post --approve

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
from core.fact_checker import FactChecker  # noqa: E402
from core.image_generator import ImageGenerator  # noqa: E402
from core.notifier import Notifier  # noqa: E402
from system_a.auto_post import AutoPoster  # noqa: E402
from system_a.theme_rotator import ThemeRotator  # noqa: E402

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"
DATA_DIR = BASE_DIR / "data" / "system_a" / "generated"

QUALITY_THRESHOLD = 84
PENDING_POST_PATH = BASE_DIR / "data" / "system_a" / "pending_approval.json"


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
    """Run fact check + quality check on all A/B/C patterns. Returns sorted list."""
    claude = ClaudeClient()
    checker = QualityChecker(claude)
    fact_checker = FactChecker()

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

        # Step 1: Auto-fix known typos
        display_text = fact_checker.auto_fix(display_text)

        # Step 2: Fact check — reject fabricated/rule-violating content
        logger.info("Fact checking %s...", key)
        fact_result = fact_checker.check(display_text)
        if not fact_result.passed:
            violations = [v["message"] for v in fact_result.violations]
            logger.warning("  %s: FACT CHECK REJECTED — %s", key, "; ".join(violations))
            checked.append({
                "key": key,
                "text": display_text,
                "format": p.get("format", "single") if isinstance(p, dict) else "single",
                "cta_type": p.get("cta_type", "") if isinstance(p, dict) else "",
                "data": p,
                "quality_score": 0,
                "quality_result": {"result": "rejected", "rejection_reasons": violations, "total_score": 0},
                "passed": False,
            })
            continue

        # Step 3: Quality check (only if fact check passed)
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


def generate_image_for_post(text, pillar: int = 0) -> str | None:
    """Generate an image for a post using Gemini Imagen."""
    gen = ImageGenerator()
    if not gen.enabled:
        logger.info("Image generation disabled (no GEMINI_API_KEY)")
        return None

    display = text if isinstance(text, str) else text[0]
    logger.info("Generating image for post...")
    path = gen.generate_for_post(display, pillar=pillar)
    if path:
        logger.info("Image generated: %s", path)
    else:
        logger.warning("Image generation failed, will post text-only")
    return path


def post_to_x(text, pillar: int = 0, pipeline: str = "P3", pattern: str = "A",
              image_path: str | None = None) -> dict:
    """Post text to X via AutoPoster, optionally with an image."""
    poster = AutoPoster()

    if image_path:
        media_id = poster._upload_media(image_path)
        if not media_id:
            logger.warning("Image upload failed, posting text-only")
    else:
        media_id = None

    if isinstance(text, list):
        logger.info("Posting thread (%d tweets)...", len(text))
        result = poster.post_thread(text, media_id=media_id)
    else:
        logger.info("Posting single tweet...")
        result = poster.post_tweet(text, media_id=media_id)

    return result


def save_pending(post_data: dict) -> None:
    """Save a post to pending approval file."""
    PENDING_POST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_POST_PATH.write_text(
        json.dumps(post_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Saved to pending approval: %s", PENDING_POST_PATH)


def load_pending() -> dict | None:
    """Load the pending approval post."""
    if not PENDING_POST_PATH.exists():
        return None
    try:
        return json.loads(PENDING_POST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def clear_pending() -> None:
    """Remove the pending approval file after posting."""
    if PENDING_POST_PATH.exists():
        PENDING_POST_PATH.unlink()


def notify_for_approval(selected: dict, pillar, sub_theme) -> None:
    """Send LINE notification with post content for human approval."""
    notifier = Notifier()
    text = selected["text"]
    if isinstance(text, list):
        display = "\n".join(text)
    else:
        display = text

    label = selected["key"].replace("pattern_", "").upper()
    score = selected["quality_score"]

    message = (
        f"【X投稿 承認待ち】\n"
        f"柱{pillar} / {sub_theme}\n"
        f"パターン{label} (スコア: {score})\n"
        f"---\n"
        f"{display}\n"
        f"---\n"
        f"承認する場合:\n"
        f"python -m system_a.generate_and_post --approve"
    )
    notifier.send_line(message)
    logger.info("LINE approval notification sent")


def main():
    parser = argparse.ArgumentParser(description="Generate and post to X")
    parser.add_argument("--dry-run", action="store_true", help="Generate + QC only, no posting")
    parser.add_argument("--interactive", "-i", action="store_true", help="Choose pattern manually")
    parser.add_argument("--approve", action="store_true", help="Approve and post the pending post")
    parser.add_argument("--pillar", type=int, choices=[1, 2, 3, 4, 5], help="Target pillar")
    parser.add_argument("--text", type=str, help="Post specific text (skip generation)")
    parser.add_argument("--no-image", action="store_true", help="Skip image generation")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Approve mode: post the pending approved content
    if args.approve:
        pending = load_pending()
        if not pending:
            logger.error("承認待ちの投稿がありません")
            sys.exit(1)

        post_text = pending["text"]
        image_path = pending.get("image_path")
        pillar = pending.get("pillar", 0)
        pattern = pending.get("pattern", "A")

        logger.info("Posting approved content...")
        post_result = post_to_x(
            post_text, pillar=pillar, pipeline="P3",
            pattern=pattern, image_path=image_path,
        )

        if isinstance(post_result, list):
            tweet_id = post_result[0].get("data", {}).get("id", "unknown") if post_result else "unknown"
        else:
            tweet_id = post_result.get("data", {}).get("id", "unknown")

        clear_pending()
        notifier = Notifier()
        notifier.send_line(f"投稿完了\nhttps://x.com/HirokiMiyao/status/{tweet_id}")
        logger.info("Posted! https://x.com/HirokiMiyao/status/%s", tweet_id)
        return

    # Direct text posting (requires --interactive or explicit intent)
    if args.text:
        image_path = None
        if not args.no_image:
            image_path = generate_image_for_post(args.text)
        if args.dry_run:
            logger.info("[DRY RUN] Would post: %s", args.text)
            if image_path:
                logger.info("[DRY RUN] With image: %s", image_path)
            return
        # Direct text still requires saving to pending + approval
        save_pending({
            "text": args.text,
            "image_path": image_path,
            "pillar": 0,
            "pattern": "direct",
            "created_at": datetime.now(JST).isoformat(),
        })
        notifier = Notifier()
        notifier.send_line(
            f"【X投稿 承認待ち（直接テキスト）】\n---\n{args.text}\n---\n"
            f"承認: python -m system_a.generate_and_post --approve"
        )
        logger.info("Pending approval. Use --approve to post.")
        return

    # Full pipeline: Generate -> QC -> Pending Approval
    logger.info("=== Generate & Approve Pipeline ===")

    # Step 1: Generate
    result = generate_post(pillar=args.pillar)
    pillar = result.get("pillar", result.get("theme", {}).get("pillar_number", "?"))
    sub_theme = result.get("sub_theme", result.get("theme", {}).get("sub_theme", "?"))
    logger.info("Generated for pillar %s / %s", pillar, sub_theme)

    # Step 2: Quality check all patterns (includes fact check)
    checked = quality_check_patterns(result)
    if not checked:
        logger.error("No patterns generated")
        sys.exit(1)

    # Step 3: Select pattern
    if args.interactive:
        display_patterns(checked, pillar, sub_theme)
        selected = interactive_select(checked)
    elif args.dry_run:
        display_patterns(checked, pillar, sub_theme)
        best = checked[0]
        logger.info("[DRY RUN] Auto-select: %s (score=%d)", best["key"], best["quality_score"])
        return
    else:
        # Auto-select: pick highest score that passes
        passed = [p for p in checked if p["passed"]]
        if passed:
            selected = passed[0]
        else:
            logger.warning("No pattern passed QC (threshold=%d). Skipping today.", QUALITY_THRESHOLD)
            notifier = Notifier()
            notifier.send_line(
                f"【X投稿 品質不足でスキップ】\n"
                f"柱{pillar} / {sub_theme}\n"
                f"全パターンが品質基準を満たしませんでした。"
            )
            return

    label = selected["key"].replace("pattern_", "").upper()
    logger.info("Selected: Pattern %s (score=%d)", label, selected["quality_score"])

    if args.dry_run:
        logger.info("[DRY RUN] Would post: %s", selected["text"][:80])
        return

    # Step 4: Generate image (if enabled)
    post_text = selected["data"].get("text", selected["text"]) if isinstance(selected["data"], dict) else selected["text"]
    image_path = None
    if not args.no_image:
        image_path = generate_image_for_post(post_text, pillar=int(pillar) if str(pillar).isdigit() else 0)

    # Step 5: Save to pending approval (DO NOT auto-post)
    save_pending({
        "text": post_text,
        "image_path": image_path,
        "pillar": pillar,
        "pattern": label,
        "pipeline": "P3",
        "sub_theme": sub_theme,
        "quality_score": selected["quality_score"],
        "created_at": datetime.now(JST).isoformat(),
    })

    # Step 6: Send LINE notification for approval
    notify_for_approval(selected, pillar, sub_theme)
    logger.info("=== Pending approval. Use --approve to post. ===")


if __name__ == "__main__":
    main()
