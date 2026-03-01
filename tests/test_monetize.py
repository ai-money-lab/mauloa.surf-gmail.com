"""Tests for monetize (マネタイズエンジン) modules."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml


class TestCatalog:
    """catalog.yaml の構造テスト."""

    @pytest.fixture
    def catalog(self):
        catalog_path = Path(__file__).parent.parent / "monetize" / "catalog.yaml"
        with open(catalog_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_instant_products_exist(self, catalog):
        assert "instant_products" in catalog
        assert len(catalog["instant_products"]) > 0

    def test_subscription_products_exist(self, catalog):
        assert "subscription_products" in catalog
        assert len(catalog["subscription_products"]) > 0

    def test_api_pricing_exists(self, catalog):
        assert "api_pricing" in catalog
        assert "image_generation" in catalog["api_pricing"]

    def test_all_instant_products_have_required_fields(self, catalog):
        required = ["id", "name", "description", "price_jpy", "generation", "auto_rate"]
        for product in catalog["instant_products"]:
            for field in required:
                assert field in product, f"Product {product.get('id', '?')} missing {field}"

    def test_all_subscription_products_have_required_fields(self, catalog):
        required = ["id", "name", "description", "price_jpy_monthly", "included"]
        for product in catalog["subscription_products"]:
            for field in required:
                assert field in product, f"Subscription {product.get('id', '?')} missing {field}"

    def test_all_prices_positive(self, catalog):
        for p in catalog["instant_products"]:
            assert p["price_jpy"] > 0, f"{p['id']} has non-positive price"
        for p in catalog["subscription_products"]:
            assert p["price_jpy_monthly"] > 0, f"{p['id']} has non-positive price"

    def test_estimated_cost_less_than_price(self, catalog):
        """原価が売価より低いことを確認（利益が出る設計）."""
        for p in catalog["instant_products"]:
            assert p["estimated_cost_jpy"] < p["price_jpy"], \
                f"{p['id']}: 原価{p['estimated_cost_jpy']} >= 売価{p['price_jpy']}"

    def test_no_banned_content(self, catalog):
        """禁止コンテンツが含まれていないことを確認."""
        text = json.dumps(catalog, ensure_ascii=False).lower()
        assert "自動売買" not in text
        assert "xauusd" not in text


class TestPricingEngine:
    """PricingEngine のテスト."""

    @patch("monetize.pricing_engine.COSTS_LOG_DIR")
    def test_get_product(self, mock_dir):
        mock_dir.mkdir = MagicMock()
        from monetize.pricing_engine import PricingEngine
        engine = PricingEngine()
        product = engine.get_product("img_single")
        assert product is not None
        assert product["name"] == "AI画像生成（1枚）"

    @patch("monetize.pricing_engine.COSTS_LOG_DIR")
    def test_get_nonexistent_product(self, mock_dir):
        mock_dir.mkdir = MagicMock()
        from monetize.pricing_engine import PricingEngine
        engine = PricingEngine()
        assert engine.get_product("nonexistent") is None

    @patch("monetize.pricing_engine.COSTS_LOG_DIR")
    def test_calculate_generation_cost(self, mock_dir):
        mock_dir.mkdir = MagicMock()
        from monetize.pricing_engine import PricingEngine
        engine = PricingEngine()
        cost = engine.calculate_generation_cost("img_single")
        assert cost["price_jpy"] == 500
        assert cost["margin_jpy"] > 0
        assert cost["margin_pct"] > 50  # 利益率50%以上

    @patch("monetize.pricing_engine.COSTS_LOG_DIR")
    def test_all_products_profitable(self, mock_dir):
        """全商品が利益を出せることを確認."""
        mock_dir.mkdir = MagicMock()
        from monetize.pricing_engine import PricingEngine
        engine = PricingEngine()
        for pid in engine.instant_products:
            cost = engine.calculate_generation_cost(pid)
            assert cost["margin_jpy"] > 0, f"{pid} is not profitable"

    @patch("monetize.pricing_engine.COSTS_LOG_DIR")
    def test_subscription_check(self, mock_dir):
        mock_dir.mkdir = MagicMock()
        from monetize.pricing_engine import PricingEngine
        engine = PricingEngine()
        result = engine.check_subscription_usage(
            "sub_starter",
            {"images": 10, "posts": 3},
        )
        assert result["within_limit"] is True
        assert result["images_remaining"] == 20

    @patch("monetize.pricing_engine.COSTS_LOG_DIR")
    def test_all_products_summary(self, mock_dir):
        mock_dir.mkdir = MagicMock()
        from monetize.pricing_engine import PricingEngine
        engine = PricingEngine()
        summary = engine.get_all_products_summary()
        assert len(summary) > 0
        types = {p["type"] for p in summary}
        assert "instant" in types
        assert "subscription" in types


class TestRevenueTracker:
    """RevenueTracker のテスト."""

    def test_daily_summary_empty(self, tmp_path):
        """データがない場合のサマリー."""
        with patch("monetize.revenue_tracker.ORDERS_DIR", tmp_path / "orders"), \
             patch("monetize.revenue_tracker.COSTS_DIR", tmp_path / "costs"), \
             patch("monetize.revenue_tracker.SUBSCRIPTIONS_DIR", tmp_path / "subs"):
            from monetize.revenue_tracker import RevenueTracker
            tracker = RevenueTracker()
            summary = tracker.get_daily_summary("20260301")
            assert summary["total_orders"] == 0
            assert summary["revenue_jpy"] == 0

    def test_pl_report_format(self, tmp_path):
        """P&Lレポートのフォーマット確認."""
        with patch("monetize.revenue_tracker.ORDERS_DIR", tmp_path / "orders"), \
             patch("monetize.revenue_tracker.COSTS_DIR", tmp_path / "costs"), \
             patch("monetize.revenue_tracker.SUBSCRIPTIONS_DIR", tmp_path / "subs"):
            from monetize.revenue_tracker import RevenueTracker
            tracker = RevenueTracker()
            report = tracker.get_pl_report("202603")
            assert "P&L" in report
            assert "売上" in report
            assert "利益" in report


class TestSalesChannel:
    """SalesChannel のテスト."""

    @patch("monetize.sales_channel.OrderHandler")
    @patch("monetize.sales_channel.PricingEngine")
    def test_detect_purchase_intent(self, mock_pricing, mock_handler):
        from monetize.sales_channel import SalesChannel
        channel = SalesChannel()
        assert channel.detect_purchase_intent("AI画像を作りたい") is True
        assert channel.detect_purchase_intent("天気はどうですか") is False

    @patch("monetize.sales_channel.OrderHandler")
    @patch("monetize.sales_channel.PricingEngine")
    def test_suggest_product_logo(self, mock_pricing, mock_handler):
        mock_pricing_instance = mock_pricing.return_value
        mock_pricing_instance.get_product.return_value = {
            "id": "brand_kit",
            "name": "AIブランドキット",
            "description": "テスト",
            "price_jpy": 19800,
        }
        from monetize.sales_channel import SalesChannel
        channel = SalesChannel()
        result = channel.suggest_product("ロゴを作りたい")
        assert result is not None
        assert result["product_id"] == "brand_kit"

    @patch("monetize.sales_channel.OrderHandler")
    @patch("monetize.sales_channel.PricingEngine")
    def test_get_product_menu(self, mock_pricing, mock_handler):
        mock_pricing_instance = mock_pricing.return_value
        mock_pricing_instance.get_all_products_summary.return_value = [
            {"id": "img_single", "name": "AI画像", "price_jpy": 500, "type": "instant"},
            {"id": "sub_starter", "name": "Starter", "price_jpy_monthly": 9800, "type": "subscription"},
        ]
        from monetize.sales_channel import SalesChannel
        channel = SalesChannel()
        menu = channel.get_product_menu()
        assert "Marketplace" in menu
        assert "¥500" in menu
