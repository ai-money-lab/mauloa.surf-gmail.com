"""
Tachibana Securities API Client (Placeholder)
立花証券 e-Support API

Stage 2 implementation — all methods currently raise NotImplementedError.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class TachibanaAPI:
    """Placeholder client for the 立花証券 e-Support API (Stage 2)."""

    def __init__(self) -> None:
        """
        Initialise the Tachibana API client.

        Reads TACHIBANA_API_KEY from environment.
        """
        self.api_key: str = os.environ.get("TACHIBANA_API_KEY", "")
        if not self.api_key:
            logger.warning("TACHIBANA_API_KEY is not set")

    def login(self) -> bool:
        """
        Log in to the e-Support API.

        Raises:
            NotImplementedError: Stage 2 not yet implemented.
        """
        raise NotImplementedError("Stage 2: 立花証券API未実装")

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

        Raises:
            NotImplementedError: Stage 2 not yet implemented.
        """
        raise NotImplementedError("Stage 2: 立花証券API未実装")

    def get_positions(self) -> list[dict]:
        """
        Get current open positions.

        Raises:
            NotImplementedError: Stage 2 not yet implemented.
        """
        raise NotImplementedError("Stage 2: 立花証券API未実装")

    def get_orders(self) -> list[dict]:
        """
        Get active orders.

        Raises:
            NotImplementedError: Stage 2 not yet implemented.
        """
        raise NotImplementedError("Stage 2: 立花証券API未実装")
