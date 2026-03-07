"""System A - TASK A-3: AI分析エンジン

収集ツイートをClaude APIで分析し、TOP5を選定する。
"""

import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from core.claude_client import ClaudeClient

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
COLLECTED_DIR = BASE_DIR / "data" / "system_a" / "collected"
ANALYZED_DIR = BASE_DIR / "data" / "system_a" / "analyzed"

PILLAR_WEIGHTS = {
    "universality": 0.10,
    "japan_fit": 0.15,
    "pillar_fit": 0.20,
    "hiroki_fit": 0.20,
    "rt_potential": 0.15,
    "reply_potential": 0.10,
    "bookmark_potential": 0.10,
}


class TweetAnalyzer:
    """バイラルツイート分析"""

    def __init__(self):
        self.claude = ClaudeClient()

    def load_collected(self, date_str: str | None = None) -> list[dict]:
        """収集済みツイートを読み込む"""
        if date_str is None:
            date_str = datetime.now(JST).strftime("%Y-%m-%d")

        file_path = COLLECTED_DIR / f"{date_str}.json"
        if not file_path.exists():
            logger.error(f"Collected data not found: {file_path}")
            return []

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("tweets", [])

    def analyze(self, tweets: list[dict]) -> list[dict]:
        """ツイートをAI分析"""
        if not tweets:
            return []

        prompt = self.claude.load_prompt(
            "analyze_viral.txt",
            tweets_json=json.dumps(tweets, ensure_ascii=False, indent=2),
        )

        try:
            results = self.claude.generate_json(prompt, max_tokens=4096, temperature=0.3)
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return []

        if isinstance(results, dict):
            results = results.get("analyses", [results])

        for result in results:
            if "total_score" not in result:
                pillar = result.get("content_pillar", {})
                algo = result.get("algorithm_prediction", {})
                result["total_score"] = (
                    result.get("universality_score", 5) * PILLAR_WEIGHTS["universality"]
                    + result.get("japan_market_fit", 5) * PILLAR_WEIGHTS["japan_fit"]
                    + pillar.get("pillar_fit", 5) * PILLAR_WEIGHTS["pillar_fit"]
                    + result.get("hiroki_fit", 5) * PILLAR_WEIGHTS["hiroki_fit"]
                    + algo.get("rt_potential", 5) * PILLAR_WEIGHTS["rt_potential"]
                    + algo.get("reply_potential", 5) * PILLAR_WEIGHTS["reply_potential"]
                    + algo.get("bookmark_potential", 5) * PILLAR_WEIGHTS["bookmark_potential"]
                )

        return results

    def select_top5(self, analyses: list[dict]) -> list[dict]:
        """異なる柱から分散してTOP5を選定"""
        sorted_analyses = sorted(analyses, key=lambda x: x.get("total_score", 0), reverse=True)

        selected = []
        pillar_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        pillar_limits = {1: 2, 2: 1, 3: 1, 4: 1, 5: 1}

        for analysis in sorted_analyses:
            if len(selected) >= 5:
                break

            pillar = analysis.get("content_pillar", {}).get("pillar_number", 1)
            if pillar_counts.get(pillar, 0) < pillar_limits.get(pillar, 1):
                selected.append(analysis)
                pillar_counts[pillar] = pillar_counts.get(pillar, 0) + 1

        if len(selected) < 5:
            for analysis in sorted_analyses:
                if len(selected) >= 5:
                    break
                if analysis not in selected:
                    selected.append(analysis)

        return selected

    def save(self, analyses: list[dict], top5: list[dict]) -> str:
        """分析結果を保存"""
        ANALYZED_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(JST).strftime("%Y-%m-%d")
        output_path = ANALYZED_DIR / f"{date_str}.json"

        output = {
            "analyzed_at": datetime.now(JST).isoformat(),
            "total_analyzed": len(analyses),
            "top5_ids": [a.get("original_id", "") for a in top5],
            "all_analyses": analyses,
            "top5": top5,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        logger.info(f"Analysis saved: {output_path}")
        return str(output_path)


def main():
    logging.basicConfig(level=logging.INFO)
    analyzer = TweetAnalyzer()

    tweets = analyzer.load_collected()
    if not tweets:
        print("No collected tweets found")
        return

    analyses = analyzer.analyze(tweets)
    top5 = analyzer.select_top5(analyses)
    path = analyzer.save(analyses, top5)
    print(f"Analyzed {len(analyses)} tweets, selected TOP5 → {path}")


if __name__ == "__main__":
    main()
