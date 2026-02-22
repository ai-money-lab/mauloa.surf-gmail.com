"""Tests for System B modules — OrderProcessor, OrderIntake, products config.

Covers:
- products.yaml configuration validation
- OrderProcessor: product loading, _get_product, invalid product
- OrderIntake: webhook handling, order ID generation, email parsing
- EA/FX content filtering
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml


# ===========================================================================
# Products configuration tests
# ===========================================================================

class TestProductsConfig:
    """Test products.yaml configuration."""

    @pytest.fixture
    def products(self):
        products_path = Path(__file__).parent.parent / "system_b" / "products.yaml"
        with open(products_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_products_exist(self, products):
        assert "products" in products
        assert len(products["products"]) > 0

    def test_all_products_have_required_fields(self, products):
        required = ["id", "name", "price_range", "description", "quality_profile", "template"]
        for product in products["products"]:
            for field in required:
                assert field in product, (
                    f"Product {product.get('id', '?')} missing {field}"
                )

    def test_tier1_products_have_high_prices(self, products):
        tier1 = [p for p in products["products"] if p["id"].startswith("tier1")]
        assert len(tier1) > 0
        for p in tier1:
            assert p["price_range"][0] >= 300000

    def test_tier3_products_are_recurring(self, products):
        tier3 = [p for p in products["products"] if p["id"].startswith("tier3")]
        for p in tier3:
            if "recurring" in p:
                assert p["recurring"] is True

    def test_all_templates_are_md(self, products):
        for product in products["products"]:
            assert product["template"].endswith(".md"), (
                f"Template {product['template']} should be .md"
            )

    def test_quality_profiles_are_valid(self, products):
        valid_profiles = {"x_post", "report", "data_collection"}
        for product in products["products"]:
            assert product["quality_profile"] in valid_profiles

    def test_no_banned_ea_fx_content(self, products):
        """Product definitions must not reference EA/FX trading."""
        text = json.dumps(products, ensure_ascii=False).lower()
        tokens = text.split()
        # "ea" can appear in "realestate" but not standalone
        standalone_ea = [t for t in tokens if t.strip('",.:[]{}') == "ea"]
        assert len(standalone_ea) == 0
        assert "自動売買" not in text
        assert "xauusd" not in text

    def test_product_ids_are_unique(self, products):
        ids = [p["id"] for p in products["products"]]
        assert len(ids) == len(set(ids))

    def test_tier2_security_camera_exists(self, products):
        """Verify the security camera product is present."""
        ids = [p["id"] for p in products["products"]]
        assert "tier2_security_camera" in ids

    def test_tier2_special_cleaning_exists(self, products):
        ids = [p["id"] for p in products["products"]]
        assert "tier2_special_cleaning" in ids


# ===========================================================================
# OrderProcessor tests
# ===========================================================================

class TestOrderProcessor:
    """Test OrderProcessor."""

    @patch("system_b.process_order.SheetsClient")
    @patch("system_b.process_order.Notifier")
    @patch("system_b.process_order.PDFGenerator")
    @patch("system_b.process_order.QualityChecker")
    @patch("system_b.process_order.ClaudeClient")
    def test_get_product_valid_id(self, mock_claude, mock_qc, mock_pdf,
                                   mock_notif, mock_sheets):
        from system_b.process_order import OrderProcessor
        processor = OrderProcessor()
        product = processor._get_product("tier1_area_analysis")
        assert product["name"] == "不動産投資エリア分析レポート"

    @patch("system_b.process_order.SheetsClient")
    @patch("system_b.process_order.Notifier")
    @patch("system_b.process_order.PDFGenerator")
    @patch("system_b.process_order.QualityChecker")
    @patch("system_b.process_order.ClaudeClient")
    def test_get_product_invalid_id_raises(self, mock_claude, mock_qc, mock_pdf,
                                            mock_notif, mock_sheets):
        from system_b.process_order import OrderProcessor
        processor = OrderProcessor()
        with pytest.raises(ValueError, match="Unknown product"):
            processor._get_product("nonexistent")

    @patch("system_b.process_order.SheetsClient")
    @patch("system_b.process_order.Notifier")
    @patch("system_b.process_order.PDFGenerator")
    @patch("system_b.process_order.QualityChecker")
    @patch("system_b.process_order.ClaudeClient")
    def test_products_loaded_on_init(self, mock_claude, mock_qc, mock_pdf,
                                      mock_notif, mock_sheets):
        from system_b.process_order import OrderProcessor
        processor = OrderProcessor()
        assert len(processor.products) > 0
        assert "tier1_area_analysis" in processor.products

    @patch("system_b.process_order.SheetsClient")
    @patch("system_b.process_order.Notifier")
    @patch("system_b.process_order.PDFGenerator")
    @patch("system_b.process_order.QualityChecker")
    @patch("system_b.process_order.ClaudeClient")
    def test_get_product_returns_correct_fields(self, mock_claude, mock_qc, mock_pdf,
                                                  mock_notif, mock_sheets):
        from system_b.process_order import OrderProcessor
        processor = OrderProcessor()
        product = processor._get_product("tier2_rental_valuation")
        assert "name" in product
        assert "quality_profile" in product
        assert product["quality_profile"] == "report"


# ===========================================================================
# OrderIntake tests
# ===========================================================================

class TestOrderIntake:
    """Test OrderIntake webhook and email handling."""

    @patch("system_b.order_intake.OrderProcessor")
    @patch("system_b.order_intake.Notifier")
    def test_generate_order_id_format(self, mock_notifier, mock_processor):
        from system_b.order_intake import OrderIntake
        intake = OrderIntake()
        order_id = intake._generate_order_id()
        assert order_id.startswith("ORD-")
        parts = order_id.split("-")
        assert len(parts) == 3

    @patch("system_b.order_intake.OrderProcessor")
    @patch("system_b.order_intake.Notifier")
    def test_handle_webhook_builds_order_dict(self, mock_notifier, mock_processor):
        from system_b.order_intake import OrderIntake
        mock_processor_instance = MagicMock()
        mock_processor.return_value = mock_processor_instance
        mock_processor_instance.process.return_value = {"status": "delivered"}

        intake = OrderIntake()
        payload = {
            "order_id": "ORD-TEST-001",
            "product_id": "tier1_area_analysis",
            "client_name": "テスト太郎",
            "parameters": {"area": "渋谷区"},
            "deadline": "2026-03-01",
            "platform": "coconala",
        }
        intake.handle_webhook(payload)

        call_args = mock_processor_instance.process.call_args[0][0]
        assert call_args["order_id"] == "ORD-TEST-001"
        assert call_args["product_id"] == "tier1_area_analysis"
        assert call_args["client_name"] == "テスト太郎"
        assert call_args["platform"] == "coconala"

    @patch("system_b.order_intake.OrderProcessor")
    @patch("system_b.order_intake.Notifier")
    def test_handle_webhook_sends_notification(self, mock_notifier, mock_processor):
        from system_b.order_intake import OrderIntake
        mock_notifier_instance = MagicMock()
        mock_notifier.return_value = mock_notifier_instance
        mock_processor.return_value.process.return_value = {"status": "delivered"}

        intake = OrderIntake()
        intake.handle_webhook({"product_id": "tier1_area_analysis"})

        mock_notifier_instance.send_line.assert_called_once()

    @patch("system_b.order_intake.OrderProcessor")
    @patch("system_b.order_intake.Notifier")
    def test_handle_webhook_default_platform_is_direct(self, mock_notifier, mock_processor):
        from system_b.order_intake import OrderIntake
        mock_processor_instance = MagicMock()
        mock_processor.return_value = mock_processor_instance
        mock_processor_instance.process.return_value = {}

        intake = OrderIntake()
        intake.handle_webhook({"product_id": "test"})

        call_args = mock_processor_instance.process.call_args[0][0]
        assert call_args["platform"] == "direct"
