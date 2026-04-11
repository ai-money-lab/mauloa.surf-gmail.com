"""
KabuStation API Client
kabuステーション REST API (au kabucom Securities / auカブコム証券)

Correct parameters per https://github.com/kabucom/kabusapi/issues/1014:
- Side: int (1=sell, 2=buy) NOT string
- AccountType: 4 (特定口座)
- FundType: "  " (2 spaces = 保護預り) for cash
- DelivType: 0 for sell, 2 for buy
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta

import requests

logger = logging.getLogger(__name__)

_SIDE_MAP = {
    "buy": 2,   # 買い (int)
    "sell": 1,  # 売り (int)
}

_ORDER_TYPE_MAP = {
    "market": 1,
    "limit": 2,
}


class KabuStationAPI:
    """Client for the kabuステーション local REST API."""

    BASE_URL = "http://localhost:18080"

    def __init__(self, password: str | None = None) -> None:
        self.password = password or os.environ.get("KABU_API_PASSWORD", "")
        if not self.password:
            logger.warning("KABU_API_PASSWORD is not set")

        self._token: str | None = None
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def _get_token(self) -> str:
        url = f"{self.BASE_URL}/kabusapi/token"
        payload = {"APIPassword": self.password}
        try:
            resp = self._session.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            token = data.get("Token", "")
            if not token:
                raise RuntimeError(f"Token response missing: {data}")
            self._token = token
            self._session.headers["X-API-KEY"] = token
            logger.info("Token obtained")
            return token
        except requests.RequestException as exc:
            logger.error("Token request failed: %s", exc)
            raise

    def _ensure_token(self) -> None:
        if self._token is None:
            self._get_token()

    def get_board(self, symbol: str, exchange: int = 1) -> dict:
        self._ensure_token()
        url = f"{self.BASE_URL}/kabusapi/board/{symbol}@{exchange}"
        try:
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error("get_board failed: %s", exc)
            return {"error": str(exc), "symbol": symbol}

    def get_positions(self) -> list[dict]:
        self._ensure_token()
        url = f"{self.BASE_URL}/kabusapi/positions"
        try:
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except requests.RequestException as exc:
            logger.error("get_positions failed: %s", exc)
            return []

    def get_orders(self) -> list[dict]:
        self._ensure_token()
        url = f"{self.BASE_URL}/kabusapi/orders"
        try:
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except requests.RequestException as exc:
            logger.error("get_orders failed: %s", exc)
            return []

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        order_type: str = "market",
        price: float | None = None,
        exchange: int = 1,
    ) -> dict:
        """Place an order using correct kabuStation API parameters."""
        self._ensure_token()

        if side not in _SIDE_MAP:
            raise ValueError(f"Invalid side '{side}'. Must be 'buy' or 'sell'.")
        if order_type not in _ORDER_TYPE_MAP:
            raise ValueError(f"Invalid order_type '{order_type}'. Must be 'market' or 'limit'.")
        if order_type == "limit" and price is None:
            raise ValueError("price is required for limit orders")

        url = f"{self.BASE_URL}/kabusapi/sendorder"

        # ExpireDay: limit orders valid for 7 days (5 business days)
        if order_type == "market":
            expire_day = 0
        else:
            expire_date = date.today() + timedelta(days=7)
            expire_day = int(expire_date.strftime("%Y%m%d"))

        # kabuStation API sendorder parameters (per GitHub issue #1014)
        is_buy = side == "buy"
        deliv_type = 2 if is_buy else 0  # 2=お預り金 (buy), 0=sell

        payload = {
            "Password": self.password,
            "Symbol": symbol,
            "Exchange": exchange,
            "SecurityType": 1,
            "Side": _SIDE_MAP[side],    # int
            "CashMargin": 1,             # 現物
            "DelivType": deliv_type,
            "FundType": "  ",            # 2 spaces = 保護預り
            "AccountType": 4,            # 特定口座
            "Qty": qty,
            "FrontOrderType": 10 if order_type == "market" else 20,
            "Price": 0 if order_type == "market" else price,
            "ExpireDay": expire_day,
        }

        logger.info(
            "Placing %s %s order: %s x%d @ %s (exchange=%d)",
            side, order_type, symbol, qty, price or "MARKET", exchange,
        )
        try:
            resp = self._session.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            logger.info("Order placed: %s", data.get("OrderId", data))
            return data
        except requests.RequestException as exc:
            err_body = ""
            if hasattr(exc, "response") and exc.response is not None:
                try:
                    err_body = exc.response.text[:500]
                except Exception:
                    pass
            logger.error("place_order failed: %s body=%s", exc, err_body)
            return {"error": str(exc), "body": err_body, "symbol": symbol, "side": side}

    def cancel_order(self, order_id: str) -> dict:
        self._ensure_token()
        url = f"{self.BASE_URL}/kabusapi/cancelorder"
        payload = {
            "OrderId": order_id,
            "Password": self.password,
        }
        try:
            resp = self._session.put(url, json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error("cancel_order failed: %s", exc)
            return {"error": str(exc), "order_id": order_id}
