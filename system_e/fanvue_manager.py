"""System E — Fanvue Content Manager.

Manages content creation and organization for Fanvue subscription platform.
Separates content into tiers (free, basic, premium, VIP).
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from core.claude_client import ClaudeClient

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
CONFIG_PATH = Path(__file__).parent / "character_config.yaml"
FANVUE_DIR = Path(__file__).parent.parent / "data" / "system_e" / "fanvue"


def load_character_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


class FanvueManager:
    """Manage content pipeline for Fanvue subscription tiers."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.config = load_character_config()
        self.tiers = self.config["monetization"]["fanvue_tiers"]
        FANVUE_DIR.mkdir(parents=True, exist_ok=True)

    def categorize_content(self, image_path: str, scene: str) -> str:
        """Determine which Fanvue tier an image belongs to.

        Args:
            image_path: Path to the generated image.
            scene: Scene category used for generation.

        Returns:
            Tier name: 'free', 'basic', 'premium', or 'vip'.
        """
        # Tier logic based on scene exclusivity
        premium_scenes = {"studio", "workout"}
        basic_scenes = {"morning_routine", "outdoor", "lifestyle"}

        if scene in premium_scenes:
            return "premium"
        elif scene in basic_scenes:
            return "basic"
        return "free"

    def prepare_fanvue_post(
        self,
        image_path: str,
        scene: str,
        caption: str = "",
    ) -> dict:
        """Prepare a content item for Fanvue posting.

        Args:
            image_path: Path to the image file.
            scene: Scene category.
            caption: Optional caption (will generate one if empty).

        Returns:
            Dict with all info needed to post to Fanvue.
        """
        tier = self.categorize_content(image_path, scene)

        if not caption:
            caption = self._generate_fanvue_caption(scene, tier)

        post = {
            "image_path": image_path,
            "caption": caption,
            "tier": tier,
            "scene": scene,
            "created_at": datetime.now(JST).isoformat(),
            "status": "ready",
        }

        # Save to queue
        self._add_to_queue(post)
        return post

    def _generate_fanvue_caption(self, scene: str, tier: str) -> str:
        """Generate a Fanvue-appropriate caption.

        Fanvue captions are more personal/exclusive than X posts.
        """
        char = self.config["character"]

        tier_vibes = {
            "free": "casual preview that teases exclusive content",
            "basic": "personal and behind-the-scenes, like talking to a close friend",
            "premium": "exclusive and intimate, sharing something special",
            "vip": "very personal, like a private message to your closest supporter",
        }

        vibe = tier_vibes.get(tier, tier_vibes["basic"])

        prompt = f"""Write a short Fanvue caption (2-3 sentences, max 200 chars) for a {scene} photo.

Vibe: {vibe}
Tier: {tier} ({"free — visible to everyone" if tier == "free" else f"${self.tiers[tier]['price']}/month subscribers only"})

Make it feel exclusive and personal. No hashtags needed.
Return just the caption text, nothing else."""

        try:
            system = (
                f"You are {char['name']}, {char['tagline']}. "
                f"Personality: {', '.join(char['personality']['traits'])}. "
                f"Write as yourself in first person."
            )
            return self.claude.generate(
                prompt=prompt,
                system=system,
                max_tokens=256,
                temperature=0.8,
            ).strip().strip('"')
        except Exception as e:
            logger.error("Fanvue caption generation failed: %s", e)
            return f"New {scene} content just dropped! ✨"

    def _add_to_queue(self, post: dict) -> None:
        """Add a post to the Fanvue posting queue."""
        queue_file = FANVUE_DIR / "posting_queue.json"
        existing = []
        if queue_file.exists():
            try:
                existing = json.loads(queue_file.read_text(encoding="utf-8"))
            except Exception:
                existing = []

        existing.append(post)
        queue_file.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Added to Fanvue queue: tier=%s, scene=%s", post["tier"], post["scene"])

    def get_queue(self, tier: str | None = None) -> list[dict]:
        """Get pending Fanvue posts, optionally filtered by tier."""
        queue_file = FANVUE_DIR / "posting_queue.json"
        if not queue_file.exists():
            return []

        try:
            queue = json.loads(queue_file.read_text(encoding="utf-8"))
        except Exception:
            return []

        if tier:
            return [p for p in queue if p.get("tier") == tier and p.get("status") == "ready"]
        return [p for p in queue if p.get("status") == "ready"]

    def mark_posted(self, index: int) -> None:
        """Mark a queue item as posted."""
        queue_file = FANVUE_DIR / "posting_queue.json"
        if not queue_file.exists():
            return

        queue = json.loads(queue_file.read_text(encoding="utf-8"))
        if 0 <= index < len(queue):
            queue[index]["status"] = "posted"
            queue[index]["posted_at"] = datetime.now(JST).isoformat()
            queue_file.write_text(
                json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    def get_tier_stats(self) -> dict:
        """Get content statistics per tier."""
        queue_file = FANVUE_DIR / "posting_queue.json"
        if not queue_file.exists():
            return {}

        try:
            queue = json.loads(queue_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

        stats = {}
        for item in queue:
            tier = item.get("tier", "unknown")
            status = item.get("status", "unknown")
            if tier not in stats:
                stats[tier] = {"ready": 0, "posted": 0}
            stats[tier][status] = stats[tier].get(status, 0) + 1

        return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager = FanvueManager()
    stats = manager.get_tier_stats()
    print("Fanvue queue stats:", json.dumps(stats, indent=2))
