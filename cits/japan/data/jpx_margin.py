"""JPX margin trading balance tracker (信用取引残高)."""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

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

    def _fetch_csv(self, url: str) -> str:
        """Fetch CSV content from JPX, handling Shift_JIS encoding."""
        try:
            resp = self._session.get(url, timeout=30)
            resp.raise_for_status()
            resp.encoding = "shift_jis"
            return resp.text
        except Exception as e:
            logger.error("Failed to fetch CSV %s: %s", url, e)
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
            return self._cache if self._cache else _empty_margin()

        result = self._parse_margin_balance(html)
        if result and result.get("date"):
            self._cache = result
            self._cache_time = now
            return result

        # Fallback: try CSV link from the page
        csv_url = _extract_csv_link(html, JPX_MARGIN_URL)
        if csv_url:
            csv_text = self._fetch_csv(csv_url)
            if csv_text:
                result = self._parse_margin_balance_csv(csv_text)
                if result and result.get("date"):
                    self._cache = result
                    self._cache_time = now
                    return result

        logger.warning("Could not parse margin balance data; returning defaults")
        return self._cache if self._cache else _empty_margin()

    @staticmethod
    def _parse_margin_balance(html: str) -> dict:
        """Parse overall margin balance from JPX HTML page.

        JPX margin pages typically have tables with columns:
        日付, 信用買残(株数/金額), 信用売残(株数/金額), 倍率

        Returns:
            Dict with date, margin_buy, margin_sell, margin_ratio,
            margin_buy_change, margin_sell_change.
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            tables = soup.find_all("table")

            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    cell_texts = [c.get_text(strip=True) for c in cells]

                    if not cell_texts:
                        continue

                    # Look for a date in the first cell
                    date_match = re.search(
                        r"(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})", cell_texts[0]
                    )
                    if date_match and len(cell_texts) >= 3:
                        y, m, d = date_match.groups()
                        date_str = f"{y}-{int(m):02d}-{int(d):02d}"

                        margin_buy = _parse_number(
                            cell_texts[1] if len(cell_texts) > 1 else None
                        )
                        margin_sell = _parse_number(
                            cell_texts[2] if len(cell_texts) > 2 else None
                        )
                        margin_ratio = _parse_number(
                            cell_texts[3] if len(cell_texts) > 3 else None
                        )
                        margin_buy_change = _parse_number(
                            cell_texts[4] if len(cell_texts) > 4 else None
                        )
                        margin_sell_change = _parse_number(
                            cell_texts[5] if len(cell_texts) > 5 else None
                        )

                        logger.info(
                            "Parsed margin balance from HTML: date=%s buy=%s sell=%s",
                            date_str,
                            margin_buy,
                            margin_sell,
                        )
                        return {
                            "date": date_str,
                            "margin_buy": margin_buy,
                            "margin_sell": margin_sell,
                            "margin_ratio": margin_ratio,
                            "margin_buy_change": margin_buy_change,
                            "margin_sell_change": margin_sell_change,
                        }

            logger.info(
                "No table-based margin data found in HTML (%d bytes)", len(html)
            )
        except Exception as e:
            logger.error("Error parsing margin balance HTML: %s", e)

        return _empty_margin()

    @staticmethod
    def _parse_margin_balance_csv(csv_text: str) -> dict:
        """Parse overall margin balance from a JPX CSV file.

        Expected columns: 日付, 信用買残, 信用売残, 倍率
        Returns the most recent row.
        """
        try:
            reader = csv.reader(io.StringIO(csv_text))
            header: list[str] = []
            last_row: list[str] = []

            for row in reader:
                if not row:
                    continue
                if any("日付" in cell for cell in row) or any(
                    "買残" in cell for cell in row
                ):
                    header = row
                    continue
                if header and row[0].strip():
                    last_row = row

            if not last_row:
                return _empty_margin()

            date_match = re.search(
                r"(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})", last_row[0]
            )
            date_str = None
            if date_match:
                y, m, d = date_match.groups()
                date_str = f"{y}-{int(m):02d}-{int(d):02d}"

            margin_buy = _parse_number(last_row[1] if len(last_row) > 1 else None)
            margin_sell = _parse_number(last_row[2] if len(last_row) > 2 else None)
            margin_ratio = _parse_number(last_row[3] if len(last_row) > 3 else None)
            margin_buy_change = _parse_number(
                last_row[4] if len(last_row) > 4 else None
            )
            margin_sell_change = _parse_number(
                last_row[5] if len(last_row) > 5 else None
            )

            logger.info(
                "Parsed margin balance from CSV: date=%s buy=%s sell=%s",
                date_str,
                margin_buy,
                margin_sell,
            )
            return {
                "date": date_str,
                "margin_buy": margin_buy,
                "margin_sell": margin_sell,
                "margin_ratio": margin_ratio,
                "margin_buy_change": margin_buy_change,
                "margin_sell_change": margin_sell_change,
            }
        except Exception as e:
            logger.error("Error parsing margin balance CSV: %s", e)
            return _empty_margin()

    def get_margin_by_stock(self, ticker: str) -> dict:
        """Get margin trading data for a specific stock.

        Args:
            ticker: Stock code (e.g. "7203").

        Returns:
            Dict with ticker, margin_buy, margin_sell, margin_ratio,
            margin_buy_change, margin_sell_change, date.
        """
        try:
            url = f"{JPX_MARGIN_URL}individual/"
            html = self._fetch_page(url)
            if not html:
                return _empty_stock_margin(ticker)

            result = self._parse_stock_margin(html, ticker)
            if result and result.get("date"):
                return result

            # Fallback: try CSV
            csv_url = _extract_csv_link(html, url)
            if csv_url:
                csv_text = self._fetch_csv(csv_url)
                if csv_text:
                    result = self._parse_stock_margin_csv(csv_text, ticker)
                    if result and result.get("date"):
                        return result

            logger.warning(
                "Could not parse stock margin data for %s; returning defaults", ticker
            )
            return _empty_stock_margin(ticker)
        except Exception as e:
            logger.error("Failed to get margin data for %s: %s", ticker, e)
            return _empty_stock_margin(ticker)

    @staticmethod
    def _parse_stock_margin(html: str, ticker: str) -> dict:
        """Parse individual stock margin data from JPX HTML page.

        Looks for a row matching the given ticker code in the margin table.
        Expected columns: 銘柄コード, 銘柄名, 信用買残, 信用売残, 倍率

        Returns:
            Dict with margin balance details for the given ticker.
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            tables = soup.find_all("table")

            # Try to extract a date from the page (often in a heading or caption)
            page_date = _extract_page_date(soup)

            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    cell_texts = [c.get_text(strip=True) for c in cells]

                    if not cell_texts:
                        continue

                    # Check if this row contains our ticker
                    if not any(ticker in c for c in cell_texts[:3]):
                        continue

                    # Found the ticker row - extract data
                    # Typical layout: code, name, buy, sell, ratio, buy_chg, sell_chg
                    margin_buy = None
                    margin_sell = None
                    margin_ratio = None
                    margin_buy_change = None
                    margin_sell_change = None

                    # Skip code and name columns, then parse numerics
                    numeric_cells = []
                    for cell_val in cell_texts:
                        num = _parse_number(cell_val)
                        if num is not None:
                            numeric_cells.append(num)

                    if len(numeric_cells) >= 2:
                        margin_buy = numeric_cells[0]
                        margin_sell = numeric_cells[1]
                    if len(numeric_cells) >= 3:
                        margin_ratio = numeric_cells[2]
                    if len(numeric_cells) >= 4:
                        margin_buy_change = numeric_cells[3]
                    if len(numeric_cells) >= 5:
                        margin_sell_change = numeric_cells[4]

                    logger.info(
                        "Parsed stock margin for %s from HTML: buy=%s sell=%s",
                        ticker,
                        margin_buy,
                        margin_sell,
                    )
                    return {
                        "ticker": ticker,
                        "date": page_date,
                        "margin_buy": margin_buy,
                        "margin_sell": margin_sell,
                        "margin_ratio": margin_ratio,
                        "margin_buy_change": margin_buy_change,
                        "margin_sell_change": margin_sell_change,
                    }

            logger.info(
                "Ticker %s not found in margin HTML (%d bytes)", ticker, len(html)
            )
        except Exception as e:
            logger.error("Error parsing stock margin HTML for %s: %s", ticker, e)

        return _empty_stock_margin(ticker)

    @staticmethod
    def _parse_stock_margin_csv(csv_text: str, ticker: str) -> dict:
        """Parse per-stock margin data from a JPX CSV file.

        Expected columns: 日付, 銘柄コード, 信用買残, 信用売残, 倍率
        """
        try:
            reader = csv.reader(io.StringIO(csv_text))
            header: list[str] = []

            for row in reader:
                if not row:
                    continue
                if any("銘柄" in cell for cell in row) or any(
                    "日付" in cell for cell in row
                ):
                    header = row
                    continue
                if not header or len(row) < 3:
                    continue

                # Check if this row matches the ticker
                if not any(ticker in cell for cell in row[:3]):
                    continue

                # Extract date
                date_str = None
                for cell_val in row[:2]:
                    dm = re.search(
                        r"(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})", cell_val
                    )
                    if dm:
                        y, mo, dy = dm.groups()
                        date_str = f"{y}-{int(mo):02d}-{int(dy):02d}"
                        break

                # Collect numeric values from the row
                numeric_vals: list[float] = []
                for cell_val in row:
                    num = _parse_number(cell_val)
                    if num is not None:
                        numeric_vals.append(num)

                margin_buy = numeric_vals[0] if len(numeric_vals) > 0 else None
                margin_sell = numeric_vals[1] if len(numeric_vals) > 1 else None
                margin_ratio = numeric_vals[2] if len(numeric_vals) > 2 else None
                margin_buy_change = numeric_vals[3] if len(numeric_vals) > 3 else None
                margin_sell_change = numeric_vals[4] if len(numeric_vals) > 4 else None

                logger.info(
                    "Parsed stock margin for %s from CSV: buy=%s sell=%s",
                    ticker,
                    margin_buy,
                    margin_sell,
                )
                return {
                    "ticker": ticker,
                    "date": date_str,
                    "margin_buy": margin_buy,
                    "margin_sell": margin_sell,
                    "margin_ratio": margin_ratio,
                    "margin_buy_change": margin_buy_change,
                    "margin_sell_change": margin_sell_change,
                }

            logger.info("Ticker %s not found in margin CSV", ticker)
        except Exception as e:
            logger.error("Error parsing stock margin CSV for %s: %s", ticker, e)

        return _empty_stock_margin(ticker)

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
            result.append({"week": w, "data": _empty_margin()})

        return result


def _empty_margin() -> dict:
    """Return an empty but well-structured margin balance dict."""
    return {
        "date": None,
        "margin_buy": None,
        "margin_sell": None,
        "margin_ratio": None,
        "margin_buy_change": None,
        "margin_sell_change": None,
    }


def _empty_stock_margin(ticker: str) -> dict:
    """Return an empty but well-structured per-stock margin dict."""
    return {
        "ticker": ticker,
        "date": None,
        "margin_buy": None,
        "margin_sell": None,
        "margin_ratio": None,
        "margin_buy_change": None,
        "margin_sell_change": None,
    }


def _extract_csv_link(html: str, base_url: str) -> Optional[str]:
    """Extract the first CSV download link from an HTML page."""
    try:
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.endswith(".csv"):
                if href.startswith("http"):
                    return href
                if href.startswith("/"):
                    return f"https://www.jpx.co.jp{href}"
                return f"{base_url.rstrip('/')}/{href}"
    except Exception as e:
        logger.error("Failed to extract CSV link: %s", e)
    return None


def _extract_page_date(soup: BeautifulSoup) -> Optional[str]:
    """Try to extract a date from page headings or captions."""
    try:
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "caption", "p"]):
            text = tag.get_text(strip=True)
            dm = re.search(r"(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})", text)
            if dm:
                y, m, d = dm.groups()
                return f"{y}-{int(m):02d}-{int(d):02d}"
    except Exception:
        pass
    return None


def _parse_number(value: Optional[str]) -> Optional[float]:
    """Parse a numeric string, stripping commas and whitespace."""
    if value is None:
        return None
    cleaned = value.strip().replace(",", "").replace("、", "").replace("%", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None
