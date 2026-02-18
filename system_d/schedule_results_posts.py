"""Schedule System D results posts into System A's posting pipeline."""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from system_d.generate_results_content import ResultsContentGenerator

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"


class ResultsPostScheduler:
    """Merge System D posts into System A's schedule."""

    def __init__(self):
        self.generator = ResultsContentGenerator()
        self._load_config()

    def _load_config(self):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            self.posts_per_week = cfg.get("system_d", {}).get("results_posts_per_week", 4)
            self.target_pillars = cfg.get("system_d", {}).get("target_pillars", [3, 5])
        except Exception:
            self.posts_per_week = 4
            self.target_pillars = [3, 5]

    def generate_and_schedule(self) -> list:
        """Generate results posts and inject into System A pipeline."""
        posts = self.generator.run()

        # Select up to posts_per_week posts
        selected = posts[:self.posts_per_week]

        # Save to System A's pipeline data for pickup by post_selector
        today = datetime.now(JST).strftime("%Y-%m-%d")
        out_dir = BASE_DIR / "data" / "system_a" / "pipeline3" / "generated"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Append to existing pipeline3 data (or create new)
        existing_path = out_dir / f"{today}.json"
        existing = []
        if existing_path.exists():
            try:
                existing = json.loads(existing_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Tag System D posts
        for post in selected:
            post["pipeline"] = "D"

        combined = existing + selected
        existing_path.write_text(
            json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        logger.info(
            "Scheduled %d System D posts (target pillars: %s)",
            len(selected), self.target_pillars,
        )
        return selected

    def run(self) -> list:
        """Execute scheduling."""
        return self.generate_and_schedule()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scheduler = ResultsPostScheduler()
    scheduler.run()
