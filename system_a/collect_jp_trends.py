"""Collect Japanese domestic trends and news for Pipeline 2."""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from core.claude_client import ClaudeClient

load_dotenv()

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "system_a" / "pipeline2" / "sources"

REAL_ESTATE_KEYWORDS = [
    "不動産", "住宅", "マンション", "賃貸", "リフォーム",
    "住み替え", "金利", "投資", "空き家", "再開発",
    "地価", "建築", "間取り", "防犯", "MATTERPORT",
]

NEWS_SOURCES = [
    {
        "name": "yahoo_news_realestate",
        "url": "https://news.yahoo.co.jp/categories/business",
        "type": "html",
    },
    {
        "name": "mlit_updates",
        "url": "https://www.mlit.go.jp/report/press/",
        "type": "html",
    },
]


class JpTrendsCollector:
    """Collect Japanese real estate trends and news."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.user_agent = "HIROKI-AI-Research/1.0"

    def _fetch_html(self, url: str) -> str:
        """Fetch HTML content from URL."""
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

    def collect_news(self) -> list:
        """Collect news from configured sources."""
        articles = []
        for source in NEWS_SOURCES:
            html = self._fetch_html(source["url"])
            if not html:
                continue
            soup = BeautifulSoup(html, "lxml")
            # Extract headlines
            for tag in soup.find_all(["h2", "h3", "a"], limit=50):
                text = tag.get_text(strip=True)
                if any(kw in text for kw in REAL_ESTATE_KEYWORDS):
                    href = tag.get("href", "")
                    articles.append({
                        "source": source["name"],
                        "title": text,
                        "url": href,
                        "collected_at": datetime.now(JST).isoformat(),
                    })
        return articles

    def collect_x_trends(self) -> list:
        """Collect X (Twitter) trending topics in Japan."""
        api_key = os.getenv("TWITTERAPI_IO_KEY", "")
        if not api_key:
            return []

        try:
            resp = requests.get(
                "https://api.twitterapi.io/twitter/trends/",
                headers={"X-API-Key": api_key},
                params={"country": "japan"},
                timeout=15,
            )
            resp.raise_for_status()
            trends = resp.json().get("trends", [])
            # Filter for relevant topics
            relevant = []
            for t in trends:
                name = t.get("name", "")
                if any(kw in name for kw in REAL_ESTATE_KEYWORDS):
                    relevant.append({
                        "trend": name,
                        "volume": t.get("tweet_volume", 0),
                    })
            return relevant
        except Exception as e:
            logger.warning("X trends collection failed: %s", e)
            return []

    def filter_with_ai(self, items: list) -> list:
        """Quick AI filter: is this usable as a post topic?"""
        if not items:
            return []

        prompt = (
            "以下のニュース/トレンドのリストから、X投稿のネタになりそうなものを選んでください。\n"
            "不動産・住宅・暮らし・投資・テクノロジーに関連するものを優先。\n"
            "各アイテムに対して usable: true/false を判定してください。\n"
            "JSON配列で出力。\n\n"
            f"{json.dumps(items, ensure_ascii=False, indent=2)}"
        )

        try:
            result = self.claude.generate_json(prompt, temperature=0.2)
            if isinstance(result, list):
                return [r for r in result if r.get("usable")]
            return []
        except Exception:
            return items  # Fallback: return all

    def collect_system_c_data(self) -> list:
        """Load latest data from System C if available."""
        system_c_dir = BASE_DIR / "data" / "system_c"
        data = []

        for subdir in ["daily", "weekly"]:
            path = system_c_dir / subdir
            if not path.exists():
                continue
            files = sorted(path.glob("*.json"), reverse=True)
            if files:
                try:
                    content = json.loads(files[0].read_text(encoding="utf-8"))
                    data.append({
                        "source": f"system_c_{subdir}",
                        "file": files[0].name,
                        "data": content,
                    })
                except Exception as e:
                    logger.warning("Failed to load System C data: %s", e)

        return data

    def run(self) -> dict:
        """Collect all trend sources and save."""
        logger.info("Collecting JP trends and news...")

        news = self.collect_news()
        trends = self.collect_x_trends()
        system_c = self.collect_system_c_data()

        all_items = news + [{"source": "x_trend", **t} for t in trends]
        filtered = self.filter_with_ai(all_items)

        output = {
            "collected_at": datetime.now(JST).isoformat(),
            "news": news,
            "x_trends": trends,
            "system_c_data": system_c,
            "filtered_items": filtered,
        }

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now(JST).strftime("%Y-%m-%d")
        out_path = DATA_DIR / f"{today}.json"
        out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Trends collected -> %s", out_path)
        return output


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    collector = JpTrendsCollector()
    collector.run()
