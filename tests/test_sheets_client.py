"""Tests for core/sheets_client.py."""

from unittest.mock import patch, MagicMock

import pytest

from core.sheets_client import SheetsClient


class TestSheetsClientInit:
    """Test SheetsClient initialization."""

    def test_default_init(self):
        client = SheetsClient()
        assert client._client is None
        assert client.credentials_path is not None

    def test_env_vars_loaded(self):
        with patch.dict("os.environ", {
            "GOOGLE_SHEETS_CREDENTIALS_PATH": "/custom/creds.json",
            "SHEETS_POST_MANAGEMENT_ID": "post123",
            "SHEETS_ORDER_MANAGEMENT_ID": "order456",
        }):
            client = SheetsClient()
            assert client.credentials_path == "/custom/creds.json"
            assert client.post_sheet_id == "post123"
            assert client.order_sheet_id == "order456"


class TestSheetsClientGetClient:
    """Test _get_client specific error handling."""

    def test_get_client_missing_credentials_raises_file_not_found(self):
        """存在しない認証ファイルでFileNotFoundError."""
        client = SheetsClient()
        client.credentials_path = "/nonexistent/credentials.json"
        with pytest.raises(FileNotFoundError):
            client._get_client()


class TestSheetsClientRecordPost:
    """Test post recording."""

    @patch.object(SheetsClient, "_get_client")
    def test_record_post_success(self, mock_get_client):
        mock_sheet = MagicMock()
        mock_client = MagicMock()
        mock_client.open_by_key.return_value.sheet1 = mock_sheet
        mock_get_client.return_value = mock_client

        client = SheetsClient()
        client.record_post({
            "datetime": "2024-01-01",
            "pillar": "1",
            "pipeline": "P1",
            "pattern": "A",
            "text": "テスト投稿",
            "quality_score": 90,
            "status": "posted",
        })

        mock_sheet.append_row.assert_called_once()
        row = mock_sheet.append_row.call_args[0][0]
        assert row[0] == "2024-01-01"
        assert row[4] == "テスト投稿"
        assert row[5] == "90"

    @patch.object(SheetsClient, "_get_client")
    def test_record_post_with_missing_fields(self, mock_get_client):
        mock_sheet = MagicMock()
        mock_client = MagicMock()
        mock_client.open_by_key.return_value.sheet1 = mock_sheet
        mock_get_client.return_value = mock_client

        client = SheetsClient()
        client.record_post({})  # empty dict — defaults used

        row = mock_sheet.append_row.call_args[0][0]
        assert row[0] == ""  # default for missing datetime

    @patch.object(SheetsClient, "_get_client")
    def test_record_post_api_error_raises(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.open_by_key.side_effect = RuntimeError("API error")
        mock_get_client.return_value = mock_client

        client = SheetsClient()
        with pytest.raises(RuntimeError):
            client.record_post({"text": "test"})


class TestSheetsClientRecordOrder:
    """Test order recording."""

    @patch.object(SheetsClient, "_get_client")
    def test_record_order_success(self, mock_get_client):
        mock_sheet = MagicMock()
        mock_client = MagicMock()
        mock_client.open_by_key.return_value.sheet1 = mock_sheet
        mock_get_client.return_value = mock_client

        client = SheetsClient()
        client.record_order({
            "order_id": "ORD001",
            "product_id": "P001",
            "client_name": "テスト太郎",
            "deadline": "2024-02-01",
            "platform": "coconala",
            "status": "received",
            "created_at": "2024-01-15",
        })

        mock_sheet.append_row.assert_called_once()
        row = mock_sheet.append_row.call_args[0][0]
        assert row[0] == "ORD001"
        assert row[2] == "テスト太郎"


class TestSheetsClientUpdateOrderStatus:
    """Test order status update."""

    @patch.object(SheetsClient, "_get_client")
    def test_update_order_status_found(self, mock_get_client):
        mock_sheet = MagicMock()
        mock_cell = MagicMock()
        mock_cell.row = 5
        mock_sheet.find.return_value = mock_cell
        mock_client = MagicMock()
        mock_client.open_by_key.return_value.sheet1 = mock_sheet
        mock_get_client.return_value = mock_client

        client = SheetsClient()
        client.update_order_status("ORD001", "completed")

        mock_sheet.update_cell.assert_called_once_with(5, 6, "completed")

    @patch.object(SheetsClient, "_get_client")
    def test_update_order_status_not_found(self, mock_get_client):
        mock_sheet = MagicMock()
        mock_sheet.find.return_value = None
        mock_client = MagicMock()
        mock_client.open_by_key.return_value.sheet1 = mock_sheet
        mock_get_client.return_value = mock_client

        client = SheetsClient()
        # Should not raise, just skip
        client.update_order_status("NONEXISTENT", "completed")
        mock_sheet.update_cell.assert_not_called()

    @patch.object(SheetsClient, "_get_client")
    def test_update_order_status_api_error_raises(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.open_by_key.side_effect = RuntimeError("API error")
        mock_get_client.return_value = mock_client

        client = SheetsClient()
        with pytest.raises(RuntimeError):
            client.update_order_status("ORD001", "completed")
