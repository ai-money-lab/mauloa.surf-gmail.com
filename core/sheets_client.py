"""Google Sheets クライアント"""

import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsClient:
    """Google Sheets 操作クライアント"""

    def __init__(self):
        creds_path = os.getenv(
            "GOOGLE_SHEETS_CREDENTIALS_PATH", "./config/credentials.json"
        )
        if not Path(creds_path).exists():
            logger.warning(f"Credentials not found: {creds_path}")
            self._client = None
            return

        credentials = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        self._client = gspread.authorize(credentials)

    @property
    def available(self) -> bool:
        return self._client is not None

    def _get_sheet(self, sheet_id: str, worksheet_name: str = None):
        if not self.available:
            raise RuntimeError("Google Sheets credentials not configured")
        spreadsheet = self._client.open_by_key(sheet_id)
        if worksheet_name:
            return spreadsheet.worksheet(worksheet_name)
        return spreadsheet.sheet1

    def append_post_record(self, post_data: dict) -> int | None:
        """投稿管理表にレコード追加

        列構成:
            A: 記録日時
            B: 柱 (pillar)
            C: パターン (pattern_key)
            D: テキスト (先頭500文字)
            E: 品質スコア
            F: ステータス (scheduled/posted/failed/edited)
            G: tweet_id (メインツイート)
            H: all_tweet_ids (スレッド全ID, カンマ区切り)
            I: scheduled_time (予定投稿時刻)
            J: posted_at (実際の投稿時刻)

        Returns:
            書き込んだ行番号（Sheets上のrow number）。失敗時はNone。
        """
        sheet_id = os.getenv("SHEETS_POST_MANAGEMENT_ID")
        if not sheet_id:
            logger.warning("SHEETS_POST_MANAGEMENT_ID not set")
            return None

        sheet = self._get_sheet(sheet_id)
        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")

        # tweet_ids: リストまたは文字列に対応
        tweet_ids = post_data.get("tweet_ids", [])
        main_tweet_id = post_data.get("tweet_id", "")
        if not main_tweet_id and tweet_ids:
            main_tweet_id = tweet_ids[0] if isinstance(tweet_ids, list) else tweet_ids
        all_tweet_ids_str = (
            ",".join(tweet_ids) if isinstance(tweet_ids, list) else str(tweet_ids)
        )

        row = [
            now,
            post_data.get("pillar", ""),
            post_data.get("pattern_key", post_data.get("pattern", "")),
            post_data.get("text", "")[:500],
            post_data.get("quality_score", 0),
            post_data.get("status", "scheduled"),
            main_tweet_id,
            all_tweet_ids_str,
            post_data.get("scheduled_time", ""),
            post_data.get("posted_at", ""),
        ]
        sheet.append_row(row)
        row_number = len(sheet.get_all_values())
        logger.info(f"Post record appended to sheet row {row_number}")
        return row_number

    def get_scheduled_post_text(self, row_number: int) -> dict | None:
        """指定行から投稿データを読み込む（編集済みテキストを取得）

        Returns:
            {"text": str, "status": str} or None
        """
        sheet_id = os.getenv("SHEETS_POST_MANAGEMENT_ID")
        if not sheet_id:
            return None

        try:
            sheet = self._get_sheet(sheet_id)
            row = sheet.row_values(row_number)
            if not row or len(row) < 6:
                return None
            return {
                "text": row[3],       # D列: テキスト
                "status": row[5],     # F列: ステータス
            }
        except Exception as e:
            logger.error(f"Failed to read row {row_number}: {e}")
            return None

    def update_post_status(self, row_number: int, status: str, tweet_id: str = "", posted_at: str = ""):
        """投稿管理表のステータスを更新"""
        sheet_id = os.getenv("SHEETS_POST_MANAGEMENT_ID")
        if not sheet_id:
            return

        try:
            sheet = self._get_sheet(sheet_id)
            sheet.update_cell(row_number, 6, status)        # F列
            if tweet_id:
                sheet.update_cell(row_number, 7, tweet_id)  # G列
            if posted_at:
                sheet.update_cell(row_number, 10, posted_at) # J列
            logger.info(f"Post row {row_number} status updated to: {status}")
        except Exception as e:
            logger.error(f"Failed to update row {row_number}: {e}")

    def append_order_record(self, order_data: dict):
        """案件管理表にレコード追加"""
        sheet_id = os.getenv("SHEETS_ORDER_MANAGEMENT_ID")
        if not sheet_id:
            logger.warning("SHEETS_ORDER_MANAGEMENT_ID not set")
            return

        sheet = self._get_sheet(sheet_id)
        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")

        row = [
            now,
            order_data.get("order_id", ""),
            order_data.get("product_id", ""),
            order_data.get("client_name", ""),
            order_data.get("platform", ""),
            order_data.get("price", 0),
            order_data.get("deadline", ""),
            order_data.get("status", "received"),
        ]
        sheet.append_row(row)
        logger.info(f"Order record appended: {order_data.get('order_id')}")

    def update_order_status(self, order_id: str, status: str):
        """案件ステータスを更新"""
        sheet_id = os.getenv("SHEETS_ORDER_MANAGEMENT_ID")
        if not sheet_id:
            logger.warning("SHEETS_ORDER_MANAGEMENT_ID not set")
            return

        sheet = self._get_sheet(sheet_id)
        cell = sheet.find(order_id)
        if cell:
            sheet.update_cell(cell.row, 8, status)
            logger.info(f"Order {order_id} status updated to: {status}")
        else:
            logger.warning(f"Order {order_id} not found in sheet")

    def get_post_performance(self, days: int = 7) -> list[dict]:
        """投稿パフォーマンスデータを取得"""
        sheet_id = os.getenv("SHEETS_POST_MANAGEMENT_ID")
        if not sheet_id:
            return []

        sheet = self._get_sheet(sheet_id)
        records = sheet.get_all_records()
        return records[-days * 3:] if records else []

    def get_completed_orders(self, limit: int = 10) -> list[dict]:
        """完了案件を取得"""
        sheet_id = os.getenv("SHEETS_ORDER_MANAGEMENT_ID")
        if not sheet_id:
            return []

        sheet = self._get_sheet(sheet_id)
        records = sheet.get_all_records()
        completed = [r for r in records if r.get("status") == "delivered"]
        return completed[-limit:]
