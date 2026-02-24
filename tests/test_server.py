"""Server統合テスト — LINE Webhook + Web Chat統合サーバー.

カバレッジ目標: 0% → 80%+
"""

import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from inquiry_bot.server import create_server


@pytest.fixture
def server_client():
    """統合サーバーのTestClient."""
    with patch("inquiry_bot.bot_engine.ClaudeClient") as mock_claude, \
         patch("inquiry_bot.bot_engine.Notifier") as mock_notifier, \
         patch("inquiry_bot.bot_engine.InquiryAnalytics") as mock_analytics:
        mock_claude.return_value = MagicMock()
        mock_claude.return_value.generate.return_value = json.dumps({
            "reply": "統合テスト回答",
            "category": "general",
            "confidence": 0.9,
            "escalate": False,
        })
        mock_notifier.return_value = MagicMock()
        mock_analytics.return_value = MagicMock()
        mock_analytics.return_value.generate_daily_report.return_value = "レポート"
        mock_analytics.return_value.generate_monthly_summary.return_value = "サマリー"

        app = create_server()
        yield TestClient(app)


class TestRootEndpoint:
    def test_root(self, server_client):
        resp = server_client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "ROCKEDGE 問い合わせ自動対応Bot"
        assert "chat_api" in data["endpoints"]
        assert "line_webhook" in data["endpoints"]


class TestLineWebhookEndpoint:
    def test_line_webhook_empty_events(self, server_client):
        body = json.dumps({"events": []})
        resp = server_client.post(
            "/webhook/line",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200

    def test_line_webhook_invalid_json(self, server_client):
        resp = server_client.post(
            "/webhook/line",
            content="not json",
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code == 400


class TestWebChatViaServer:
    """統合サーバー経由でWeb Chatが機能すること."""

    def test_chat_via_server(self, server_client):
        resp = server_client.post("/api/chat", json={"message": "テスト"})
        assert resp.status_code == 200
        assert resp.json()["reply"] == "統合テスト回答"

    def test_health_via_server(self, server_client):
        resp = server_client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_widget_config_via_server(self, server_client):
        resp = server_client.get("/api/widget-config")
        assert resp.status_code == 200
        assert "title" in resp.json()


class TestServerConfigValidation:
    """設定ファイルバリデーションのテスト."""

    @patch("inquiry_bot.server.CONFIG_PATH")
    def test_missing_config_raises(self, mock_path):
        mock_path.read_text.side_effect = FileNotFoundError("config.yaml not found")
        with pytest.raises(FileNotFoundError):
            create_server()

    @patch("inquiry_bot.server.CONFIG_PATH")
    def test_empty_config_raises(self, mock_path):
        mock_path.read_text.return_value = ""
        with pytest.raises(ValueError):
            create_server()
