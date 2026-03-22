"""J-Quants API client for Japanese market data."""

import logging
import os
import time
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.jquants.com/v1/"


class JQuantsClient:
    """Client for the J-Quants API (https://jpx-jquants.com/)."""

    def __init__(self) -> None:
        self._api_key: str = os.environ.get("JQUANTS_API_KEY", "")
        if not self._api_key:
            logger.warning("JQUANTS_API_KEY not set in environment")
        self._id_token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _refresh_token(self) -> None:
        """Obtain or refresh the id_token via the refresh-token endpoint."""
        try:
            # Step 1: get refresh token using the API key
            resp = self._session.post(
                f"{BASE_URL}token/auth_user",
                headers={"Content-Type": "application/json"},
                json={"mailaddress": "", "password": ""},  # API-key flow
                params={"apikey": self._api_key},
                timeout=30,
            )
            resp.raise_for_status()
            refresh_token = resp.json().get("refreshToken")
            if not refresh_token:
                logger.error("No refreshToken in auth response")
                return

            # Step 2: exchange refresh token for id token
            resp2 = self._session.post(
                f"{BASE_URL}token/auth_refresh",
                params={"refreshtoken": refresh_token},
                timeout=30,
            )
            resp2.raise_for_status()
            self._id_token = resp2.json().get("idToken")
            # Tokens are valid for ~24 hours; refresh after 23 hours
            self._token_expiry = time.time() + 23 * 3600
        except Exception as e:
            logger.error("J-Quants token refresh failed: %s", e)
            self._id_token = None

    def _get_headers(self) -> dict:
        """Return auth headers, refreshing the token if needed."""
        if not self._id_token or time.time() >= self._token_expiry:
            self._refresh_token()
        return {"Authorization": f"Bearer {self._id_token}"} if self._id_token else {}

    def _get(self, endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
        """Issue an authenticated GET request."""
        url = f"{BASE_URL}{endpoint}"
        try:
            resp = self._session.get(
                url,
                headers=self._get_headers(),
                params=params or {},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("J-Quants GET %s failed: %s", endpoint, e)
            return None

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def get_listed_stocks(self) -> pd.DataFrame:
        """Get all listed stocks on the Tokyo Stock Exchange.

        Returns:
            DataFrame with columns like Code, CompanyName, Sector33Code, etc.
        """
        data = self._get("listed/info")
        if not data or "info" not in data:
            return pd.DataFrame()
        return pd.DataFrame(data["info"])

    def get_daily_quotes(
        self, ticker: str, from_date: str, to_date: str
    ) -> pd.DataFrame:
        """Get daily OHLCV quotes for a stock.

        Args:
            ticker: Stock code (e.g. "72030").
            from_date: Start date "YYYY-MM-DD".
            to_date: End date "YYYY-MM-DD".

        Returns:
            DataFrame with daily quote data.
        """
        params = {"code": ticker, "from": from_date, "to": to_date}
        data = self._get("prices/daily_quotes", params=params)
        if not data or "daily_quotes" not in data:
            return pd.DataFrame()
        return pd.DataFrame(data["daily_quotes"])

    def get_financial_statements(self, ticker: str) -> dict:
        """Get financial statements / earnings for a company.

        Args:
            ticker: Stock code.

        Returns:
            Dict with financial statement data.
        """
        data = self._get("fins/statements", params={"code": ticker})
        if not data:
            return {}
        return data

    def get_trading_calendar(self) -> list:
        """Get TSE trading calendar (business days).

        Returns:
            List of dicts with Date and HolidayDivision keys.
        """
        data = self._get("markets/trading_calendar")
        if not data or "trading_calendar" not in data:
            return []
        return data["trading_calendar"]
