"""Real Estate Data Research Agent.

Collects property data, transaction records, and land price data
for specified areas.
"""

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from core.claude_client import ClaudeClient
from core.quality_checker import QualityChecker

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "system_c"


class RealEstateDataAgent:
    """Agent for collecting real estate data."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.quality_checker = QualityChecker(self.claude)
        self.rate_limit = 0.5  # seconds between requests
        self.user_agent = "HIROKI-AI-Research/1.0"

    def _request(self, url: str, params: dict = None) -> requests.Response:
        """Make a rate-limited HTTP request."""
        time.sleep(self.rate_limit)
        return requests.get(
            url,
            params=params,
            headers={"User-Agent": self.user_agent},
            timeout=15,
        )

    def fetch_land_prices(self, area: str, year: int = None) -> dict:
        """Fetch land price data from MLIT API."""
        if not year:
            year = datetime.now(JST).year

        url = "https://www.land.mlit.go.jp/webland/api/TradeListSearch"
        params = {
            "from": f"{year - 1}1",
            "to": f"{year}4",
            "area": "13",  # Tokyo default
            "city": "",
        }

        try:
            resp = self._request(url, params)
            resp.raise_for_status()
            data = resp.json()
            return {
                "source": "mlit_land_prices",
                "area": area,
                "year": year,
                "records": data.get("data", [])[:50],
                "collected_at": datetime.now(JST).isoformat(),
            }
        except Exception as e:
            logger.warning("Land price fetch failed: %s", e)
            return {"source": "mlit_land_prices", "area": area, "error": str(e)}

    def fetch_population_data(self, area_code: str) -> dict:
        """Fetch population data from e-Stat."""
        import os

        api_key = os.getenv("ESTAT_API_KEY", "")
        if not api_key:
            return {"source": "estat", "error": "API key not configured"}

        url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
        params = {
            "appId": api_key,
            "statsDataId": "0003448233",  # Population census
            "cdArea": area_code,
            "limit": 100,
        }

        try:
            resp = self._request(url, params)
            resp.raise_for_status()
            data = resp.json()
            return {
                "source": "estat_population",
                "area_code": area_code,
                "data": data.get("GET_STATS_DATA", {}).get("STATISTICAL_DATA", {}),
                "collected_at": datetime.now(JST).isoformat(),
            }
        except Exception as e:
            logger.warning("Population data fetch failed: %s", e)
            return {"source": "estat_population", "error": str(e)}

    def analyze_area(self, area: str, params: dict = None) -> dict:
        """Comprehensive area analysis."""
        logger.info("Starting area analysis for: %s", area)

        result = {
            "area": area,
            "analysis_date": datetime.now(JST).isoformat(),
            "land_prices": self.fetch_land_prices(area),
            "population": {},
        }

        # Use Claude to synthesize
        prompt = (
            f"以下のデータを基に、{area}の不動産投資エリア分析サマリーを作成してください。\n"
            f"JSON形式で出力。\n\n"
            f"データ:\n{json.dumps(result, ensure_ascii=False, indent=2)[:3000]}"
        )

        try:
            summary = self.claude.generate_json(prompt, temperature=0.3)
            result["summary"] = summary
        except Exception as e:
            logger.warning("Summary generation failed: %s", e)

        # Quality check
        qr = self.quality_checker.check(
            profile="data_collection",
            content=json.dumps(result, ensure_ascii=False),
            context=f"Area analysis: {area}",
        )
        result["quality_check"] = qr

        # Save
        output_dir = DATA_DIR / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(JST).strftime("%Y-%m-%d")
        safe_area = area.replace("/", "_").replace(" ", "_")
        output_path = output_dir / f"area_{safe_area}_{date_str}.json"
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Area analysis saved: %s", output_path)
        return result

    def rental_valuation(self, property_id: str, params: dict = None) -> dict:
        """Estimate rental value for a property."""
        logger.info("Rental valuation for property: %s", property_id)

        area = (params or {}).get("area", "東京都")

        # Collect comparable data
        land_data = self.fetch_land_prices(area)

        result = {
            "property_id": property_id,
            "area": area,
            "valuation_date": datetime.now(JST).isoformat(),
            "comparable_data": land_data,
        }

        # Use Claude to estimate
        prompt = (
            f"以下のデータを基に、物件ID {property_id} の適正賃料を推定してください。\n"
            f"パラメータ: {json.dumps(params or {}, ensure_ascii=False)}\n"
            f"JSON形式で出力。\n\n"
            f"比較データ:\n{json.dumps(land_data, ensure_ascii=False)[:3000]}"
        )

        try:
            estimate = self.claude.generate_json(prompt, temperature=0.3)
            result["estimate"] = estimate
        except Exception as e:
            logger.warning("Rental estimation failed: %s", e)

        # Save
        output_dir = DATA_DIR / "valuations"
        output_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(JST).strftime("%Y-%m-%d")
        output_path = output_dir / f"rental_{property_id}_{date_str}.json"
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result

    def renovation_cost(self, job_id: str, params: dict = None) -> dict:
        """Research renovation costs for a specified job."""
        logger.info("Renovation cost research for job: %s", job_id)

        result = {
            "job_id": job_id,
            "research_date": datetime.now(JST).isoformat(),
            "parameters": params or {},
        }

        prompt = (
            f"以下の工事内容について、相場調査と費用比較を行ってください。\n"
            f"工事ID: {job_id}\n"
            f"パラメータ: {json.dumps(params or {}, ensure_ascii=False)}\n"
            f"3パターンの費用見積もりをJSON形式で出力してください。"
        )

        try:
            cost_analysis = self.claude.generate_json(prompt, temperature=0.4)
            result["cost_analysis"] = cost_analysis
        except Exception as e:
            logger.warning("Cost analysis failed: %s", e)

        # Save
        output_dir = DATA_DIR / "costs"
        output_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(JST).strftime("%Y-%m-%d")
        output_path = output_dir / f"renovation_{job_id}_{date_str}.json"
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result
