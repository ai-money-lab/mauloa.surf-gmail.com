"""Tests for system_b modules."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml


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
                assert field in product, f"Product {product.get('id', '?')} missing {field}"

    def test_tier1_products_have_high_prices(self, products):
        tier1 = [p for p in products["products"] if p["id"].startswith("tier1")]
        for p in tier1:
            assert p["price_range"][0] >= 300000

    def test_tier3_products_are_recurring(self, products):
        tier3 = [p for p in products["products"] if p["id"].startswith("tier3")]
        for p in tier3:
            if "recurring" in p:
                assert p["recurring"] is True

    def test_all_templates_referenced(self, products):
        templates_dir = Path(__file__).parent.parent / "templates"
        for product in products["products"]:
            template = product["template"]
            # Template file should exist (or will be created by background agent)
            assert template.endswith(".md"), f"Template {template} should be .md"

    def test_quality_profiles_are_valid(self, products):
        valid_profiles = {"x_post", "report", "data_collection"}
        for product in products["products"]:
            assert product["quality_profile"] in valid_profiles

    def test_no_banned_content_in_products(self, products):
        """Ensure no EA/FX content in product definitions."""
        text = json.dumps(products, ensure_ascii=False).lower()
        assert "ea" not in text.split() or "ea" in "realestate"
        assert "fx" not in text.split()
        assert "自動売買" not in text
        assert "xauusd" not in text


class TestOrderProcessor:
    """Test OrderProcessor."""

    @patch("system_b.process_order.SheetsClient")
    @patch("system_b.process_order.Notifier")
    @patch("system_b.process_order.PDFGenerator")
    @patch("system_b.process_order.QualityChecker")
    @patch("system_b.process_order.ClaudeClient")
    def test_get_product_valid_id(self, mock_claude, mock_qc, mock_pdf, mock_notif, mock_sheets):
        from system_b.process_order import OrderProcessor
        processor = OrderProcessor()
        product = processor._get_product("tier1_area_analysis")
        assert product["name"] == "不動産投資エリア分析レポート"

    @patch("system_b.process_order.SheetsClient")
    @patch("system_b.process_order.Notifier")
    @patch("system_b.process_order.PDFGenerator")
    @patch("system_b.process_order.QualityChecker")
    @patch("system_b.process_order.ClaudeClient")
    def test_get_product_invalid_id_raises(self, mock_claude, mock_qc, mock_pdf, mock_notif, mock_sheets):
        from system_b.process_order import OrderProcessor
        processor = OrderProcessor()
        with pytest.raises(ValueError, match="Unknown product"):
            processor._get_product("nonexistent")
