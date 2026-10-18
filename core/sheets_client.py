"""Google Sheets client for managing post and order records.

Service-account credentials are read from one of two env vars:

``GOOGLE_SHEETS_CREDENTIALS_JSON``
    The service-account JSON itself. Use this on CI runners, where there is
    no credentials file on disk.
``GOOGLE_SHEETS_CREDENTIALS_PATH``
    Path to the JSON file (default ``./config/credentials.json``). Used when
    the inline variable is empty.
"""

import json
import os
import logging

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsClient:
    """Google Sheets interface for post management and order tracking."""

    def __init__(self):
        self.credentials_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON", "").strip()
        self.credentials_path = os.getenv(
            "GOOGLE_SHEETS_CREDENTIALS_PATH", "./config/credentials.json"
        )
        self.post_sheet_id = os.getenv("SHEETS_POST_MANAGEMENT_ID", "")
        self.order_sheet_id = os.getenv("SHEETS_ORDER_MANAGEMENT_ID", "")
        self._client = None

    def _build_credentials(self):
        """Build service-account credentials from inline JSON or a file."""
        from google.oauth2.service_account import Credentials

        if self.credentials_json:
            info = json.loads(self.credentials_json)
            return Credentials.from_service_account_info(info, scopes=SCOPES)
        return Credentials.from_service_account_file(
            self.credentials_path, scopes=SCOPES
        )

    def _get_client(self):
        """Lazy-init gspread client."""
        if self._client is None:
            try:
                import gspread

                self._client = gspread.authorize(self._build_credentials())
            except Exception as e:
                logger.error("Failed to initialize Sheets client: %s", e)
                raise
        return self._client

    def record_post(self, post_data: dict) -> None:
        """Record a post to the post management sheet.

        Args:
            post_data: Dict with keys like datetime, pillar, pipeline,
                       pattern, text, quality_score, status.
        """
        try:
            client = self._get_client()
            sheet = client.open_by_key(self.post_sheet_id).sheet1
            row = [
                post_data.get("datetime", ""),
                post_data.get("pillar", ""),
                post_data.get("pipeline", ""),
                post_data.get("pattern", ""),
                post_data.get("text", ""),
                str(post_data.get("quality_score", "")),
                post_data.get("status", ""),
            ]
            sheet.append_row(row)
            logger.info("Post recorded to Sheets: %s", post_data.get("datetime"))
        except Exception as e:
            logger.error("Failed to record post: %s", e)
            raise

    def record_order(self, order_data: dict) -> None:
        """Record an order to the order management sheet."""
        try:
            client = self._get_client()
            sheet = client.open_by_key(self.order_sheet_id).sheet1
            row = [
                order_data.get("order_id", ""),
                order_data.get("product_id", ""),
                order_data.get("client_name", ""),
                order_data.get("deadline", ""),
                order_data.get("platform", ""),
                order_data.get("status", "received"),
                order_data.get("created_at", ""),
            ]
            sheet.append_row(row)
            logger.info("Order recorded: %s", order_data.get("order_id"))
        except Exception as e:
            logger.error("Failed to record order: %s", e)
            raise

    def update_order_status(self, order_id: str, status: str) -> None:
        """Update an order's status in the sheet."""
        try:
            client = self._get_client()
            sheet = client.open_by_key(self.order_sheet_id).sheet1
            cell = sheet.find(order_id)
            if cell:
                sheet.update_cell(cell.row, 6, status)
                logger.info("Order %s status updated to %s", order_id, status)
        except Exception as e:
            logger.error("Failed to update order status: %s", e)
            raise
