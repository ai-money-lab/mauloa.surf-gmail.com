"""
Tachibana Securities API Client
立花証券 e-Support API v4r3

Base URL: https://kabuka.e-shiten.jp/e_api_v4r3/
Authentication: POST login returns session token (p_sd_date)
All requests use POST with JSON body.
"""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

# Side mapping: human-readable -> Tachibana API value
_SIDE_MAP = {
    "buy": "3",   # 買い
    "sell": "1",   # 売り
}

# Order type mapping
_ORDER_TYPE_MAP = {
    "market": "*",   # 成行
    "limit": "limit",  # 指値 (use actual price)
}


class TachibanaAPI:
    """Client for the 立花証券 e-Support API."""

    BASE_URL = "https://kabuka.e-shiten.jp/e_api_v4r3"

    def __init__(
        self,
        user_id: str | None = None,
        password: str | None = None,
    ) -> None:
        """
        Initialise the Tachibana API client.

        Args:
            user_id: User ID. Falls back to TACHIBANA_USER_ID env var.
            password: Password. Falls back to TACHIBANA_PASSWORD env var.
        """
        self.user_id: str = user_id or os.environ.get("TACHIBANA_USER_ID", "")
        self.password: str = password or os.environ.get("TACHIBANA_PASSWORD", "")
        if not self.user_id:
            logger.warning("TACHIBANA_USER_ID is not set")
        if not self.password:
            logger.warning("TACHIBANA_PASSWORD is not set")

        self._session_token: str | None = None
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def login(self) -> bool:
        """
        Log in to the e-Support API and store the session token.

        Returns:
            True if login succeeded.

        Raises:
            RuntimeError: If login fails or token is missing.
        """
        url = f"{self.BASE_URL}/auth/"
        payload = {
            "sCLMID": "CLMAuthLoginRequest",
            "sUserId": self.user_id,
            "sPassword": self.password,
        }

        logger.debug("Logging in to Tachibana API at %s", url)
        try:
            resp = self._session.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            token = data.get("p_sd_date", "")
            if not token:
                raise RuntimeError(
                    f"Login response missing p_sd_date: {data}"
                )
            self._session_token = token
            logger.info("Tachibana login succeeded (session: %s...)", token[:8])
            return True
        except requests.RequestException as exc:
            logger.error("Tachibana login failed: %s", exc)
            raise RuntimeError(f"Tachibana login failed: {exc}") from exc

    def _ensure_session(self) -> None:
        """Ensure we have a valid session token, logging in if needed."""
        if self._session_token is None:
            self.login()

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
    ) -> dict:
        """
        Place an order.

        Args:
            symbol: Security code (e.g. "7203").
            side: "buy" or "sell".
            qty: Number of shares.
            order_type: "market" or "limit".
            price: Required for limit orders.

        Returns:
            Order response dict with order_id and status.

        Raises:
            ValueError: If side/order_type is invalid or limit has no price.
        """
        self._ensure_session()

        if side not in _SIDE_MAP:
            raise ValueError(f"Invalid side '{side}'. Must be 'buy' or 'sell'.")
        if order_type not in _ORDER_TYPE_MAP:
            raise ValueError(
                f"Invalid order_type '{order_type}'. Must be 'market' or 'limit'."
            )
        if order_type == "limit" and price is None:
            raise ValueError("price is required for limit orders")

        # Determine the price field value
        order_price = "*" if order_type == "market" else str(price)

        url = f"{self.BASE_URL}/request/"
        payload = {
            "sCLMID": "CLMOrderRequest",
            "p_sd_date": self._session_token,
            "sIssueCode": symbol,
            "sSizyouC": "00",         # 市場コード: 00=自動
            "sBaibaiKubun": _SIDE_MAP[side],
            "sGenkinSinyouKubun": "0",  # 0=現物
            "sOrderSuryou": str(qty),
            "sOrderCondition": "0",     # 通常注文
            "sOrderPrice": order_price,
        }

        logger.info(
            "Placing %s %s order: %s x%d @ %s",
            side, order_type, symbol, qty, price or "MARKET",
        )
        try:
            resp = self._session.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            order_id = data.get("sOrderNumber", "")
            status = data.get("sResultCode", "")
            logger.info("Order placed: %s (status=%s)", order_id, status)
            return {
                "order_id": order_id,
                "status": status,
                "raw": data,
            }
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
        self._ensure_session()

        url = f"{self.BASE_URL}/request/"
        payload = {
            "sCLMID": "CLMOrderCancelRequest",
            "p_sd_date": self._session_token,
            "sOrderNumber": order_id,
        }

        logger.info("Cancelling order: %s", order_id)
        try:
            resp = self._session.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            logger.info("Order cancelled: %s", data)
            return {
                "order_id": order_id,
                "status": data.get("sResultCode", ""),
                "raw": data,
            }
        except requests.RequestException as exc:
            logger.error("cancel_order failed for %s: %s", order_id, exc)
            return {"error": str(exc), "order_id": order_id}

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_orders(self) -> list[dict]:
        """
        Get active/open orders.

        Returns:
            List of order dicts.
        """
        self._ensure_session()

        url = f"{self.BASE_URL}/request/"
        payload = {
            "sCLMID": "CLMOrderListRequest",
            "p_sd_date": self._session_token,
            "sOrderStatusFilter": "0",  # 0=有効注文のみ
        }

        logger.debug("Querying open orders")
        try:
            resp = self._session.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            orders = data.get("aOrderList", [])
            logger.debug("Orders: %d items", len(orders))
            return orders if isinstance(orders, list) else []
        except requests.RequestException as exc:
            logger.error("get_orders failed: %s", exc)
            return []

    def get_positions(self) -> list[dict]:
        """
        Get current open positions.

        Returns:
            List of position dicts.
        """
        self._ensure_session()

        url = f"{self.BASE_URL}/request/"
        payload = {
            "sCLMID": "CLMPositionListRequest",
            "p_sd_date": self._session_token,
        }

        logger.debug("Querying positions")
        try:
            resp = self._session.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            positions = data.get("aPositionList", [])
            logger.debug("Positions: %d items", len(positions))
            return positions if isinstance(positions, list) else []
        except requests.RequestException as exc:
            logger.error("get_positions failed: %s", exc)
            return []
