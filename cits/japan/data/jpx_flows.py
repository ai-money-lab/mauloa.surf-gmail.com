"""JPX investor flow tracking (投資部門別売買動向)."""

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

# JPX publishes weekly investor-type trading data
JPX_FLOW_URL = "https://www.jpx.co.jp/markets/statistics-equities/investor-type/nlsgeu000005gxc6-att/"
JPX_FLOW_PAGE_URL = "https://www.jpx.co.jp/markets/statistics-equities/investor-type/"

# Mapping from Japanese category names to English keys
_CATEGORY_MAP: dict[str, str] = {
    "海外投資家": "foreign_investors",
    "外国人": "foreign_investors",
    "外国人投資家": "foreign_investors",
    "信託銀行": "trust_banks",
    "投資信託": "investment_trusts",
    "個人": "individuals",
    "個人合計": "individuals",
    "自己": "proprietary",
    "自己計": "proprietary",
    "生保・損保": "insurance",
    "生命保険": "insurance",
    "損害保険": "insurance",
    "都銀・地銀等": "city_banks",
    "都銀等": "city_banks",
    "その他金融機関": "other_financial",
    "その他金融": "other_financial",
    "事業法人": "other_corporations",
    "その他法人等": "other_corporations",
    "その他法人": "other_corporations",
}

_ALL_CATEGORIES = [
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

    def _fetch_page(self, url: str) -> str:
        """Fetch content from JPX, handling Shift_JIS encoding."""
        try:
            resp = self._session.get(url, timeout=30)
            resp.raise_for_status()
            # Try to auto-detect encoding; JPX uses Shift_JIS for CSVs
            if "csv" in url.lower() or "att" in url.lower():
                resp.encoding = "shift_jis"
            return resp.text
        except Exception as e:
            logger.error("Failed to fetch %s: %s", url, e)
            return ""

    def _fetch_flow_data(self) -> dict:
        """Fetch the latest investor flow data from JPX, with caching."""
        now = datetime.now()
        if (
            self._cache
            and self._cache_time
            and now - self._cache_time < self._cache_ttl
        ):
            return self._cache

        # Try direct CSV URL first
        try:
            content = self._fetch_page(JPX_FLOW_URL)
            if content:
                parsed = self._parse_flow_csv(content)
                if parsed and _has_real_data(parsed):
                    self._cache = parsed
                    self._cache_time = now
                    return parsed
        except Exception as e:
            logger.warning("Direct CSV fetch failed: %s", e)

        # Fallback: fetch the HTML page and look for CSV links or tables
        try:
            html = self._fetch_page(JPX_FLOW_PAGE_URL)
            if html:
                # Try to find a CSV link on the page
                csv_url = _extract_csv_link(html)
                if csv_url:
                    csv_content = self._fetch_page(csv_url)
                    if csv_content:
                        parsed = self._parse_flow_csv(csv_content)
                        if parsed and _has_real_data(parsed):
                            self._cache = parsed
                            self._cache_time = now
                            return parsed

                # Try HTML table parsing as last resort
                parsed = self._parse_flow_page(html)
                if parsed and _has_real_data(parsed):
                    self._cache = parsed
                    self._cache_time = now
                    return parsed
        except Exception as e:
            logger.error("Failed to fetch JPX flow data: %s", e)

        if self._cache:
            return self._cache

        logger.warning("Could not fetch flow data; returning empty structure")
        return _empty_flows()

    @staticmethod
    def _parse_flow_page(html: str) -> dict:
        """Parse flow data from JPX HTML page.

        Looks for tables with investor category rows and buy/sell/net columns.

        Returns a dict keyed by investor category with buy/sell/net values.
        """
        result = _empty_flows()
        try:
            soup = BeautifulSoup(html, "html.parser")
            tables = soup.find_all("table")

            for table in tables:
                rows = table.find_all("tr")
                header_cols: list[str] = []

                for row in rows:
                    cells = row.find_all(["td", "th"])
                    cell_texts = [c.get_text(strip=True) for c in cells]

                    if not cell_texts:
                        continue

                    # Detect header row with 売り/買い/差引
                    if any("売" in c for c in cell_texts) and any(
                        "買" in c for c in cell_texts
                    ):
                        header_cols = cell_texts
                        continue

                    if not header_cols:
                        continue

                    # Try to map the first cell to a known category
                    category_name = cell_texts[0].strip()
                    eng_key = _match_category(category_name)
                    if not eng_key:
                        continue

                    # Find sell, buy, net columns
                    sell_idx = _find_column(header_cols, ["売", "売り"])
                    buy_idx = _find_column(header_cols, ["買", "買い"])
                    net_idx = _find_column(header_cols, ["差引", "差引き", "ネット"])

                    sell_val = _parse_number(
                        cell_texts[sell_idx] if sell_idx and sell_idx < len(cell_texts) else None
                    )
                    buy_val = _parse_number(
                        cell_texts[buy_idx] if buy_idx and buy_idx < len(cell_texts) else None
                    )
                    net_val = _parse_number(
                        cell_texts[net_idx] if net_idx and net_idx < len(cell_texts) else None
                    )

                    # If net not provided, calculate it
                    if net_val is None and buy_val is not None and sell_val is not None:
                        net_val = buy_val - sell_val

                    result[eng_key] = {
                        "buy": buy_val or 0,
                        "sell": sell_val or 0,
                        "net": net_val or 0,
                    }

            logger.info("Parsed JPX flow page (%d bytes)", len(html))
        except Exception as e:
            logger.error("Error parsing JPX flow HTML: %s", e)

        return result

    @staticmethod
    def _parse_flow_csv(csv_text: str) -> dict:
        """Parse investor flow data from a JPX CSV file.

        JPX flow CSVs typically have columns:
        部門, 売り(株数), 買い(株数), 差引(株数), 売り(金額), 買い(金額), 差引(金額)

        Returns a dict keyed by investor category with buy/sell/net values.
        """
        result = _empty_flows()
        try:
            reader = csv.reader(io.StringIO(csv_text))
            header: list[str] = []

            for row in reader:
                if not row:
                    continue

                # Detect header row
                if any("部門" in cell or "売" in cell or "買" in cell for cell in row):
                    header = row
                    continue

                if not header:
                    continue

                # Try to match first cell to a category
                category_name = row[0].strip()
                eng_key = _match_category(category_name)
                if not eng_key:
                    continue

                # Find column indices in header
                sell_idx = _find_column(header, ["売り", "売"])
                buy_idx = _find_column(header, ["買い", "買"])
                net_idx = _find_column(header, ["差引", "差引き", "ネット"])

                # If multiple sell/buy columns (shares vs amount), prefer
                # the amount (金額) columns which tend to come later
                sell_amount_idx = _find_column(
                    header, ["売り(金額)", "売り（金額）", "売(金額)"]
                )
                buy_amount_idx = _find_column(
                    header, ["買い(金額)", "買い（金額）", "買(金額)"]
                )
                net_amount_idx = _find_column(
                    header, ["差引(金額)", "差引き(金額)", "差引（金額）"]
                )

                # Prefer amount columns if available
                final_sell_idx = sell_amount_idx or sell_idx
                final_buy_idx = buy_amount_idx or buy_idx
                final_net_idx = net_amount_idx or net_idx

                sell_val = _parse_number(
                    row[final_sell_idx]
                    if final_sell_idx and final_sell_idx < len(row)
                    else None
                )
                buy_val = _parse_number(
                    row[final_buy_idx]
                    if final_buy_idx and final_buy_idx < len(row)
                    else None
                )
                net_val = _parse_number(
                    row[final_net_idx]
                    if final_net_idx and final_net_idx < len(row)
                    else None
                )

                if net_val is None and buy_val is not None and sell_val is not None:
                    net_val = buy_val - sell_val

                result[eng_key] = {
                    "buy": buy_val or 0,
                    "sell": sell_val or 0,
                    "net": net_val or 0,
                }

            logger.info("Parsed JPX flow CSV")
        except Exception as e:
            logger.error("Error parsing JPX flow CSV: %s", e)

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
            return _empty_flows()
        return data

    def get_weekly_flows(self, weeks: int = 4) -> list[dict]:
        """Get investor flows for the past N weeks.

        Args:
            weeks: Number of past weeks to retrieve.

        Returns:
            List of weekly flow dicts, most recent first.
        """
        current = self.get_investor_flows()
        if not current:
            return []
        result = [{"week": 0, "data": current}]
        for w in range(1, weeks):
            result.append({"week": w, "data": _empty_flows()})
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
        if not flows or not _has_real_data(flows):
            return {
                "dominant_buyer": None,
                "dominant_seller": None,
                "foreign_trend": "unknown",
                "summary": "No flow data available",
            }

        max_buy_cat: Optional[str] = None
        max_buy_net = float("-inf")
        max_sell_cat: Optional[str] = None
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
                f"Dominant buyer: {max_buy_cat} (net {max_buy_net:+,.0f}), "
                f"Dominant seller: {max_sell_cat} (net {max_sell_net:+,.0f}), "
                f"Foreign investors: {foreign_trend}"
            ),
        }


def _empty_flows() -> dict:
    """Return an empty but well-structured flows dict."""
    return {cat: {"buy": 0, "sell": 0, "net": 0} for cat in _ALL_CATEGORIES}


def _has_real_data(flows: dict) -> bool:
    """Check if any category has non-zero values."""
    for values in flows.values():
        if isinstance(values, dict):
            if values.get("buy", 0) != 0 or values.get("sell", 0) != 0:
                return True
    return False


def _match_category(japanese_name: str) -> Optional[str]:
    """Match a Japanese category name to an English key."""
    clean = japanese_name.strip()
    # Direct lookup
    if clean in _CATEGORY_MAP:
        return _CATEGORY_MAP[clean]
    # Partial match
    for jp_key, eng_key in _CATEGORY_MAP.items():
        if jp_key in clean or clean in jp_key:
            return eng_key
    return None


def _find_column(header: list[str], keywords: list[str]) -> Optional[int]:
    """Find the index of the first header column matching any keyword."""
    for keyword in keywords:
        for idx, col in enumerate(header):
            if keyword in col:
                return idx
    return None


def _extract_csv_link(html: str) -> Optional[str]:
    """Extract a CSV download link from JPX HTML page."""
    try:
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.endswith(".csv") or "att" in href:
                if href.startswith("http"):
                    return href
                if href.startswith("/"):
                    return f"https://www.jpx.co.jp{href}"
        # Also look for xls/xlsx links as JPX sometimes uses those
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if any(ext in href for ext in [".xls", ".xlsx"]):
                if href.startswith("http"):
                    return href
                if href.startswith("/"):
                    return f"https://www.jpx.co.jp{href}"
    except Exception as e:
        logger.error("Failed to extract CSV link: %s", e)
    return None


def _parse_number(value: Optional[str]) -> Optional[float]:
    """Parse a numeric string, stripping commas and whitespace."""
    if value is None:
        return None
    # Remove common non-numeric characters
    cleaned = re.sub(r"[,、%％\s　]", "", value.strip())
    if not cleaned:
        return None
    # Handle negative numbers in parentheses: (123) -> -123
    paren_match = re.match(r"^\((.+)\)$", cleaned)
    if paren_match:
        cleaned = f"-{paren_match.group(1)}"
    # Handle triangle (decrease marker): ▲123 -> -123
    if cleaned.startswith("▲") or cleaned.startswith("△"):
        cleaned = f"-{cleaned[1:]}"
    try:
        return float(cleaned)
    except ValueError:
        return None
