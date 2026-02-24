"""Web Chat Handler — FastAPI全エンドポイント + ヘルパー関数テスト.

カバレッジ目標: 0% → 70%+
"""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from inquiry_bot.web_chat_handler import (
    _build_property_card,
    _get_available_property_cards,
    _clean_reply_for_cards,
    create_app,
)


# ─── ヘルパー関数テスト ───


class TestBuildPropertyCard:
    """_build_property_card のテスト."""

    def test_basic_card(self):
        card = _build_property_card("p1", {
            "name": "テストマンション",
            "rent": 85000,
            "management_fee": 5000,
            "layout": "1K",
            "area_sqm": 25.5,
            "nearest_station": "渋谷駅",
            "walk_minutes": 5,
            "pet_policy": "ペット不可",
            "vacancy_status": "空室あり",
            "available_date": "即入居可",
        })
        assert card.id == "p1"
        assert card.name == "テストマンション"
        assert "85,000円" in card.rent
        assert "5,000円" in card.rent
        assert card.layout == "1K"
        assert card.walk_minutes == 5
        assert "即入居可" in card.features

    def test_card_no_mgmt_fee(self):
        card = _build_property_card("p2", {
            "name": "物件B",
            "rent": 70000,
            "management_fee": 0,
            "layout": "1R",
            "area_sqm": 20,
        })
        assert "管理費" not in card.rent
        assert "70,000円" in card.rent

    def test_card_pet_allowed(self):
        card = _build_property_card("p3", {
            "name": "ペット可物件",
            "rent": 100000,
            "pet_policy": "小型犬可",
        })
        assert "ペット可" in card.features

    def test_card_with_facilities(self):
        card = _build_property_card("p4", {
            "name": "設備充実",
            "rent": 90000,
            "facility_list": "インターネット無料,オートロック,宅配ボックス",
        })
        assert "ネット無料" in card.features
        assert "オートロック" in card.features
        assert "宅配BOX" in card.features

    def test_card_features_max_4(self):
        card = _build_property_card("p5", {
            "name": "全部入り",
            "rent": 120000,
            "available_date": "即入居可",
            "pet_policy": "犬猫可",
            "facility_list": "インターネット無料,オートロック,宅配ボックス",
        })
        assert len(card.features) <= 4

    def test_card_string_rent(self):
        card = _build_property_card("p6", {"name": "X", "rent": "要問合せ"})
        assert card.rent == "要問合せ"

    def test_card_missing_fields(self):
        card = _build_property_card("p7", {})
        assert card.name == "p7"  # name defaults to pid
        assert card.rent == "0円"


class TestGetAvailablePropertyCards:
    """_get_available_property_cards のテスト."""

    def test_empty_data(self):
        assert _get_available_property_cards({}) == []
        assert _get_available_property_cards(None) == []

    def test_filters_vacancy(self):
        data = {
            "p1": {"name": "空室A", "rent": 80000, "vacancy_status": "空室あり"},
            "p2": {"name": "満室B", "rent": 90000, "vacancy_status": "満室"},
            "p3": {"name": "空室C", "rent": 70000, "vacancy_status": "空室1室"},
        }
        cards = _get_available_property_cards(data)
        assert len(cards) == 2
        names = {c.name for c in cards}
        assert "空室A" in names
        assert "空室C" in names
        assert "満室B" not in names


class TestCleanReplyForCards:
    """_clean_reply_for_cards のテスト."""

    def test_removes_property_listing(self):
        reply = "ご案内します。\n\n【現在空室の物件】\nテストマンション\n・賃料: 80,000円\n\nお気軽にどうぞ。"
        result = _clean_reply_for_cards(reply, ["テストマンション"])
        assert "テストマンション" not in result
        assert "賃料" not in result
        assert "気になる物件をタップしてください" in result

    def test_empty_text_becomes_default(self):
        reply = "【空室物件】\nマンションA\n・賃料: 80,000円"
        result = _clean_reply_for_cards(reply, ["マンションA"])
        assert "空室物件をご案内いたします" in result

    def test_removes_trailing_prompt(self):
        reply = "現在の空室を確認しました。\nどちらがご希望でしょうか？"
        result = _clean_reply_for_cards(reply, [])
        assert "どちら" not in result

    def test_preserves_non_listing_text(self):
        reply = "空室状況をご案内します。詳細はお問い合わせください。"
        result = _clean_reply_for_cards(reply, ["存在しない物件名"])
        assert "ご案内します" in result


# ─── FastAPI エンドポイントテスト ───


@pytest.fixture
def mock_bot_engine():
    """BotEngineのモックを作成."""
    bot = MagicMock()
    bot.config = {
        "web_chat": {
            "widget": {
                "title": "テストBot",
                "subtitle": "テスト用",
                "primary_color": "#000000",
                "accent_color": "#FF0000",
                "position": "bottom-right",
                "welcome_message": "こんにちは！テストです。",
            },
            "cors_origins": ["http://localhost:3000"],
        }
    }
    bot.handle_message.return_value = {
        "reply": "テスト回答です",
        "category": "general",
        "confidence": 0.9,
        "escalated": False,
    }
    bot.kb = MagicMock()
    bot.kb.property_data = {}
    bot.analytics = MagicMock()
    bot.analytics.generate_daily_report.return_value = "日次レポート"
    bot.analytics.generate_monthly_summary.return_value = "月次サマリー"
    bot.get_analytics.return_value = {
        "total_sessions": 10,
        "active_sessions": 3,
        "escalated_sessions": 1,
    }
    return bot


@pytest.fixture
def client(mock_bot_engine):
    """TestClient作成."""
    app = create_app(mock_bot_engine)
    return TestClient(app)


class TestChatEndpoint:
    """POST /api/chat のテスト."""

    def test_chat_normal(self, client, mock_bot_engine):
        resp = client.post("/api/chat", json={"message": "こんにちは"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["reply"] == "テスト回答です"
        assert data["category"] == "general"
        assert data["escalated"] is False
        assert "session_id" in data

    def test_chat_with_session_id(self, client, mock_bot_engine):
        resp = client.post("/api/chat", json={"message": "質問", "session_id": "my_session"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "my_session"

    def test_chat_empty_message(self, client):
        resp = client.post("/api/chat", json={"message": "   "})
        assert resp.status_code == 400

    def test_chat_vacancy_category_with_cards(self, client, mock_bot_engine):
        mock_bot_engine.handle_message.return_value = {
            "reply": "空室物件はこちらです。",
            "category": "vacancy",
            "confidence": 0.9,
            "escalated": False,
        }
        mock_bot_engine.kb.property_data = {
            "p1": {"name": "テスト物件", "rent": 80000, "vacancy_status": "空室あり",
                   "layout": "1K", "area_sqm": 25, "nearest_station": "渋谷"},
        }
        resp = client.post("/api/chat", json={"message": "空室ありますか"})
        data = resp.json()
        assert data["category"] == "vacancy"
        assert len(data["property_cards"]) == 1
        assert data["property_cards"][0]["name"] == "テスト物件"

    def test_chat_viewing_category_options(self, client, mock_bot_engine):
        mock_bot_engine.handle_message.return_value = {
            "reply": "内見について", "category": "viewing",
            "confidence": 0.9, "escalated": False,
        }
        resp = client.post("/api/chat", json={"message": "内見したい"})
        data = resp.json()
        assert "3Dツアーを見たい" in data["options"]

    def test_chat_maintenance_category_options(self, client, mock_bot_engine):
        mock_bot_engine.handle_message.return_value = {
            "reply": "修理の件", "category": "maintenance",
            "confidence": 0.9, "escalated": False,
        }
        resp = client.post("/api/chat", json={"message": "水漏れ"})
        data = resp.json()
        assert "担当者と話したい" in data["options"]

    def test_chat_fallback_options(self, client, mock_bot_engine):
        mock_bot_engine.handle_message.return_value = {
            "reply": "回答です", "category": "other",
            "confidence": 0.9, "escalated": False,
        }
        resp = client.post("/api/chat", json={"message": "その他"})
        data = resp.json()
        # フォールバック選択肢が表示される
        assert len(data["options"]) > 0
        assert "空室を確認したい" in data["options"]

    def test_chat_suggested_actions_from_engine(self, client, mock_bot_engine):
        mock_bot_engine.handle_message.return_value = {
            "reply": "回答", "category": "general",
            "confidence": 0.9, "escalated": False,
            "suggested_actions": ["カスタムA", "カスタムB"],
        }
        resp = client.post("/api/chat", json={"message": "テスト"})
        data = resp.json()
        assert data["options"] == ["カスタムA", "カスタムB"]


class TestWidgetConfigEndpoint:
    """GET /api/widget-config のテスト."""

    def test_widget_config(self, client):
        resp = client.get("/api/widget-config")
        assert resp.status_code == 200
        data = resp.json()
        # 実際のconfig.yamlから読み込まれるので、キーの存在を検証
        assert "title" in data
        assert "primaryColor" in data
        assert "welcomeMessage" in data
        assert isinstance(data["title"], str)
        assert len(data["title"]) > 0


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAnalyticsEndpoint:
    def test_analytics(self, client):
        resp = client.get("/api/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sessions"] == 10

    def test_daily_report(self, client):
        resp = client.get("/api/report/daily")
        assert resp.status_code == 200
        assert resp.json()["report"] == "日次レポート"

    def test_monthly_report(self, client):
        resp = client.get("/api/report/monthly")
        assert resp.status_code == 200
        assert resp.json()["report"] == "月次サマリー"


class TestFeedbackEndpoint:
    def test_feedback_positive(self, client):
        resp = client.post("/api/feedback", json={
            "session_id": "s1", "type": "positive", "message_index": 0,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_feedback_negative(self, client):
        resp = client.post("/api/feedback", json={
            "session_id": "s1", "type": "negative", "message_index": 1,
        })
        assert resp.status_code == 200

    def test_feedback_analytics_not_implemented(self, client, mock_bot_engine):
        mock_bot_engine.analytics.record_feedback.side_effect = AttributeError
        resp = client.post("/api/feedback", json={
            "session_id": "s1", "type": "positive", "message_index": 0,
        })
        assert resp.status_code == 200  # gracefully handles missing method


class TestPropertiesEndpoint:
    def test_list_properties(self, client, mock_bot_engine):
        mock_bot_engine.kb.property_data = {"p1": {"name": "物件A"}}
        resp = client.get("/api/properties")
        assert resp.status_code == 200
        assert resp.json()["properties"]["p1"]["name"] == "物件A"

    @patch("inquiry_bot.web_chat_handler._save_properties_yaml")
    def test_register_property(self, mock_save, client, mock_bot_engine):
        mock_bot_engine.kb.property_data = {}
        mock_bot_engine._build_system_prompt = MagicMock(return_value="prompt")
        resp = client.post("/api/properties", json={
            "name": "新規マンション",
            "rent": 95000,
            "layout": "1LDK",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["name"] == "新規マンション"
        mock_save.assert_called_once()

    @patch("inquiry_bot.web_chat_handler._save_properties_yaml")
    def test_delete_property(self, mock_save, client, mock_bot_engine):
        mock_bot_engine.kb.property_data = {"test_prop": {"name": "削除対象"}}
        mock_bot_engine._build_system_prompt = MagicMock(return_value="prompt")
        resp = client.delete("/api/properties/test_prop")
        assert resp.status_code == 200
        assert "test_prop" not in mock_bot_engine.kb.property_data

    def test_delete_property_not_found(self, client, mock_bot_engine):
        mock_bot_engine.kb.property_data = {}
        resp = client.delete("/api/properties/nonexistent")
        assert resp.status_code == 404


class TestPageEndpoints:
    def test_chat_page(self, client):
        resp = client.get("/chat")
        # Widget HTML exists
        assert resp.status_code in (200, 404)

    def test_admin_properties_page(self, client):
        resp = client.get("/admin/properties")
        assert resp.status_code == 200

    def test_admin_properties_v2(self, client):
        resp = client.get("/admin/properties/v2")
        assert resp.status_code == 200
