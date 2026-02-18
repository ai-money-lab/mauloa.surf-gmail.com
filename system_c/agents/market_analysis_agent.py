"""Market Analysis Agent.

Analyzes macro-economic indicators and their correlation
with real estate markets.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from core.claude_client import ClaudeClient
from core.quality_checker import QualityChecker

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "system_c"


class MarketAnalysisAgent:
    """Analyze market data and produce forecasts."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.quality_checker = QualityChecker(self.claude)

    def daily_market_watch(self) -> dict:
        """Daily check of market conditions."""
        logger.info("Running daily market watch...")

        prompt = (
            "以下の項目について、最新の市場動向をJSON形式でまとめてください:\n"
            "1. 金利動向（住宅ローン金利の変動）\n"
            "2. 不動産関連法改正の動き\n"
            "3. 新築マンション供給状況\n"
            "4. 補助金・助成金の新設・変更\n"
            "5. 地価の注目動向\n\n"
            "各項目について source, summary, impact_level(high/medium/low), "
            "relevance_to_hiroki を含めてください。"
        )

        try:
            result = self.claude.generate_json(prompt, temperature=0.3)
        except Exception as e:
            logger.error("Market watch failed: %s", e)
            result = {"error": str(e)}

        output = {
            "type": "daily_market_watch",
            "date": datetime.now(JST).isoformat(),
            "data": result,
        }

        # Quality check
        qr = self.quality_checker.check(
            profile="data_collection",
            content=json.dumps(output, ensure_ascii=False),
            context="Daily market watch",
        )
        output["quality_check"] = qr

        # Save
        output_dir = DATA_DIR / "daily"
        output_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(JST).strftime("%Y-%m-%d")
        path = output_dir / f"market_watch_{date_str}.json"
        path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Daily market watch saved: %s", path)
        return output

    def analyze_area_market(self, area: str, data: dict) -> dict:
        """Analyze market conditions for a specific area."""
        prompt = (
            f"以下のデータを基に、{area}の不動産市場分析を行ってください。\n"
            f"JSON形式で出力。項目:\n"
            f"- market_overview: 市場概況\n"
            f"- price_trend: 価格トレンド（上昇/横ばい/下落）\n"
            f"- supply_demand: 需給バランス\n"
            f"- forecast_6months: 6ヶ月予測\n"
            f"- forecast_1year: 1年予測\n"
            f"- risks: リスク要因\n"
            f"- opportunities: 機会\n\n"
            f"データ:\n{json.dumps(data, ensure_ascii=False)[:3000]}"
        )

        try:
            analysis = self.claude.generate_json(prompt, temperature=0.4)
            return {
                "area": area,
                "analysis_date": datetime.now(JST).isoformat(),
                "analysis": analysis,
            }
        except Exception as e:
            logger.error("Area market analysis failed: %s", e)
            return {"area": area, "error": str(e)}
