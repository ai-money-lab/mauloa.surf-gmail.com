"""
STRATEGY FEEDBACK — 議論結果からコンテンツ戦略を自動調整

debate結果 → 次回の生成キューへ反映するフィードバックループ。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("nexus.v2.strategy_feedback")


class StrategyFeedback:
    """Read debate results and produce an optimized creation queue."""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path("nexus/data/v2")

    def load_latest_debate(self) -> dict | None:
        """Load the most recent debate file."""
        debate_dir = self.data_dir / "debate"
        if not debate_dir.exists():
            return None

        files = sorted(debate_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not files:
            return None

        try:
            return json.loads(files[0].read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to load debate: %s", e)
            return None

    def load_existing_assets(self) -> list[dict]:
        """Load existing generated assets."""
        content_dir = self.data_dir / "content"
        if not content_dir.exists():
            return []

        assets = []
        for f in content_dir.glob("*.json"):
            try:
                assets.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                continue
        return assets

    def generate_optimized_queue(self) -> list[dict[str, Any]]:
        """Generate creation queue optimized by debate insights.

        Returns a prioritized list of asset specs based on:
        1. Debate channel priority ranking
        2. Gaps in existing portfolio
        3. Phase-appropriate timing
        """
        debate = self.load_latest_debate()
        existing = self.load_existing_assets()
        existing_types = {_guess_type(a) for a in existing}

        queue = []

        if debate:
            queue = self._queue_from_debate(debate, existing_types)

        if not queue:
            queue = self._default_queue(existing_types)

        # Save the queue for transparency
        queue_file = self.data_dir / "creation_queue.json"
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        queue_file.write_text(
            json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Generated optimized queue: %d items", len(queue))
        return queue

    def _queue_from_debate(self, debate: dict, existing_types: set[str]) -> list[dict]:
        """Build queue from debate priorities."""
        queue = []
        synthesis = debate.get("debate_synthesis", {})
        ranking = synthesis.get("confidence_weighted_ranking", {})
        channel_priority = ranking.get("channel_priority", [])

        # Map debate channels to asset specs
        channel_to_assets = {
            "YouTube Faceless Channel": [
                {"asset_type": "video_script", "theme": "不動産投資で失敗する人の共通パターン5選", "priority": 10},
                {"asset_type": "video_script", "theme": "AI時代の不動産業務DX — 現場で使えるツール紹介", "priority": 9},
            ],
            "Gumroad Digital Products": [
                {"asset_type": "template", "theme": "不動産投資収支シミュレーションNotionテンプレート", "priority": 10},
                {"asset_type": "prompt_pack", "theme": "不動産業務効率化AIプロンプト集100選", "priority": 8},
                {"asset_type": "ebook", "theme": "はじめての不動産投資 — 現役20年プロが教える判断基準", "priority": 7},
            ],
            "AI Music (Spotify/DSP)": [
                {"asset_type": "music_track", "theme": "Lo-fi ambient study beats — Rainy Day Collection", "priority": 6},
                {"asset_type": "music_track", "theme": "Meditation ambient — Deep Focus Series", "priority": 5},
            ],
            "Stock Assets (Adobe/Shutterstock)": [
                {"asset_type": "stock_image", "theme": "Modern Japanese real estate and urban architecture", "priority": 5},
                {"asset_type": "stock_image", "theme": "Business technology and AI concept visuals", "priority": 4},
            ],
            "Micro-SaaS": [
                {"asset_type": "api_service", "theme": "不動産物件レポート自動生成API — PropReport", "priority": 3},
            ],
        }

        for item in channel_priority:
            channel_name = item.get("channel", "")
            specs = channel_to_assets.get(channel_name, [])
            for spec in specs:
                if spec["asset_type"] not in existing_types or spec["priority"] >= 8:
                    queue.append(spec)

        # Sort by priority
        queue.sort(key=lambda x: -x.get("priority", 0))
        return queue[:7]

    def _default_queue(self, existing_types: set[str]) -> list[dict]:
        """Fallback queue when no debate is available."""
        defaults = [
            {"asset_type": "video_script", "theme": "不動産投資初心者が知るべき5つの真実", "priority": 10},
            {"asset_type": "template", "theme": "不動産投資収支計算Notionテンプレート", "priority": 9},
            {"asset_type": "music_track", "theme": "Lo-fi hip hop beats for studying and relaxation", "priority": 7},
            {"asset_type": "stock_image", "theme": "Modern real estate and architecture concepts", "priority": 6},
            {"asset_type": "prompt_pack", "theme": "不動産業務効率化AIプロンプト50選", "priority": 5},
        ]
        return [d for d in defaults if d["asset_type"] not in existing_types or d["priority"] >= 8]

    def get_phase_recommendation(self) -> dict:
        """Get current phase recommendation based on debate."""
        debate = self.load_latest_debate()
        if not debate:
            return {"phase": 1, "focus": ["YouTube", "Gumroad"], "note": "No debate data"}

        plan = debate.get("final_action_plan", {})
        phases = plan.get("phases", [])

        # Default to phase 1
        return {
            "phase": 1,
            "focus": phases[0].get("focus_channels", []) if phases else ["YouTube", "Gumroad"],
            "milestones": phases[0].get("milestones", []) if phases else [],
            "expected_revenue": phases[0].get("expected_revenue_month3", "$0") if phases else "$0",
        }


def _guess_type(asset: dict) -> str:
    """Guess asset type from structure."""
    if "tracks" in asset:
        return "music_track"
    if "script" in asset:
        return "video_script"
    if "sales_page" in asset:
        return "template"
    if "assets" in asset and isinstance(asset.get("assets"), list):
        return "stock_image"
    if "api_endpoints" in asset:
        return "api_service"
    return "unknown"
