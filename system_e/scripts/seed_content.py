"""System E — Seed Content Generator.

Generate the first week of content plans and images for launch.
This pre-populates the content queue so System E can start posting immediately.

Usage:
    # Generate 7 days of content plans (text only, no images):
    PYTHONPATH=. python system_e/scripts/seed_content.py --days 7

    # Generate content + images:
    PYTHONPATH=. python system_e/scripts/seed_content.py --days 7 --images

    # Generate content + images for specific dates:
    PYTHONPATH=. python system_e/scripts/seed_content.py --start 2026-03-20 --days 7 --images

    # Dry run (preview content plan without generation):
    PYTHONPATH=. python system_e/scripts/seed_content.py --days 3 --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
GENERATED_DIR = Path(__file__).parent.parent.parent / "data" / "system_e" / "generated"


def main():
    parser = argparse.ArgumentParser(description="Seed content for System E launch")
    parser.add_argument("--days", type=int, default=7, help="Number of days to generate (default: 7)")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD, default: tomorrow)")
    parser.add_argument("--images", action="store_true", help="Also generate images for each content item")
    parser.add_argument("--dry-run", action="store_true", help="Preview plan without generating")
    args = parser.parse_args()

    # Calculate date range
    if args.start:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=JST)
    else:
        start_date = datetime.now(JST) + timedelta(days=1)

    dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(args.days)]

    print(f"\n{'=' * 60}")
    print(f" System E — Seed Content Generator")
    print(f" Dates: {dates[0]} → {dates[-1]} ({len(dates)} days)")
    print(f" Images: {'Yes' if args.images else 'No'}")
    print(f" Dry run: {'Yes' if args.dry_run else 'No'}")
    print(f"{'=' * 60}\n")

    if args.dry_run:
        _preview_plan(dates)
        return

    # Import here to avoid loading heavy modules for dry-run
    from system_e.content_generator import ContentGenerator
    content_gen = ContentGenerator()

    image_pipeline = None
    if args.images:
        from system_e.image_pipeline import ImagePipeline
        image_pipeline = ImagePipeline()
        if not image_pipeline.enabled:
            logger.warning("Image pipeline not enabled. Generating text content only.")
            image_pipeline = None

    total_items = 0
    total_images = 0

    for date in dates:
        plan_file = GENERATED_DIR / f"content_plan_{date}.json"
        if plan_file.exists():
            logger.info("Skipping %s — plan already exists", date)
            continue

        logger.info("Generating content for %s...", date)
        plan = content_gen.generate_daily_content_plan(date)
        total_items += len(plan)

        for item in plan:
            text = item.get("text", "")[:60]
            time_jst = item.get("scheduled_time_jst", "??:??")
            logger.info("  [%s] %s: %s...", time_jst, item.get("type", "?"), text)

        # Generate images if requested
        if image_pipeline and plan:
            for item in plan:
                scene = item.get("scene", "lifestyle")
                try:
                    image_path = image_pipeline.generate_for_scene(
                        scene=scene, aspect_ratio="16:9",
                    )
                    if image_path:
                        item["image_path"] = image_path
                        total_images += 1
                except Exception as e:
                    logger.error("Image gen failed for %s/%s: %s", date, scene, e)

            # Re-save plan with image paths
            plan_file.write_text(
                json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    print(f"\n{'=' * 60}")
    print(f" Seed Generation Complete")
    print(f" Content items: {total_items}")
    print(f" Images: {total_images}")
    print(f" Content dir: {GENERATED_DIR}")
    print(f"{'=' * 60}")


def _preview_plan(dates: list[str]):
    """Preview the content schedule without generating."""
    # Content mix from ContentGenerator
    content_slots = [
        {"time": "07:00", "type": "standard", "scene": "morning_routine", "note": "Asia peak"},
        {"time": "12:00", "type": "engagement", "scene": "lifestyle", "note": "Asia lunch"},
        {"time": "19:00", "type": "standard", "scene": "(random)", "note": "EU morning + Asia evening"},
        {"time": "23:00", "type": "story", "scene": "(random)", "note": "US West morning"},
    ]

    for date in dates:
        plan_file = GENERATED_DIR / f"content_plan_{date}.json"
        exists = plan_file.exists()
        status = " (EXISTS — will skip)" if exists else ""
        print(f"\n--- {date}{status} ---")
        if not exists:
            for slot in content_slots:
                print(f"  [{slot['time']}] {slot['type']:11s} | {slot['scene']:16s} | {slot['note']}")

    total_new = sum(1 for d in dates if not (GENERATED_DIR / f"content_plan_{d}.json").exists())
    print(f"\n{total_new} days to generate ({total_new * 4} content items)")


if __name__ == "__main__":
    sys.exit(main() or 0)
