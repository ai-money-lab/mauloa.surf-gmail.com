"""PropTech Scout Agent.

Tracks latest technology trends in AI x Real Estate,
MATTERPORT, and PropTech space.
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

from core.claude_client import ClaudeClient
from core.quality_checker import QualityChecker

load_dotenv()

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "system_c"

SEARCH_TOPICS = [
    "PropTech 不動産テック 最新",
    "MATTERPORT 3Dスキャン 不動産",
    "AI 不動産 活用事例",
    "不動産DX デジタルトランスフォーメーション",
    "AI防犯カメラ 最新技術",
    "VR内見 バーチャル内見",
]


class TechTrendAgent:
    """Scout PropTech and AI x Real Estate trends."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.quality_checker = QualityChecker(self.claude)
        self.twitter_api_key = os.getenv("TWITTERAPI_IO_KEY", "")

    def search_x_for_trends(self) -> list:
        """Search X for PropTech trends."""
        if not self.twitter_api_key:
            return []

        results = []
        for topic in SEARCH_TOPICS[:3]:
            try:
                resp = requests.get(
                    "https://api.twitterapi.io/twitter/tweet/advanced_search",
                    headers={"X-API-Key": self.twitter_api_key},
                    params={
                        "query": f"{topic} lang:ja min_faves:100",
                        "queryType": "Latest",
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                tweets = resp.json().get("tweets", [])
                for t in tweets[:5]:
                    results.append({
                        "source": "x_search",
                        "topic": topic,
                        "text": t.get("text", ""),
                        "likes": t.get("likeCount", 0),
                        "author": t.get("author", {}).get("userName", ""),
                    })
            except Exception as e:
                logger.warning("X search failed for '%s': %s", topic, e)

        return results

    def generate_weekly_report(self, raw_data: list = None) -> dict:
        """Generate weekly tech trends report."""
        logger.info("Generating weekly tech trends report...")

        if raw_data is None:
            raw_data = self.search_x_for_trends()

        prompt = (
            "以下の情報源を基に、不動産テック（PropTech）の週次トレンドレポートを作成してください。\n"
            "JSON形式で出力:\n"
            "- trends: [{title, summary, relevance_score(1-10), source}]\n"
            "- key_insight: 最も注目すべきポイント\n"
            "- hiroki_opportunities: HIROKIのビジネスに活かせる機会\n\n"
            f"収集データ:\n{json.dumps(raw_data, ensure_ascii=False, indent=2)[:3000]}"
        )

        try:
            report = self.claude.generate_json(prompt, temperature=0.4)
        except Exception as e:
            logger.error("Tech report generation failed: %s", e)
            report = {"error": str(e)}

        output = {
            "type": "weekly_tech_trends",
            "date": datetime.now(JST).isoformat(),
            "raw_data_count": len(raw_data),
            "report": report,
        }

        # Quality check
        qr = self.quality_checker.check(
            profile="data_collection",
            content=json.dumps(output, ensure_ascii=False),
            context="Weekly tech trends report",
        )
        output["quality_check"] = qr

        # Save
        output_dir = DATA_DIR / "weekly"
        output_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(JST).strftime("%Y-%m-%d")
        path = output_dir / f"tech_trends_{date_str}.json"
        path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Weekly tech report saved: %s", path)
        return output

    def run(self) -> dict:
        """Execute tech trend collection and reporting."""
        raw = self.search_x_for_trends()
        return self.generate_weekly_report(raw)
