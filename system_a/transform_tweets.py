"""System A - TASK A-4: ローカライズ変換エンジン

TOP5の各ツイートに対し日本語投稿を3パターン生成する。
"""

import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.claude_client import ClaudeClient

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
ANALYZED_DIR = BASE_DIR / "data" / "system_a" / "analyzed"
TRANSFORMED_DIR = BASE_DIR / "data" / "system_a" / "transformed"


MARKET_WATCH_DIR = BASE_DIR / "data" / "system_c" / "daily"


class TweetTransformer:
    """バイラルツイート→日本語オリジナル投稿変換"""

    def __init__(self):
        self.claude = ClaudeClient()
        self._market_context = self._load_market_context()

    def _load_market_context(self) -> str:
        """System Cのmarket watchデータから最新トピックを抽出"""
        date_str = datetime.now(JST).strftime("%Y-%m-%d")
        market_file = MARKET_WATCH_DIR / f"market_watch_{date_str}.json"

        if not market_file.exists():
            # 前日分を試す
            yesterday = (datetime.now(JST) - timedelta(days=1)).strftime("%Y-%m-%d")
            market_file = MARKET_WATCH_DIR / f"market_watch_{yesterday}.json"
            if not market_file.exists():
                logger.info("No market watch data available for context")
                return ""

        try:
            with open(market_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            topics = []

            # 法規制の変更トピック
            reg = data.get("regulation_updates", {})
            updates = reg.get("real_estate_legal_updates", [])
            for u in updates[:3]:  # 上位3件
                if u.get("impact_level") == "high":
                    topics.append(f"[法規制] {u.get('title', '')}: {u.get('summary', '')[:60]}")

            # マーケット動向
            market = data.get("market_overview", {})
            report = market.get("market_report", market)
            conditions = report.get("market_conditions", {})

            if conditions.get("interest_rates"):
                ir = conditions["interest_rates"]
                topics.append(f"[金利] {ir.get('trend', '')}")

            outlook = conditions.get("market_outlook", {})
            if outlook.get("overall_sentiment"):
                topics.append(f"[市場見通し] {outlook['overall_sentiment']}")

            if topics:
                context = "## 今日のマーケットインサイト（System C収集）:\n" + "\n".join(f"- {t}" for t in topics)
                logger.info(f"Loaded {len(topics)} market context topics")
                return context
            return ""
        except Exception as e:
            logger.warning(f"Failed to load market context: {e}")
            return ""

    def load_top5(self, date_str: str | None = None) -> list[dict]:
        """分析済みTOP5を読み込む"""
        if date_str is None:
            date_str = datetime.now(JST).strftime("%Y-%m-%d")

        file_path = ANALYZED_DIR / f"{date_str}.json"
        if not file_path.exists():
            logger.error(f"Analyzed data not found: {file_path}")
            return []

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("top5", [])

    def transform(self, tweet_analysis: dict, original_tweet: dict | None = None) -> dict:
        """1ツイートを3パターンに変換"""
        tweet_data = {
            "analysis": tweet_analysis,
            "original_text": original_tweet.get("text", "") if original_tweet else "",
            "pillar": tweet_analysis.get("content_pillar", {}).get("pillar_number", 1),
            "trigger": tweet_analysis.get("psychological_trigger", "surprise"),
            "format": tweet_analysis.get("recommended_format", "standard"),
        }

        # market contextがあれば追加
        if self._market_context:
            tweet_data["market_context"] = self._market_context

        prompt = self.claude.load_prompt(
            "transform_viral.txt",
            tweet_data=json.dumps(tweet_data, ensure_ascii=False, indent=2),
        )

        try:
            result = self.claude.generate_json(prompt, max_tokens=4096, temperature=0.8)
            return result
        except Exception as e:
            logger.error(f"Transform failed: {e}")
            return {}

    def transform_all(self, top5: list[dict]) -> list[dict]:
        """TOP5すべてを変換"""
        results = []
        for i, analysis in enumerate(top5):
            logger.info(f"Transforming tweet {i + 1}/{len(top5)}")
            result = self.transform(analysis)
            if result:
                results.append(result)
        return results

    def save(self, transformed: list[dict]) -> str:
        """変換結果を保存"""
        TRANSFORMED_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(JST).strftime("%Y-%m-%d")
        output_path = TRANSFORMED_DIR / f"{date_str}.json"

        output = {
            "transformed_at": datetime.now(JST).isoformat(),
            "count": len(transformed),
            "tweets": transformed,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        logger.info(f"Transformed tweets saved: {output_path}")
        return str(output_path)


def main():
    logging.basicConfig(level=logging.INFO)
    transformer = TweetTransformer()

    top5 = transformer.load_top5()
    if not top5:
        print("No analyzed tweets found")
        return

    transformed = transformer.transform_all(top5)
    path = transformer.save(transformed)
    print(f"Transformed {len(transformed)} tweets → {path}")


if __name__ == "__main__":
    main()
