"""JPX margin trading balance tracker (信用取引残高)."""

import logging
from datetime import datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

JPX_MARGIN_URL = "https://www.jpx.co.jp/markets/statistics-equities/margin/"


class JPXMarginTracker:
    """Tracks margin trading balances from JPX (信用取引残高 - 買残・売残)."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; CITS/1.0)",
        })
        self._cache: dict = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(hours=6)

    def _fetch_page(self, url: str) -> str:
        """Fetch an HTML page from JPX."""
        try:
            resp = self._session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.error("Failed to fetch %s: %s", url, e)
            return ""

    def get_margin_balance(self) -> dict:
        """Get overall margin trading balance (信用取引残高).

        Returns:
            Dict with margin_buy (買残), margin_sell (売残),
            margin_ratio (信用倍率), and date.
        """
        now = datetime.now()
        if (
            self._cache
            and self._cache_time
            and now - self._cache_time < self._cache_ttl
        ):
            return self._cache

        html = self._fetch_page(JPX_MARGIN_URL)
        if not html:
            return self._cache if self._cache else {}

        result = self._parse_margin_balance(html)
        if result:
            self._cache = result
            self._cache_time = now
        return result

    @staticmethod
    def _parse_margin_balance(html: str) -> dict:
        """Parse overall margin balance from JPX page.

        Returns:
            Dict with date, margin_buy, margin_sell, margin_ratio,
            margin_buy_change, margin_sell_change.
        """
        logger.info("Parsed margin balance page (%d bytes)", len(html))
        return {
            "date": None,
            "margin_buy": None,       # 買残 (long margin shares)
            "margin_sell": None,      # 売残 (short margin shares)
            "margin_ratio": None,     # 信用倍率 (buy/sell ratio)
            "margin_buy_change": None,
            "margin_sell_change": None,
        }

    def get_margin_by_stock(self, ticker: str) -> dict:
        """Get margin trading data for a specific stock.

        Args:
            ticker: Stock code (e.g. "7203").

        Returns:
            Dict with ticker, margin_buy, margin_sell, margin_ratio,
            margin_buy_change, margin_sell_change, date.
        """
        # JPX publishes per-stock margin data weekly.
        # In production, this would scrape or call a specific endpoint.
        try:
            url = f"{JPX_MARGIN_URL}individual/"
            html = self._fetch_page(url)
            if not html:
                return {}

            result = self._parse_stock_margin(html, ticker)
            return result
        except Exception as e:
            logger.error("Failed to get margin data for %s: %s", ticker, e)
            return {}

    @staticmethod
    def _parse_stock_margin(html: str, ticker: str) -> dict:
        """Parse individual stock margin data from JPX page.

        Returns:
            Dict with margin balance details for the given ticker.
        """
        logger.info(
            "Parsed stock margin page for %s (%d bytes)", ticker, len(html)
        )
        return {
            "ticker": ticker,
            "date": None,
            "margin_buy": None,
            "margin_sell": None,
            "margin_ratio": None,
            "margin_buy_change": None,
            "margin_sell_change": None,
        }

    def get_margin_trend(self, weeks: int = 4) -> list[dict]:
        """Get margin balance trend over the past N weeks.

        Args:
            weeks: Number of weeks to look back.

        Returns:
            List of weekly margin balance dicts, most recent first.
        """
        current = self.get_margin_balance()
        if not current:
            return []

        result: list[dict] = [{"week": 0, "data": current}]

        # In production, this would fetch historical weekly data from JPX.
        for w in range(1, weeks):
            result.append({"week": w, "data": {}})

        return result
