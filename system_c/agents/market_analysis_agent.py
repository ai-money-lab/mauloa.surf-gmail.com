"""不動産マーケットアナリストエージェント

人口動態・金利・供給量から市場予測を行う。
"""

import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env", override=True)

from core.claude_client import ClaudeClient
from core.quality_checker import QualityChecker

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = _ROOT


class MarketAnalysisAgent:
    """不動産マーケット分析エージェント"""

    def __init__(self):
        self.claude = ClaudeClient()
        self.quality_checker = QualityChecker()

    def analyze_market(self, area: str, data: dict | None = None) -> dict:
        """市場分析を実行"""
        logger.info(f"Analyzing market for: {area}")

        context_data = json.dumps(data, ensure_ascii=False) if data else "{}"

        prompt = (
            f"不動産マーケットアナリストとして、{area}の市場分析を行ってください。\n\n"
            f"## 利用可能データ:\n{context_data}\n\n"
            f"## 分析項目:\n"
            f"1. 市場トレンド（上昇/横ばい/下落）\n"
            f"2. 需給バランス\n"
            f"3. 金利影響分析\n"
            f"4. 人口動態の影響\n"
            f"5. 再開発・インフラ計画\n"
            f"6. 投資判断（推奨/中立/非推奨）\n"
            f"7. リスク要因\n"
            f"8. 6ヶ月〜1年の見通し\n\n"
            f"JSON形式で出力してください。"
        )

        try:
            analysis = self.claude.generate_json(prompt, max_tokens=4096, temperature=0.4)
            analysis["area"] = area
            analysis["analyzed_at"] = datetime.now(JST).isoformat()

            quality = self.quality_checker.check(
                profile="data_collection",
                content=json.dumps(analysis, ensure_ascii=False),
                context=f"market_analysis_{area}",
            )
            analysis["quality_score"] = quality.total_score

            return analysis
        except Exception as e:
            logger.error(f"Market analysis failed: {e}")
            return {"area": area, "error": str(e)}

    def daily_market_watch(self) -> dict:
        """日次マーケットウォッチ"""
        logger.info("Running daily market watch")

        prompt = (
            "不動産マーケットアナリストとして、本日の市場動向をJSON形式で報告してください。\n\n"
            "## チェック項目:\n"
            "1. 金利動向（日銀政策・住宅ローン金利）\n"
            "2. 新築マンション供給状況\n"
            "3. 中古マンション価格指数\n"
            "4. 地価動向\n"
            "5. 注目の再開発プロジェクト\n"
            "6. 法改正・補助金の動き\n"
            "7. 市場全体の所感\n\n"
            "各項目にsource_urlとconfidence_levelを含めてください。"
        )

        try:
            report = self.claude.generate_json(prompt, max_tokens=4096, temperature=0.3)
            report["report_date"] = datetime.now(JST).strftime("%Y-%m-%d")
            return report
        except Exception as e:
            logger.error(f"Daily market watch failed: {e}")
            return {"error": str(e)}

    def save_result(self, data: dict, output_path: str) -> str:
        """結果を保存"""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Analysis saved: {path}")
        return str(path)
