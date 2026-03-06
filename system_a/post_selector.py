"""Post selector: pools candidates from 3 pipelines,
applies quality checks, and selects 3 posts per day
with pillar balance and pipeline ratio optimization.
"""

import json
import logging
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from core.quality_checker import QualityChecker
from core.claude_client import ClaudeClient
from core.fact_checker import FactChecker

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "system_a"
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"

TARGET_PILLAR_RATIO = {1: 0.30, 2: 0.25, 3: 0.20, 4: 0.15, 5: 0.10}


class PostSelector:
    """Select daily posts from the candidate pool."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.quality_checker = QualityChecker(self.claude)
        self.fact_checker = FactChecker()
        self._load_config()

    def _load_config(self):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
        except Exception:
            self.config = {}

        sa = self.config.get("system_a", {})
        self.posts_per_day = sa.get("posts_per_day", 3)
        self.post_times = sa.get("post_times", ["07:00", "12:00", "19:00"])

        ratio = sa.get("pipeline_ratio", {})
        self.pipeline_ratio = {
            "P1": ratio.get("pipeline1_jp_buzz", 40) / 100,
            "P2": ratio.get("pipeline2_data_driven", 35) / 100,
            "P3": ratio.get("pipeline3_ai_original", 25) / 100,
        }

    def load_candidates(self, date_str: str = None) -> list:
        """Load all pipeline outputs for a given date."""
        if not date_str:
            date_str = datetime.now(JST).strftime("%Y-%m-%d")

        candidates = []
        pipelines = [
            ("pipeline1", "generated"),
            ("pipeline2", "generated"),
            ("pipeline3", "generated"),
        ]

        for pipeline_dir, sub in pipelines:
            path = DATA_DIR / pipeline_dir / sub / f"{date_str}.json"
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        candidates.extend(data)
                except Exception as e:
                    logger.warning("Failed to load %s: %s", path, e)

        return candidates

    def _extract_posts(self, candidate: dict) -> list:
        """Extract individual post texts from a candidate (may have patterns A/B/C)."""
        posts = []
        for pattern_key in ["pattern_a", "pattern_b", "pattern_c", "A", "B", "C"]:
            if pattern_key in candidate:
                post = candidate[pattern_key]
                text = post if isinstance(post, str) else post.get("text", "")
                if text:
                    posts.append({
                        "text": text,
                        "pattern": pattern_key.replace("pattern_", "").upper(),
                        "pipeline": candidate.get("pipeline", "unknown"),
                        "pillar": candidate.get("theme", {}).get("pillar_number",
                                  candidate.get("pillar", 0)),
                        "metadata": candidate,
                    })
        # Fallback: if no patterns found, use text directly
        if not posts and "text" in candidate:
            posts.append({
                "text": candidate["text"],
                "pattern": "A",
                "pipeline": candidate.get("pipeline", "unknown"),
                "pillar": candidate.get("theme", {}).get("pillar_number",
                          candidate.get("pillar", 0)),
                "metadata": candidate,
            })
        return posts

    def quality_check_all(self, candidates: list) -> list:
        """Run quality checks and fact checks on all candidates."""
        approved = []
        for candidate in candidates:
            posts = self._extract_posts(candidate)
            for post in posts:
                text = post["text"]

                # Step 1: Auto-fix known typos before checking
                text = self.fact_checker.auto_fix(text)
                post["text"] = text

                # Step 2: Fact check — reject fabricated content
                fact_result = self.fact_checker.check(text)
                if not fact_result.passed:
                    logger.warning(
                        "Fact check REJECTED: P%s pillar%s — %s",
                        post["pipeline"], post["pillar"],
                        "; ".join(v["message"] for v in fact_result.violations),
                    )
                    post["quality_result"] = {
                        "result": "rejected",
                        "rejection_reasons": [v["message"] for v in fact_result.violations],
                        "total_score": 0,
                    }
                    continue

                # Step 3: Quality check
                result = self.quality_checker.check(
                    profile="x_post",
                    content=text,
                    context=f"Pipeline: {post['pipeline']}, Pillar: {post['pillar']}",
                )
                post["quality_result"] = result
                if result.get("result") == "auto_approved":
                    post["quality_score"] = result.get("total_score", 0)
                    approved.append(post)
                else:
                    logger.info(
                        "Rejected: P%s pillar%s score=%s",
                        post["pipeline"], post["pillar"],
                        result.get("total_score", 0),
                    )
        return approved

    def select_with_pillar_balance(self, approved: list) -> list:
        """Select posts maintaining pillar ratio balance."""
        if len(approved) <= self.posts_per_day:
            return approved

        # Load last 7 days history for pillar balance
        history_path = DATA_DIR / "post_history.json"
        recent_pillars = Counter()
        if history_path.exists():
            try:
                history = json.loads(history_path.read_text(encoding="utf-8"))
                cutoff = (datetime.now(JST) - timedelta(days=7)).isoformat()
                for entry in history:
                    if entry.get("date", "") >= cutoff:
                        recent_pillars[entry.get("pillar_number", 0)] += 1
            except Exception:
                pass

        # Calculate deficit: which pillars are underrepresented
        total_recent = sum(recent_pillars.values()) or 1
        deficit = {}
        for pillar, target in TARGET_PILLAR_RATIO.items():
            actual = recent_pillars.get(pillar, 0) / total_recent
            deficit[pillar] = target - actual

        # Sort approved by deficit (prioritize underrepresented pillars)
        approved.sort(
            key=lambda p: (
                -deficit.get(p.get("pillar", 0), 0),
                -p.get("quality_score", 0),
            )
        )
        return approved[:self.posts_per_day]

    def assign_time_slots(self, selected: list) -> list:
        """Assign posting times to selected posts."""
        for i, post in enumerate(selected):
            if i < len(self.post_times):
                post["scheduled_time"] = self.post_times[i]
            else:
                post["scheduled_time"] = self.post_times[-1]
        return selected

    def _text_key(self, post: dict) -> str:
        """Get hashable text key from post (text may be str or list)."""
        text = post.get("text", "")
        return "\n".join(text) if isinstance(text, list) else text

    def save_stock_pool(self, approved: list, selected: list) -> None:
        """Save unused approved candidates to stock pool."""
        selected_texts = {self._text_key(p) for p in selected}
        stock = [p for p in approved if self._text_key(p) not in selected_texts]

        if stock:
            stock_dir = DATA_DIR / "stock_pool"
            stock_dir.mkdir(parents=True, exist_ok=True)
            today = datetime.now(JST).strftime("%Y-%m-%d")
            path = stock_dir / f"{today}.json"
            path.write_text(json.dumps(stock, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("Saved %d posts to stock pool", len(stock))

    def run(self) -> list:
        """Execute full selection pipeline."""
        logger.info("PostSelector: Loading candidates...")
        candidates = self.load_candidates()
        logger.info("PostSelector: %d candidates loaded", len(candidates))

        logger.info("PostSelector: Running quality checks...")
        approved = self.quality_check_all(candidates)
        logger.info("PostSelector: %d approved", len(approved))

        logger.info("PostSelector: Selecting with pillar balance...")
        selected = self.select_with_pillar_balance(approved)

        selected = self.assign_time_slots(selected)
        self.save_stock_pool(approved, selected)

        logger.info(
            "PostSelector: Selected %d posts for today: %s",
            len(selected),
            [(p.get("pipeline"), p.get("pillar"), p.get("scheduled_time")) for p in selected],
        )
        return selected


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    selector = PostSelector()
    selector.run()
