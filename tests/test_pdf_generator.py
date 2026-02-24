"""Tests for core/pdf_generator.py."""

from unittest.mock import patch, MagicMock

import pytest

from core.pdf_generator import PDFGenerator, CSS_TEMPLATE


class TestPDFGeneratorInit:
    """Test PDFGenerator initialization."""

    def test_default_template_dir(self):
        gen = PDFGenerator()
        assert gen.template_dir.name == "templates"
        assert gen.template_dir.exists()

    def test_custom_template_dir(self, tmp_path):
        gen = PDFGenerator(template_dir=str(tmp_path))
        assert gen.template_dir == tmp_path


class TestPDFGeneratorRenderTemplate:
    """Test template rendering with Jinja2."""

    def test_render_simple_template(self, tmp_path):
        template = tmp_path / "test.md"
        template.write_text("# {{ title }}\n{{ body }}", encoding="utf-8")

        gen = PDFGenerator(template_dir=str(tmp_path))
        result = gen.render_template("test.md", {"title": "テスト", "body": "内容"})

        assert "# テスト" in result
        assert "内容" in result

    def test_render_with_empty_variables(self, tmp_path):
        template = tmp_path / "test.md"
        template.write_text("Static text only", encoding="utf-8")

        gen = PDFGenerator(template_dir=str(tmp_path))
        result = gen.render_template("test.md", {})
        assert result == "Static text only"

    def test_render_real_template_exists(self):
        gen = PDFGenerator()
        # Should not raise — template files exist
        result = gen.render_template("rental_valuation_report.md", {
            "report_title": "テストレポート",
            "date": "2024-01-01",
            "client_name": "テスト太郎",
            "property_name": "テストマンション",
            "property_address": "東京都渋谷区",
            "property_type": "マンション",
            "area": "30",
            "age": "10",
            "floor": "5",
            "estimated_rent": "100000",
            "confidence_range_low": "90000",
            "confidence_range_high": "110000",
            "market_average": "95000",
            "comparison_properties": "近隣物件A, B, C",
            "ai_analysis": "分析コメント",
            "recommendations": "推奨事項",
        })
        assert len(result) > 0

    def test_render_missing_template_raises(self, tmp_path):
        gen = PDFGenerator(template_dir=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            gen.render_template("nonexistent.md", {})


class TestPDFGeneratorMarkdownToHtml:
    """Test Markdown to HTML conversion."""

    def test_basic_conversion(self):
        gen = PDFGenerator()
        html = gen.markdown_to_html("# Hello\n\nWorld")

        assert "<h1" in html  # toc extension adds id attr
        assert "Hello" in html
        assert "World" in html
        assert "<!DOCTYPE html>" in html

    def test_includes_css(self):
        gen = PDFGenerator()
        html = gen.markdown_to_html("text")
        assert CSS_TEMPLATE in html

    def test_table_extension(self):
        gen = PDFGenerator()
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        html = gen.markdown_to_html(md)
        assert "<table>" in html

    def test_fenced_code(self):
        gen = PDFGenerator()
        md = "```python\nprint('hello')\n```"
        html = gen.markdown_to_html(md)
        assert "print" in html


class TestPDFGeneratorGeneratePdf:
    """Test PDF generation (mock weasyprint)."""

    @patch("core.pdf_generator.HTML", create=True)
    def test_generate_pdf_success(self, mock_html_cls, tmp_path):
        # Create template
        template = tmp_path / "templates" / "test.md"
        template.parent.mkdir(parents=True, exist_ok=True)
        template.write_text("# {{ title }}", encoding="utf-8")

        output = tmp_path / "output" / "test.pdf"
        mock_html_instance = MagicMock()
        mock_html_cls.return_value = mock_html_instance

        # Patch weasyprint import inside generate_pdf
        with patch.dict("sys.modules", {"weasyprint": MagicMock(HTML=mock_html_cls)}):
            gen = PDFGenerator(template_dir=str(tmp_path / "templates"))
            result = gen.generate_pdf("test.md", {"title": "テスト"}, str(output))

        assert result == str(output)
        assert output.parent.exists()

    def test_generate_pdf_creates_output(self, tmp_path):
        """weasyprint installed — actual PDF generation."""
        template = tmp_path / "test.md"
        template.write_text("# {{ title }}", encoding="utf-8")

        output = tmp_path / "output" / "test.pdf"

        gen = PDFGenerator(template_dir=str(tmp_path))
        result = gen.generate_pdf("test.md", {"title": "テスト"}, str(output))

        assert result == str(output)
        assert output.exists()
        assert output.stat().st_size > 0
