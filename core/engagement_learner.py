"""Engagement learner — analyzes popular posts and learns what works.

Fetches top-performing posts from X (own and industry), analyzes WHY
they resonate, and feeds those insights back into content generation.
"""

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

from core.claude_client import ClaudeClient

load_dotenv()

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "system_a"
INSIGHTS_PATH = DATA_DIR / "engagement_insights.json"
WINNING_PATTERNS_PATH = DATA_DIR / "winning_patterns.json"
POSTED_LOG_PATH = DATA_DIR / "posted_tweets.json"

ANALYSIS_PROMPT = """\
あなたは投稿コンテンツの専門アナリストです。

以下の投稿データを分析して、なぜ人気が高いのかを具体的に解析してください。

## 分析対象:
{posts_json}

## 分析項目:
1. **フック（1行目）の効果**: なぜ読者が止まったのか
2. **構造パターン**: 情報の出し方・順序に法則はあるか
3. **感情トリガー**: どんな感情を刺激しているか（共感・驚き・安心・危機感）
4. **実用性**: 読んだ人が具体的に何ができるようになるか
5. **投稿形式**: 長さ・改行・リスト型・スレッド型どれが効果的か
6. **CTA（締め方）**: どんな終わり方がエンゲージメントを高めているか
7. **テーマの普遍性**: なぜこのテーマが多くの人に刺さったのか

## 学びの抽出:
分析結果から、今後の投稿生成に活かせる具体的な「ルール」を抽出してください。
抽象的な分析ではなく、すぐに使える実用的な教訓を出してください。

## 出力（JSON形式のみ）:
```json
{
  "analysis_date": "YYYY-MM-DD",
  "posts_analyzed": 件数,
  "top_patterns": [
    {
      "pattern_name": "パターン名",
      "description": "どういうパターンか",
      "example_hook": "具体的な1行目の例",
      "effectiveness": "なぜ効果的か",
      "applicable_pillars": [使える柱番号]
    }
  ],
  "key_learnings": [
    {
      "learning": "具体的な教訓",
      "action": "投稿生成時にどう活かすか",
      "priority": "high/medium/low"
    }
  ],
  "avoid_patterns": [
    {
      "pattern": "避けるべきパターン",
      "reason": "なぜ効果が低いか"
    }
  ],
  "recommended_themes": [
    {
      "theme": "今後取り上げるべきテーマ",
      "reason": "なぜ需要がありそうか",
      "pillar": 柱番号
    }
  ]
}
```
"""


class EngagementLearner:
    """Analyze popular posts, learn patterns, and improve future content."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.api_key = os.getenv("TWITTERAPI_IO_KEY", "")
        self.bearer_token = os.getenv("X_BEARER_TOKEN", "")

    def fetch_own_top_posts(self, days: int = 30, min_likes: int = 5) -> list:
        """Get our own top-performing posts from the local log."""
        if not POSTED_LOG_PATH.exists():
            return []

        try:
            all_posts = json.loads(POSTED_LOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []

        cutoff = datetime.now(JST) - timedelta(days=days)
        recent = []
        for post in all_posts:
            try:
                posted_at = datetime.fromisoformat(post["datetime"])
                if posted_at >= cutoff:
                    recent.append(post)
            except (KeyError, ValueError):
                continue

        # Enrich with metrics
        enriched = []
        for post in recent:
            tweet_id = post.get("tweet_id", "")
            if tweet_id and self.bearer_token:
                metrics = self._fetch_metrics(tweet_id)
                post.update(metrics)
            enriched.append(post)

        # Filter by minimum engagement
        top = [p for p in enriched if p.get("likes", 0) >= min_likes]
        top.sort(key=lambda p: p.get("likes", 0) + p.get("retweets", 0), reverse=True)
        return top[:20]

    def fetch_industry_top_posts(self, count: int = 20) -> list:
        """Fetch popular real estate posts from X for learning."""
        if not self.api_key:
            logger.warning("TWITTERAPI_IO_KEY not set, skipping industry fetch")
            return []

        queries = [
            "不動産 min_faves:500 lang:ja -is:reply -is:quote",
            "賃貸管理 OR 売却 OR 相続 min_faves:300 lang:ja -is:reply -is:quote",
            "部屋探し OR 引越し min_faves:500 lang:ja -is:reply -is:quote",
        ]

        all_tweets = []
        for query in queries:
            url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
            headers = {"X-API-Key": self.api_key}
            params = {"query": query, "queryType": "Top", "cursor": ""}

            try:
                resp = requests.get(url, headers=headers, params=params, timeout=30)
                resp.raise_for_status()
                tweets = resp.json().get("tweets", [])
                for t in tweets:
                    all_tweets.append({
                        "text": t.get("text", ""),
                        "likes": t.get("likeCount", 0),
                        "retweets": t.get("retweetCount", 0),
                        "replies": t.get("replyCount", 0),
                        "author": t.get("author", {}).get("userName", ""),
                    })
            except Exception as e:
                logger.warning("Industry search failed for query: %s", e)

        # Deduplicate and sort
        seen = set()
        unique = []
        for t in all_tweets:
            text_key = t["text"][:50]
            if text_key not in seen:
                seen.add(text_key)
                unique.append(t)

        unique.sort(key=lambda x: x.get("likes", 0), reverse=True)
        return unique[:count]

    def analyze_and_learn(self, posts: list) -> dict:
        """Use Claude to analyze why posts are popular and extract learnings."""
        if not posts:
            return {"key_learnings": [], "top_patterns": []}

        # Limit to top 15 to stay within prompt limits
        posts_for_analysis = posts[:15]
        posts_json = json.dumps(posts_for_analysis, ensure_ascii=False, indent=2)
        prompt = ANALYSIS_PROMPT.replace("{posts_json}", posts_json)

        try:
            insights = self.claude.generate_json(prompt, temperature=0.3)
        except Exception as e:
            logger.error("Engagement analysis failed: %s", e)
            return {"key_learnings": [], "top_patterns": []}

        insights["analysis_date"] = datetime.now(JST).strftime("%Y-%m-%d")
        return insights

    def save_insights(self, insights: dict) -> None:
        """Save insights, merging with historical data."""
        existing = []
        if INSIGHTS_PATH.exists():
            try:
                existing = json.loads(INSIGHTS_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass

        if isinstance(existing, dict):
            existing = [existing]

        existing.append(insights)
        # Keep last 52 weeks of insights
        existing = existing[-52:]

        INSIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        INSIGHTS_PATH.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Engagement insights saved: %d entries", len(existing))

    def get_latest_insights(self) -> dict:
        """Load the most recent insights for use in content generation."""
        if not INSIGHTS_PATH.exists():
            return {}

        try:
            data = json.loads(INSIGHTS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data[-1]
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def build_generation_context(self) -> str:
        """Build a context string from insights for use in post generation prompts.

        This is injected into the generation prompts so AI learns from past success.
        """
        insights = self.get_latest_insights()
        if not insights:
            return ""

        lines = ["## 過去の分析から学んだ効果的なパターン:"]

        # Top patterns
        for pattern in insights.get("top_patterns", [])[:5]:
            lines.append(f"- {pattern.get('pattern_name', '')}: {pattern.get('description', '')}")
            if pattern.get("example_hook"):
                lines.append(f"  例: {pattern['example_hook']}")

        # Key learnings
        high_priority = [
            l for l in insights.get("key_learnings", [])
            if l.get("priority") == "high"
        ]
        if high_priority:
            lines.append("\n## 重要な教訓:")
            for learning in high_priority[:5]:
                lines.append(f"- {learning.get('learning', '')}")
                lines.append(f"  → {learning.get('action', '')}")

        # Avoid patterns
        avoids = insights.get("avoid_patterns", [])
        if avoids:
            lines.append("\n## 避けるべきパターン:")
            for avoid in avoids[:3]:
                lines.append(f"- {avoid.get('pattern', '')}: {avoid.get('reason', '')}")

        return "\n".join(lines)

    def _fetch_metrics(self, tweet_id: str) -> dict:
        """Fetch metrics for a single tweet."""
        if not self.bearer_token:
            return {}
        url = f"https://api.x.com/2/tweets/{tweet_id}"
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        params = {"tweet.fields": "public_metrics"}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            metrics = resp.json().get("data", {}).get("public_metrics", {})
            impressions = metrics.get("impression_count", 0)
            engagement = (
                metrics.get("like_count", 0)
                + metrics.get("retweet_count", 0)
                + metrics.get("reply_count", 0)
            )
            return {
                "likes": metrics.get("like_count", 0),
                "retweets": metrics.get("retweet_count", 0),
                "replies": metrics.get("reply_count", 0),
                "impressions": impressions,
                "engagement_rate": round(engagement / max(impressions, 1), 4),
            }
        except Exception:
            return {}

    def run(self) -> dict:
        """Full learning cycle: fetch top posts, analyze, save insights."""
        logger.info("EngagementLearner: Starting learning cycle...")

        # Collect from both own posts and industry
        own_top = self.fetch_own_top_posts(days=30)
        industry_top = self.fetch_industry_top_posts(count=20)

        all_posts = own_top + industry_top
        if not all_posts:
            logger.info("No posts found for analysis")
            return {}

        logger.info(
            "Analyzing %d posts (%d own, %d industry)...",
            len(all_posts), len(own_top), len(industry_top),
        )

        insights = self.analyze_and_learn(all_posts)
        self.save_insights(insights)

        logger.info(
            "Learning complete: %d patterns, %d learnings extracted",
            len(insights.get("top_patterns", [])),
            len(insights.get("key_learnings", [])),
        )
        return insights


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    learner = EngagementLearner()
    learner.run()
