"""EDINET API client for Japanese corporate filings (EDGAR equivalent)."""

import logging
import os
import re
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.edinet-fsa.go.jp/api/v2/"


class EdinetClient:
    """Client for the EDINET API (Financial Services Agency of Japan)."""

    def __init__(self) -> None:
        self._api_key: str = os.environ.get("EDINET_API_KEY", "")
        if not self._api_key:
            logger.warning("EDINET_API_KEY not set in environment")
        self._session = requests.Session()

    def _get(self, endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
        """Issue a GET request to the EDINET API."""
        url = f"{BASE_URL}{endpoint}"
        request_params: dict[str, Any] = {"Subscription-Key": self._api_key}
        if params:
            request_params.update(params)
        try:
            resp = self._session.get(url, params=request_params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("EDINET GET %s failed: %s", endpoint, e)
            return None

    def get_large_holdings(self, ticker: str) -> list[dict]:
        """Get large shareholding reports (大量保有報告書) for a stock.

        Args:
            ticker: Stock code (e.g. "7203").

        Returns:
            List of parsed holding dicts with filer_name, shares_held,
            ownership_pct, purpose, filing_date.
        """
        data = self._get(
            "documents.json",
            params={
                "type": 2,  # metadata + results
                "secCode": ticker,
                "docTypeCode": "060",  # 大量保有報告書
            },
        )
        if not data or "results" not in data:
            logger.warning("No large holdings data for %s", ticker)
            return []

        return _parse_large_holdings(data["results"])

    def search_filings(
        self, keyword: str, filing_type: Optional[str] = None
    ) -> list[dict]:
        """Search EDINET filings by keyword and optional filing type.

        Args:
            keyword: Search term (company name, ticker, etc.).
            filing_type: Optional EDINET docTypeCode (e.g. "120" for annual report,
                         "060" for large holdings, "140" for quarterly report).

        Returns:
            List of matching filing dicts.
        """
        params: dict[str, Any] = {"type": 2, "keyword": keyword}
        if filing_type:
            params["docTypeCode"] = filing_type
        data = self._get("documents.json", params=params)
        if not data or "results" not in data:
            return []
        return data["results"]

    def get_filing_document(self, doc_id: str) -> dict:
        """Get a specific filing document by its document ID.

        Args:
            doc_id: EDINET document ID.

        Returns:
            Dict with document metadata and content references.
        """
        data = self._get(f"documents/{doc_id}", params={"type": 1})
        if not data:
            return {}
        return data

    def get_financial_statements(self, ticker: str) -> dict:
        """Get key financial metrics from the latest annual report.

        Searches for the most recent annual securities report (有価証券報告書)
        and extracts key financial metrics.

        Args:
            ticker: Stock code (e.g. "7203").

        Returns:
            Dict with revenue, operating_income, net_income, eps, bps,
            filing_date, and doc_id. Returns empty-structured dict on failure.
        """
        try:
            data = self._get(
                "documents.json",
                params={
                    "type": 2,
                    "secCode": ticker,
                    "docTypeCode": "120",  # 有価証券報告書 (annual report)
                },
            )
            if not data or "results" not in data:
                logger.warning("No financial statements found for %s", ticker)
                return _empty_financials()

            results = data["results"]
            if not results:
                return _empty_financials()

            # Sort by filing date descending to get the most recent
            results_sorted = sorted(
                results,
                key=lambda x: x.get("submitDateTime", x.get("filingDate", "")),
                reverse=True,
            )

            latest = results_sorted[0]
            doc_id = latest.get("docID", "")

            parsed = _empty_financials()
            parsed["filing_date"] = latest.get(
                "submitDateTime", latest.get("filingDate")
            )
            parsed["doc_id"] = doc_id
            parsed["filer_name"] = latest.get("filerName", "")
            parsed["period_start"] = latest.get("periodStart")
            parsed["period_end"] = latest.get("periodEnd")
            parsed["doc_description"] = latest.get("docDescription", "")

            # Try to fetch the actual document for XBRL data
            if doc_id:
                financials = self._extract_financials_from_doc(doc_id)
                if financials:
                    parsed.update(financials)

            return parsed
        except Exception as e:
            logger.error("Error getting financial statements for %s: %s", ticker, e)
            return _empty_financials()

    def _extract_financials_from_doc(self, doc_id: str) -> dict:
        """Extract financial metrics from an EDINET XBRL document.

        Args:
            doc_id: EDINET document ID.

        Returns:
            Dict with extracted financial metrics, or empty dict on failure.
        """
        try:
            # Fetch the document with type=5 (XBRL data)
            url = f"{BASE_URL}documents/{doc_id}"
            resp = self._session.get(
                url,
                params={"type": 5, "Subscription-Key": self._api_key},
                timeout=60,
            )
            resp.raise_for_status()

            # The response may be JSON with XBRL-parsed data
            data = resp.json() if "json" in resp.headers.get("Content-Type", "") else {}
            if not data:
                return {}

            return _extract_xbrl_financials(data)
        except Exception as e:
            logger.debug("Could not extract XBRL financials for %s: %s", doc_id, e)
            return {}


def _parse_large_holdings(results: list[dict]) -> list[dict]:
    """Parse raw EDINET large holding results into structured dicts.

    Args:
        results: Raw results list from EDINET API.

    Returns:
        List of parsed holding dicts.
    """
    parsed: list[dict] = []
    for item in results:
        try:
            # Extract filer name from the document description or filer fields
            filer_name = item.get("filerName", "")
            doc_desc = item.get("docDescription", "")

            # Try to extract ownership percentage from the description
            ownership_pct = _extract_percentage(doc_desc)

            # Try to extract share count from the description
            shares_held = _extract_shares(doc_desc)

            # Extract purpose if available
            purpose = _extract_purpose(doc_desc)

            filing_date = item.get(
                "submitDateTime", item.get("filingDate")
            )

            parsed.append({
                "filer_name": filer_name,
                "shares_held": shares_held,
                "ownership_pct": ownership_pct,
                "purpose": purpose,
                "filing_date": filing_date,
                "doc_id": item.get("docID", ""),
                "doc_description": doc_desc,
                "sec_code": item.get("secCode", ""),
                "doc_type_code": item.get("docTypeCode", ""),
            })
        except Exception as e:
            logger.warning("Error parsing large holding item: %s", e)
            continue

    # Sort by filing date descending
    parsed.sort(
        key=lambda x: x.get("filing_date") or "",
        reverse=True,
    )
    return parsed


def _extract_percentage(text: str) -> Optional[float]:
    """Extract an ownership percentage from filing description text."""
    if not text:
        return None
    # Look for patterns like "12.34%" or "12.34％"
    match = re.search(r"(\d+\.?\d*)\s*[%％]", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


def _extract_shares(text: str) -> Optional[int]:
    """Extract a share count from filing description text."""
    if not text:
        return None
    # Look for patterns like "1,234,567株" or "1234567shares"
    match = re.search(r"([\d,]+)\s*株", text)
    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _extract_purpose(text: str) -> Optional[str]:
    """Extract investment purpose from filing description text."""
    if not text:
        return None
    # Common purpose keywords in large holding reports
    purposes = [
        "純投資",           # pure investment
        "政策投資",         # strategic investment
        "経営参加",         # management participation
        "重要提案行為",     # significant proposal
        "保有目的",         # holding purpose
    ]
    for purpose in purposes:
        if purpose in text:
            return purpose
    return None


def _extract_xbrl_financials(data: dict) -> dict:
    """Extract key financial metrics from XBRL JSON data.

    Looks for common XBRL taxonomy elements for Japanese GAAP / IFRS.
    """
    result: dict = {}

    # Common XBRL element names for key metrics (JP-GAAP and IFRS)
    revenue_keys = [
        "Revenue", "NetSales", "jppfs_cor:NetSales",
        "jppfs_cor:Revenue", "Revenues",
        "jppfs_cor:OperatingRevenue1",
    ]
    op_income_keys = [
        "OperatingIncome", "jppfs_cor:OperatingIncome",
        "OperatingProfit",
    ]
    net_income_keys = [
        "ProfitLossAttributableToOwnersOfParent",
        "jppfs_cor:ProfitLossAttributableToOwnersOfParent",
        "NetIncome", "jppfs_cor:NetIncome",
        "ProfitLoss",
    ]
    eps_keys = [
        "BasicEarningsLossPerShare",
        "jppfs_cor:BasicEarningsLossPerShare",
        "EarningsPerShare",
    ]
    bps_keys = [
        "NetAssetsPerShare", "jppfs_cor:NetAssetsPerShare",
        "BookValuePerShare",
    ]

    def _find_value(keys: list[str]) -> Optional[float]:
        for key in keys:
            val = _deep_find(data, key)
            if val is not None:
                try:
                    return float(str(val).replace(",", ""))
                except (ValueError, TypeError):
                    continue
        return None

    result["revenue"] = _find_value(revenue_keys)
    result["operating_income"] = _find_value(op_income_keys)
    result["net_income"] = _find_value(net_income_keys)
    result["eps"] = _find_value(eps_keys)
    result["bps"] = _find_value(bps_keys)

    return result


def _deep_find(data: Any, key: str) -> Any:
    """Recursively search for a key in nested dict/list structures."""
    if isinstance(data, dict):
        if key in data:
            return data[key]
        for v in data.values():
            found = _deep_find(v, key)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _deep_find(item, key)
            if found is not None:
                return found
    return None


def _empty_financials() -> dict:
    """Return an empty but well-structured financials dict."""
    return {
        "revenue": None,
        "operating_income": None,
        "net_income": None,
        "eps": None,
        "bps": None,
        "filing_date": None,
        "doc_id": None,
        "filer_name": None,
        "period_start": None,
        "period_end": None,
        "doc_description": None,
    }
