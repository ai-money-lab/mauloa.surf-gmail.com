"""EDINET API client for Japanese corporate filings (EDGAR equivalent)."""

import logging
import os
from typing import Optional

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
        request_params = {"Subscription-Key": self._api_key}
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
            List of filing dicts with holder info, share counts, etc.
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
            return []
        return data["results"]

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
        params: dict = {"type": 2, "keyword": keyword}
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
