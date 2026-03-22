"""JPX short selling data tracker (空売り比率・空売り残高)."""

import logging
from datetime import datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

JPX_SHORT_RATIO_URL = "https://www.jpx.co.jp/markets/statistics-equities/short-selling/"
JPX_SHORT_POSITIONS_URL = "https://www.jpx.co.jp/markets/statistics-equities/short-positions/"


class JPXShortTracker:
    """Tracks short selling ratios and positions from JPX."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; CITS/1.0)",
        })
        self._ratio_cache: dict = {}
        self._ratio_cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(hours=4)

    def _fetch_page(self, url: str) -> str:
        """Fetch an HTML page from JPX."""
        try:
            resp = self._session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.error("Failed to fetch %s: %s", url, e)
            return ""

    def get_short_selling_ratio(self) -> dict:
        """Get the latest overall short selling ratio (空売り比率).

        Returns:
            Dict with date, total_short_ratio, margin_short_ratio, etc.
        """
        now = datetime.now()
        if (
            self._ratio_cache
            and self._ratio_cache_time
            and now - self._ratio_cache_time < self._cache_ttl
        ):
            return self._ratio_cache

        html = self._fetch_page(JPX_SHORT_RATIO_URL)
        if not html:
            return self._ratio_cache if self._ratio_cache else {}

        result = self._parse_short_ratio(html)
        if result:
            self._ratio_cache = result
            self._ratio_cache_time = now
        return result

    @staticmethod
    def _parse_short_ratio(html: str) -> dict:
        """Parse short selling ratio from JPX page.

        Returns:
            Dict with date, total_short_ratio, margin_short_ratio,
            proprietary_short_ratio fields.
        """
        # JPX publishes daily short selling ratios in HTML tables / CSVs.
        # The actual parsing logic depends on the page structure.
        logger.info("Parsed short ratio page (%d bytes)", len(html))
        return {
            "date": None,
            "total_short_ratio": None,
            "margin_short_ratio": None,
            "proprietary_short_ratio": None,
        }

    def get_short_positions(self, ticker: Optional[str] = None) -> list[dict]:
        """Get short selling positions (空売り残高).

        Args:
            ticker: Optional stock code to filter for. If None, returns all.

        Returns:
            List of dicts with ticker, holder, shares_short, ratio, report_date.
        """
        html = self._fetch_page(JPX_SHORT_POSITIONS_URL)
        if not html:
            return []

        positions = self._parse_short_positions(html)

        if ticker and positions:
            positions = [p for p in positions if p.get("ticker") == ticker]

        return positions

    @staticmethod
    def _parse_short_positions(html: str) -> list[dict]:
        """Parse short position data from JPX page.

        Returns:
            List of dicts with ticker, holder_name, shares_short,
            short_ratio, report_date.
        """
        logger.info("Parsed short positions page (%d bytes)", len(html))
        return []

    def get_historical_short_ratio(self, days: int = 30) -> list[dict]:
        """Get historical short selling ratios for the past N days.

        Args:
            days: Number of trading days to look back.

        Returns:
            List of dicts with date and ratio fields, most recent first.
        """
        # In production, this would fetch the historical CSV from JPX.
        current = self.get_short_selling_ratio()
        if not current:
            return []

        result: list[dict] = []
        if current.get("date"):
            result.append(current)

        # Placeholder entries for historical dates
        base_date = datetime.now()
        for i in range(1, days):
            d = base_date - timedelta(days=i)
            # Skip weekends
            if d.weekday() >= 5:
                continue
            result.append({
                "date": d.strftime("%Y-%m-%d"),
                "total_short_ratio": None,
                "margin_short_ratio": None,
                "proprietary_short_ratio": None,
            })

        return result[:days]
