"""Regulation Watch Agent.

Monitors legal changes, new subsidies, and regulatory updates
affecting real estate.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from core.claude_client import ClaudeClient

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "system_c"

WATCH_URLS = [
    {
        "name": "国交省プレスリリース",
        "url": "https://www.mlit.go.jp/report/press/",
        "keywords": ["不動産", "住宅", "建築", "宅建", "地価", "補助金"],
    },
]


class RegulationWatchAgent:
    """Monitor regulatory changes affecting real estate."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.user_agent = "HIROKI-AI-Research/1.0"

    def _fetch(self, url: str) -> str:
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": self.user_agent},
                timeout=15,
            )
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            return resp.text
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", url, e)
            return ""

    def check_sources(self) -> list:
        """Check all configured sources for updates."""
        findings = []

        for source in WATCH_URLS:
            html = self._fetch(source["url"])
            if not html:
                continue

            soup = BeautifulSoup(html, "lxml")
            for tag in soup.find_all(["h2", "h3", "a", "li"], limit=100):
                text = tag.get_text(strip=True)
                if any(kw in text for kw in source["keywords"]):
                    findings.append({
                        "source": source["name"],
                        "title": text[:200],
                        "url": tag.get("href", ""),
                        "checked_at": datetime.now(JST).isoformat(),
                    })

        return findings

    def analyze_impact(self, findings: list) -> dict:
        """Analyze the impact of regulatory changes."""
        if not findings:
            return {"findings": [], "analysis": "No notable changes detected"}

        prompt = (
            "以下の法規制関連の更新情報について、不動産業界への影響を分析してください。\n"
            "JSON形式で出力: each item should have impact_level, summary, action_items\n\n"
            f"{json.dumps(findings, ensure_ascii=False, indent=2)}"
        )

        try:
            analysis = self.claude.generate_json(prompt, temperature=0.3)
        except Exception as e:
            logger.warning("Impact analysis failed: %s", e)
            analysis = {"error": str(e)}

        return {
            "findings": findings,
            "analysis": analysis,
            "checked_at": datetime.now(JST).isoformat(),
        }

    def run_daily(self) -> dict:
        """Run daily regulation watch."""
        logger.info("Running daily regulation watch...")
        findings = self.check_sources()
        result = self.analyze_impact(findings)
        logger.info("Found %d regulatory updates", len(findings))
        return result
