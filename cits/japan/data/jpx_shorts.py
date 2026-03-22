"""JPX short selling data tracker (空売り比率・空売り残高)."""

import csv
import io
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

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

    def _fetch_csv(self, url: str) -> str:
        """Fetch CSV content from JPX, handling Shift_JIS encoding."""
        try:
            resp = self._session.get(url, timeout=30)
            resp.raise_for_status()
            # JPX CSVs are typically Shift_JIS encoded
            resp.encoding = "shift_jis"
            return resp.text
        except Exception as e:
            logger.error("Failed to fetch CSV %s: %s", url, e)
            return ""

    def get_short_selling_ratio(self) -> dict:
        """Get the latest overall short selling ratio (空売り比率).

        Returns:
            Dict with date, total_short_ratio, naked_short_ratio, short_value.
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
            return self._ratio_cache if self._ratio_cache else _empty_ratio()

        result = self._parse_short_ratio(html)
        if result and result.get("date"):
            self._ratio_cache = result
            self._ratio_cache_time = now
            return result

        # Fallback: try to find and fetch the CSV link from the page
        csv_url = self._extract_csv_link(html, JPX_SHORT_RATIO_URL)
        if csv_url:
            csv_text = self._fetch_csv(csv_url)
            if csv_text:
                result = self._parse_short_ratio_csv(csv_text)
                if result and result.get("date"):
                    self._ratio_cache = result
                    self._ratio_cache_time = now
                    return result

        logger.warning("Could not parse short ratio data; returning defaults")
        return self._ratio_cache if self._ratio_cache else _empty_ratio()

    @staticmethod
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

    @staticmethod
    def _parse_short_ratio(html: str) -> dict:
        """Parse short selling ratio from JPX HTML page.

        JPX typically displays the data in an HTML table with columns:
        日付, 空売り比率(%), 実空売り比率(%), 空売り金額(百万円)

        Returns:
            Dict with date, total_short_ratio, naked_short_ratio, short_value.
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Look for data tables on the page
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    cell_texts = [c.get_text(strip=True) for c in cells]

                    # Skip header rows; look for rows starting with a date
                    if not cell_texts:
                        continue

                    # Try to detect a date in the first cell (e.g. 2026/3/20)
                    date_match = re.search(
                        r"(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})", cell_texts[0]
                    )
                    if date_match and len(cell_texts) >= 3:
                        y, m, d = date_match.groups()
                        date_str = f"{y}-{int(m):02d}-{int(d):02d}"

                        total_ratio = _parse_number(
                            cell_texts[1] if len(cell_texts) > 1 else None
                        )
                        naked_ratio = _parse_number(
                            cell_texts[2] if len(cell_texts) > 2 else None
                        )
                        short_value = _parse_number(
                            cell_texts[3] if len(cell_texts) > 3 else None
                        )

                        logger.info(
                            "Parsed short ratio from HTML: date=%s ratio=%.1f%%",
                            date_str,
                            total_ratio or 0,
                        )
                        return {
                            "date": date_str,
                            "total_short_ratio": total_ratio,
                            "naked_short_ratio": naked_ratio,
                            "short_value": short_value,
                        }

            logger.info(
                "No table-based short ratio found in HTML (%d bytes)", len(html)
            )
        except Exception as e:
            logger.error("Error parsing short ratio HTML: %s", e)

        return _empty_ratio()

    @staticmethod
    def _parse_short_ratio_csv(csv_text: str) -> dict:
        """Parse short selling ratio from a JPX CSV file.

        Expected columns: 日付, 空売り比率(%), 実空売り比率(%), 空売り金額(百万円)
        """
        try:
            reader = csv.reader(io.StringIO(csv_text))
            header: list[str] = []
            last_row: list[str] = []

            for row in reader:
                if not row:
                    continue
                # Detect header row by looking for 日付
                if any("日付" in cell for cell in row):
                    header = row
                    continue
                if header and row[0].strip():
                    last_row = row  # keep the most recent data row

            if not last_row:
                return _empty_ratio()

            # Parse the date from first column
            date_match = re.search(
                r"(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})", last_row[0]
            )
            date_str = None
            if date_match:
                y, m, d = date_match.groups()
                date_str = f"{y}-{int(m):02d}-{int(d):02d}"

            total_ratio = _parse_number(last_row[1] if len(last_row) > 1 else None)
            naked_ratio = _parse_number(last_row[2] if len(last_row) > 2 else None)
            short_value = _parse_number(last_row[3] if len(last_row) > 3 else None)

            logger.info(
                "Parsed short ratio from CSV: date=%s ratio=%.1f%%",
                date_str,
                total_ratio or 0,
            )
            return {
                "date": date_str,
                "total_short_ratio": total_ratio,
                "naked_short_ratio": naked_ratio,
                "short_value": short_value,
            }
        except Exception as e:
            logger.error("Error parsing short ratio CSV: %s", e)
            return _empty_ratio()

    def get_short_positions(self, ticker: Optional[str] = None) -> list[dict]:
        """Get short selling positions (空売り残高).

        Args:
            ticker: Optional stock code to filter for. If None, returns all.

        Returns:
            List of dicts with ticker, holder_name, shares_short,
            short_ratio, report_date.
        """
        html = self._fetch_page(JPX_SHORT_POSITIONS_URL)
        if not html:
            return []

        positions = self._parse_short_positions(html)

        # Also try CSV if HTML parsing yielded nothing
        if not positions:
            csv_url = self._extract_csv_link(html, JPX_SHORT_POSITIONS_URL)
            if csv_url:
                csv_text = self._fetch_csv(csv_url)
                if csv_text:
                    positions = self._parse_short_positions_csv(csv_text)

        if ticker and positions:
            positions = [p for p in positions if p.get("ticker") == ticker]

        return positions

    @staticmethod
    def _parse_short_positions(html: str) -> list[dict]:
        """Parse short position data from JPX HTML page.

        JPX short position pages list per-stock positions with columns like:
        銘柄コード, 銘柄名, 氏名又は名称, 残高割合(%), 残高数量, 報告日

        Returns:
            List of dicts with ticker, holder_name, shares_short,
            short_ratio, report_date.
        """
        positions: list[dict] = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            tables = soup.find_all("table")

            for table in tables:
                rows = table.find_all("tr")
                header_found = False

                for row in rows:
                    cells = row.find_all(["td", "th"])
                    cell_texts = [c.get_text(strip=True) for c in cells]

                    if not cell_texts:
                        continue

                    # Detect header row
                    if any("銘柄" in c for c in cell_texts):
                        header_found = True
                        continue

                    if not header_found:
                        continue

                    # Need at least ticker code and some data
                    if len(cell_texts) < 3:
                        continue

                    # Look for a 4-digit stock code in the first few cells
                    ticker_code = None
                    for cell_val in cell_texts[:2]:
                        code_match = re.match(r"^(\d{4})$", cell_val.strip())
                        if code_match:
                            ticker_code = code_match.group(1)
                            break

                    if not ticker_code:
                        continue

                    # Extract fields based on typical position
                    holder_name = cell_texts[2] if len(cell_texts) > 2 else ""
                    short_ratio = _parse_number(
                        cell_texts[3] if len(cell_texts) > 3 else None
                    )
                    shares_short = _parse_number(
                        cell_texts[4] if len(cell_texts) > 4 else None
                    )

                    # Look for a date in the row
                    report_date = None
                    for cell_val in cell_texts:
                        dm = re.search(
                            r"(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})", cell_val
                        )
                        if dm:
                            y, mo, dy = dm.groups()
                            report_date = f"{y}-{int(mo):02d}-{int(dy):02d}"
                            break

                    positions.append({
                        "ticker": ticker_code,
                        "holder_name": holder_name,
                        "shares_short": shares_short,
                        "short_ratio": short_ratio,
                        "report_date": report_date,
                    })

            logger.info(
                "Parsed %d short positions from HTML (%d bytes)",
                len(positions),
                len(html),
            )
        except Exception as e:
            logger.error("Error parsing short positions HTML: %s", e)

        return positions

    @staticmethod
    def _parse_short_positions_csv(csv_text: str) -> list[dict]:
        """Parse short positions from a JPX CSV file."""
        positions: list[dict] = []
        try:
            reader = csv.reader(io.StringIO(csv_text))
            header: list[str] = []

            for row in reader:
                if not row:
                    continue
                if any("銘柄" in cell for cell in row):
                    header = row
                    continue
                if not header or len(row) < 3:
                    continue

                ticker_code = None
                for cell_val in row[:2]:
                    code_match = re.match(r"^(\d{4})$", cell_val.strip())
                    if code_match:
                        ticker_code = code_match.group(1)
                        break

                if not ticker_code:
                    continue

                holder_name = row[2].strip() if len(row) > 2 else ""
                short_ratio = _parse_number(row[3] if len(row) > 3 else None)
                shares_short = _parse_number(row[4] if len(row) > 4 else None)

                report_date = None
                for cell_val in row:
                    dm = re.search(
                        r"(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})", cell_val
                    )
                    if dm:
                        y, mo, dy = dm.groups()
                        report_date = f"{y}-{int(mo):02d}-{int(dy):02d}"
                        break

                positions.append({
                    "ticker": ticker_code,
                    "holder_name": holder_name,
                    "shares_short": shares_short,
                    "short_ratio": short_ratio,
                    "report_date": report_date,
                })

            logger.info("Parsed %d short positions from CSV", len(positions))
        except Exception as e:
            logger.error("Error parsing short positions CSV: %s", e)

        return positions

    def get_historical_short_ratio(self, days: int = 30) -> list[dict]:
        """Get historical short selling ratios for the past N days.

        Args:
            days: Number of trading days to look back.

        Returns:
            List of dicts with date and ratio fields, most recent first.
        """
        # Try to fetch the historical CSV from the short ratio page
        html = self._fetch_page(JPX_SHORT_RATIO_URL)
        if html:
            csv_url = self._extract_csv_link(html, JPX_SHORT_RATIO_URL)
            if csv_url:
                csv_text = self._fetch_csv(csv_url)
                if csv_text:
                    historical = self._parse_short_ratio_csv_all(csv_text, days)
                    if historical:
                        return historical

        # Fallback: return current data plus placeholders
        current = self.get_short_selling_ratio()
        if not current:
            return []

        result: list[dict] = []
        if current.get("date"):
            result.append(current)

        base_date = datetime.now()
        for i in range(1, days):
            d = base_date - timedelta(days=i)
            if d.weekday() >= 5:
                continue
            result.append({
                "date": d.strftime("%Y-%m-%d"),
                "total_short_ratio": None,
                "naked_short_ratio": None,
                "short_value": None,
            })

        return result[:days]

    @staticmethod
    def _parse_short_ratio_csv_all(csv_text: str, limit: int = 30) -> list[dict]:
        """Parse all rows from a short ratio CSV file.

        Returns list of dicts sorted by date descending, up to `limit` entries.
        """
        results: list[dict] = []
        try:
            reader = csv.reader(io.StringIO(csv_text))
            header_seen = False

            for row in reader:
                if not row:
                    continue
                if any("日付" in cell for cell in row):
                    header_seen = True
                    continue
                if not header_seen or not row[0].strip():
                    continue

                date_match = re.search(
                    r"(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})", row[0]
                )
                if not date_match:
                    continue
                y, m, d = date_match.groups()
                date_str = f"{y}-{int(m):02d}-{int(d):02d}"

                results.append({
                    "date": date_str,
                    "total_short_ratio": _parse_number(
                        row[1] if len(row) > 1 else None
                    ),
                    "naked_short_ratio": _parse_number(
                        row[2] if len(row) > 2 else None
                    ),
                    "short_value": _parse_number(
                        row[3] if len(row) > 3 else None
                    ),
                })

            # Sort descending by date and limit
            results.sort(key=lambda x: x["date"] or "", reverse=True)
            results = results[:limit]
            logger.info("Parsed %d historical short ratio entries from CSV", len(results))
        except Exception as e:
            logger.error("Error parsing historical short ratio CSV: %s", e)

        return results


def _empty_ratio() -> dict:
    """Return an empty but well-structured short ratio dict."""
    return {
        "date": None,
        "total_short_ratio": None,
        "naked_short_ratio": None,
        "short_value": None,
    }


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
