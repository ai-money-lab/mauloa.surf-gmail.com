"""
KabuStation API Client
kabuステーション REST API (au kabucom Securities / auカブコム証券)

kabuステーション runs locally and exposes a REST API on localhost:18080.
Documentation: https://kabucom.github.io/kabusapi/reference/

Exchange codes:
  1  = TSE (東証)
  2  = NSE (名証)
  23 = J-NFX (日通し先物)
  24 = OSE  (大証先物・オプション)

Nikkei 225 mini futures symbol format: e.g. "167060019" (contract month encoded)
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta

import requests

logger = logging.getLogger(__name__)

# Side mapping: human-readable -> kabuステーション API value
_SIDE_MAP = {
    "buy": "2",   # 買い
    "sell": "1",   # 売り
}

# Order type mapping
_ORDER_TYPE_MAP = {
    "market": "1",  # 成行
    "limit": "2",   # 指値
}


class KabuStationAPI:
    """Client for the kabuステーション local REST API."""

    BASE_URL = "http://localhost:18080"

    def __init__(self, password: str | None = None) -> None:
        """
        Initialise the API client.

        Args:
            password: API password. Falls back to KABU_API_PASSWORD env var.
        """
        self.password = password or os.environ.get("KABU_API_PASSWORD", "")
        self.order_password = os.environ.get("KABU_ORDER_PASSWORD", self.password)
        if not self.password:
            logger.warning("KABU_API_PASSWORD is not set – authentication will fail")

        self._token: str | None = None
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _get_token(self) -> str:
        """
        Obtain an API token via POST /kabusapi/token.

        Returns:
            The bearer token string.

        Raises:
            RuntimeError: If the token request fails.
        """
        url = f"{self.BASE_URL}/kabusapi/token"
        payload = {"APIPassword": self.password}

        logger.debug("Requesting token from %s", url)
        try:
            resp = self._session.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            token = data.get("Token", "")
            if not token:
                raise RuntimeError(f"Token response missing Token field: {data}")
            self._token = token
            self._session.headers["X-API-KEY"] = self._token
            logger.info("kabuステーション token acquired")
            return self._token
        except requests.RequestException as exc:
            logger.error("Token request failed: %s", exc)
            raise RuntimeError(f"Failed to obtain kabuステーション token: {exc}") from exc

    def _ensure_token(self) -> None:
        """Ensure we have a valid token, fetching one if needed."""
        if self._token is None:
            self._get_token()

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    def get_board(self, symbol: str, exchange: int = 1) -> dict:
        """
        Fetch current quote / board info (板情報).

        Args:
            symbol: Security code (e.g. "9433" or futures symbol).
            exchange: Exchange code (1=TSE, 2=NSE, 23=J-NFX, 24=OSE).

        Returns:
            Board data dict from the API.
        """
        self._ensure_token()
        url = f"{self.BASE_URL}/kabusapi/board/{symbol}@{exchange}"

        logger.debug("GET board: %s", url)
        try:
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            logger.debug("Board response for %s: price=%s", symbol, data.get("CurrentPrice"))
            return data
        except requests.RequestException as exc:
            logger.error("get_board failed for %s@%d: %s", symbol, exchange, exc)
            return {"error": str(exc), "symbol": symbol, "exchange": exchange}

    # ------------------------------------------------------------------
    # Order management
    # ------------------------------------------------------------------

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        order_type: str = "market",
        price: float | None = None,
        exchange: int = 1,
    ) -> dict:
        """
        Place an order.

        Args:
            symbol: Security code.
            side: "buy" or "sell".
            qty: Number of shares/contracts.
            order_type: "market" or "limit".
            price: Required for limit orders.
            exchange: Exchange code (default 1=TSE).

        Returns:
            Order response dict (contains OrderId on success).
        """
        self._ensure_token()

        if side not in _SIDE_MAP:
            raise ValueError(f"Invalid side '{side}'. Must be 'buy' or 'sell'.")
        if order_type not in _ORDER_TYPE_MAP:
            raise ValueError(f"Invalid order_type '{order_type}'. Must be 'market' or 'limit'.")
        if order_type == "limit" and price is None:
            raise ValueError("price is required for limit orders")

        url = f"{self.BASE_URL}/kabusapi/sendorder"

        # ExpireDay: 0=当日, YYYYMMDD=指定日まで有効
        # 指値注文は5営業日有効（当日限りだと失効リスクあり）
        if order_type == "market":
            expire_day = 0  # 成行は当日
        else:
            # 指値: 5営業日後まで有効
            expire_date = date.today() + timedelta(days=7)  # 土日含めて7日=約5営業日
            expire_day = int(expire_date.strftime("%Y%m%d"))

        payload = {
            "Password": self.order_password,
            "Symbol": symbol,
            "Exchange": exchange,
            "SecurityType": 1,  # 1=株式 (stock)
            "Side": _SIDE_MAP[side],
            "CashMargin": 1,     # 1=現物 (cash)
            "DelivType": 2,      # 2=お預り金 (deposit)
            "AccountType": 2,    # 2=特定 (specific account)
            "Qty": qty,
            "FrontOrderType": 10 if order_type == "market" else 20,  # 10=成行, 20=指値
            "Price": 0 if order_type == "market" else price,
            "ExpireDay": expire_day,
        }

        logger.info(
            "Placing %s %s order: %s x%d @ %s",
            side, order_type, symbol, qty, price or "MARKET",
        )
        try:
            resp = self._session.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            logger.info("Order placed: %s", data.get("OrderId", data))
            return data
        except requests.RequestException as exc:
            logger.error("place_order failed: %s", exc)
            return {"error": str(exc), "symbol": symbol, "side": side}

    def cancel_order(self, order_id: str) -> dict:
        """
        Cancel an active order.

        Args:
            order_id: The order ID returned from place_order.

        Returns:
            Cancellation response dict.
        """
        self._ensure_token()
        url = f"{self.BASE_URL}/kabusapi/cancelorder"
        payload = {
            "OrderId": order_id,
            "Password": self.password,
        }

        logger.info("Cancelling order: %s", order_id)
        try:
            resp = self._session.put(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            logger.info("Order cancelled: %s", data)
            return data
        except requests.RequestException as exc:
            logger.error("cancel_order failed for %s: %s", order_id, exc)
            return {"error": str(exc), "order_id": order_id}

    # ------------------------------------------------------------------
    # Position & order queries
    # ------------------------------------------------------------------

    def get_positions(self) -> list[dict]:
        """
        Get current open positions.

        Returns:
            List of position dicts.
        """
        self._ensure_token()
        url = f"{self.BASE_URL}/kabusapi/positions"

        logger.debug("GET positions")
        try:
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            logger.debug("Positions: %d items", len(data) if isinstance(data, list) else 0)
            return data if isinstance(data, list) else []
        except requests.RequestException as exc:
            logger.error("get_positions failed: %s", exc)
            return []

    def get_orders(self) -> list[dict]:
        """
        Get active/recent orders.

        Returns:
            List of order dicts.
        """
        self._ensure_token()
        url = f"{self.BASE_URL}/kabusapi/orders"

        logger.debug("GET orders")
        try:
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            logger.debug("Orders: %d items", len(data) if isinstance(data, list) else 0)
            return data if isinstance(data, list) else []
        except requests.RequestException as exc:
            logger.error("get_orders failed: %s", exc)
            return []
