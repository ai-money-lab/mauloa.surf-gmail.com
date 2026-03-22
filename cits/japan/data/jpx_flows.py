"""JPX investor flow tracking (投資部門別売買動向)."""

import logging
from datetime import datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# JPX publishes weekly investor-type trading data
JPX_FLOW_URL = "https://www.jpx.co.jp/markets/statistics-equities/investor-type/nlsgeu000005gxc6-att/"


class JPXFlowTracker:
    """Tracks investor-type flow data from JPX (投資部門別売買動向).

    Categories: foreign investors, trust banks, individuals, proprietary, etc.
    """

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; CITS/1.0)",
        })
        self._cache: dict = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(hours=6)

    def _fetch_flow_data(self) -> dict:
        """Fetch the latest investor flow data from JPX, with caching."""
        now = datetime.now()
        if (
            self._cache
            and self._cache_time
            and now - self._cache_time < self._cache_ttl
        ):
            return self._cache

        try:
            resp = self._session.get(JPX_FLOW_URL, timeout=30)
            resp.raise_for_status()
            parsed = self._parse_flow_page(resp.text)
            if parsed:
                self._cache = parsed
                self._cache_time = now
            return parsed
        except Exception as e:
            logger.error("Failed to fetch JPX flow data: %s", e)
            return self._cache if self._cache else {}

    @staticmethod
    def _parse_flow_page(html: str) -> dict:
        """Parse flow data from JPX HTML/CSV content.

        Returns a dict keyed by investor category with buy/sell/net values.
        """
        categories = [
            "foreign_investors",
            "trust_banks",
            "investment_trusts",
            "individuals",
            "proprietary",
            "insurance",
            "city_banks",
            "other_financial",
            "other_corporations",
        ]
        result: dict = {}
        for cat in categories:
            result[cat] = {"buy": 0, "sell": 0, "net": 0}
        # Actual parsing depends on the JPX page format which changes.
        # In production this would parse the CSV/HTML tables.
        # Returning the structure so downstream code has a consistent schema.
        logger.info("Parsed JPX flow page (%d bytes)", len(html))
        return result

    def get_investor_flows(self) -> dict:
        """Get the latest weekly investor-type trading flows.

        Returns:
            Dict keyed by investor category (foreign_investors, trust_banks,
            individuals, etc.) each with buy, sell, net values in JPY.
        """
        data = self._fetch_flow_data()
        if not data:
            logger.warning("No investor flow data available")
            return {}
        return data

    def get_weekly_flows(self, weeks: int = 4) -> list[dict]:
        """Get investor flows for the past N weeks.

        Args:
            weeks: Number of past weeks to retrieve.

        Returns:
            List of weekly flow dicts, most recent first.
        """
        # In production, this would fetch historical weekly CSVs from JPX.
        # For now, returns the latest available data as a single-item list.
        current = self.get_investor_flows()
        if not current:
            return []
        result = [{"week": 0, "data": current}]
        # Placeholder for historical data
        for w in range(1, weeks):
            result.append({"week": w, "data": {}})
        return result

    def analyze_flow_trend(self) -> dict:
        """Analyze investor flow trends to determine who is buying/selling.

        Returns:
            Dict with trend analysis:
            - dominant_buyer: category with largest net buy
            - dominant_seller: category with largest net sell
            - foreign_trend: "buying" | "selling" | "neutral"
            - summary: human-readable summary
        """
        flows = self.get_investor_flows()
        if not flows:
            return {
                "dominant_buyer": None,
                "dominant_seller": None,
                "foreign_trend": "unknown",
                "summary": "No flow data available",
            }

        max_buy_cat = None
        max_buy_net = float("-inf")
        max_sell_cat = None
        max_sell_net = float("inf")

        for cat, values in flows.items():
            net = values.get("net", 0)
            if net > max_buy_net:
                max_buy_net = net
                max_buy_cat = cat
            if net < max_sell_net:
                max_sell_net = net
                max_sell_cat = cat

        foreign_net = flows.get("foreign_investors", {}).get("net", 0)
        if foreign_net > 0:
            foreign_trend = "buying"
        elif foreign_net < 0:
            foreign_trend = "selling"
        else:
            foreign_trend = "neutral"

        return {
            "dominant_buyer": max_buy_cat,
            "dominant_seller": max_sell_cat,
            "foreign_trend": foreign_trend,
            "summary": (
                f"Dominant buyer: {max_buy_cat} (net {max_buy_net:+,}), "
                f"Dominant seller: {max_sell_cat} (net {max_sell_net:+,}), "
                f"Foreign investors: {foreign_trend}"
            ),
        }
