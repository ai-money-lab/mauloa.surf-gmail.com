"""Tests for core/sheets_client.py — SheetsClient class.

Covers:
- Lazy client initialization
- record_post(): row format, append_row call
- record_order(): row format
- update_order_status(): find + update_cell
- Error handling
"""

from unittest.mock import patch, MagicMock

import pytest

from core.sheets_client import SheetsClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_gspread():
    """Patch gspread and google.oauth2 to avoid real credentials."""
    with patch.dict("os.environ", {
        "GOOGLE_SHEETS_CREDENTIALS_PATH": "/fake/creds.json",
        "SHEETS_POST_MANAGEMENT_ID": "post-sheet-id",
        "SHEETS_ORDER_MANAGEMENT_ID": "order-sheet-id",
    }):
        with patch("core.sheets_client.SheetsClient._get_client") as mock_get:
            mock_client = MagicMock()
            mock_get.return_value = mock_client
            client = SheetsClient()
            client._client = mock_client
            yield client, mock_client


# ---------------------------------------------------------------------------
# Initialization tests
# ---------------------------------------------------------------------------

class TestSheetsClientInit:
    """Test client initialization and configuration."""

    def test_credentials_path_from_env(self):
        with patch.dict("os.environ", {
            "GOOGLE_SHEETS_CREDENTIALS_PATH": "/custom/path.json",
        }):
            client = SheetsClient()
            assert client.credentials_path == "/custom/path.json"

    def test_default_credentials_path(self):
        with patch.dict("os.environ", {}, clear=False):
            # Remove the env var if present
            import os
            old = os.environ.pop("GOOGLE_SHEETS_CREDENTIALS_PATH", None)
            try:
                client = SheetsClient()
                assert client.credentials_path == "./config/credentials.json"
            finally:
                if old is not None:
                    os.environ["GOOGLE_SHEETS_CREDENTIALS_PATH"] = old

    def test_lazy_client_is_none_initially(self):
        client = SheetsClient()
        assert client._client is None

    def test_sheet_ids_from_env(self):
        with patch.dict("os.environ", {
            "SHEETS_POST_MANAGEMENT_ID": "abc123",
            "SHEETS_ORDER_MANAGEMENT_ID": "def456",
        }):
            client = SheetsClient()
            assert client.post_sheet_id == "abc123"
            assert client.order_sheet_id == "def456"


# ---------------------------------------------------------------------------
# record_post() tests
# ---------------------------------------------------------------------------

class TestRecordPost:
    """Tests for SheetsClient.record_post()."""

    def test_appends_correct_row(self, mock_gspread):
        client, mock_gc = mock_gspread
        mock_sheet = MagicMock()
        mock_gc.open_by_key.return_value.sheet1 = mock_sheet

        post_data = {
            "datetime": "2026-02-22T10:00:00",
            "pillar": "1",
            "pipeline": "P1",
            "pattern": "A",
            "text": "テスト投稿",
            "quality_score": 90,
            "status": "posted",
        }
        client.record_post(post_data)

        mock_sheet.append_row.assert_called_once()
        row = mock_sheet.append_row.call_args[0][0]
        assert row[0] == "2026-02-22T10:00:00"
        assert row[1] == "1"
        assert row[2] == "P1"
        assert row[3] == "A"
        assert row[4] == "テスト投稿"
        assert row[5] == "90"
        assert row[6] == "posted"

    def test_handles_missing_fields_gracefully(self, mock_gspread):
        client, mock_gc = mock_gspread
        mock_sheet = MagicMock()
        mock_gc.open_by_key.return_value.sheet1 = mock_sheet

        client.record_post({})  # empty dict
        mock_sheet.append_row.assert_called_once()
        row = mock_sheet.append_row.call_args[0][0]
        # All fields default to empty string
        assert all(v == "" for v in row)

    def test_raises_on_sheets_error(self, mock_gspread):
        client, mock_gc = mock_gspread
        mock_gc.open_by_key.side_effect = Exception("Sheets API error")

        with pytest.raises(Exception, match="Sheets API error"):
            client.record_post({"text": "test"})


# ---------------------------------------------------------------------------
# record_order() tests
# ---------------------------------------------------------------------------

class TestRecordOrder:
    """Tests for SheetsClient.record_order()."""

    def test_appends_correct_order_row(self, mock_gspread):
        client, mock_gc = mock_gspread
        mock_sheet = MagicMock()
        mock_gc.open_by_key.return_value.sheet1 = mock_sheet

        order_data = {
            "order_id": "ORD-001",
            "product_id": "tier1_area_analysis",
            "client_name": "田中",
            "deadline": "2026-02-28",
            "platform": "lancers",
            "status": "received",
            "created_at": "2026-02-22T10:00:00",
        }
        client.record_order(order_data)

        mock_sheet.append_row.assert_called_once()
        row = mock_sheet.append_row.call_args[0][0]
        assert row[0] == "ORD-001"
        assert row[1] == "tier1_area_analysis"
        assert row[2] == "田中"
        assert row[5] == "received"

    def test_default_status_is_received(self, mock_gspread):
        client, mock_gc = mock_gspread
        mock_sheet = MagicMock()
        mock_gc.open_by_key.return_value.sheet1 = mock_sheet

        client.record_order({"order_id": "ORD-002"})
        row = mock_sheet.append_row.call_args[0][0]
        assert row[5] == "received"  # default status


# ---------------------------------------------------------------------------
# update_order_status() tests
# ---------------------------------------------------------------------------

class TestUpdateOrderStatus:
    """Tests for SheetsClient.update_order_status()."""

    def test_finds_order_and_updates_cell(self, mock_gspread):
        client, mock_gc = mock_gspread
        mock_sheet = MagicMock()
        mock_gc.open_by_key.return_value.sheet1 = mock_sheet

        mock_cell = MagicMock()
        mock_cell.row = 5
        mock_sheet.find.return_value = mock_cell

        client.update_order_status("ORD-001", "delivered")

        mock_sheet.find.assert_called_once_with("ORD-001")
        mock_sheet.update_cell.assert_called_once_with(5, 6, "delivered")

    def test_does_not_update_when_order_not_found(self, mock_gspread):
        client, mock_gc = mock_gspread
        mock_sheet = MagicMock()
        mock_gc.open_by_key.return_value.sheet1 = mock_sheet
        mock_sheet.find.return_value = None

        client.update_order_status("NONEXISTENT", "delivered")
        mock_sheet.update_cell.assert_not_called()

    def test_raises_on_sheets_error(self, mock_gspread):
        client, mock_gc = mock_gspread
        mock_gc.open_by_key.side_effect = Exception("Sheets error")

        with pytest.raises(Exception, match="Sheets error"):
            client.update_order_status("ORD-001", "delivered")
