"""問い合わせBot — 自動テスト."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


# ═══ YAML設定ファイルのバリデーション ═══

class TestConfigValidation:
    """設定ファイルの構造テスト."""

    def test_config_yaml_loads(self):
        """config.yaml が正しくロードできる."""
        path = Path(__file__).parent.parent / "inquiry_bot" / "config.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "bot" in data
        assert "line" in data
        assert "web_chat" in data
        assert "escalation" in data
        assert "categories" in data

    def test_faq_data_yaml_loads(self):
        """faq_data.yaml が正しくロードできる."""
        path = Path(__file__).parent.parent / "inquiry_bot" / "faq_data.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "faq" in data
        assert "company" in data
        # 各FAQ項目に必須フィールドがある
        for faq_item in data["faq"]:
            assert "id" in faq_item
            assert "category" in faq_item
            assert "patterns" in faq_item
            assert "answer" in faq_item

    def test_properties_yaml_loads(self):
        """properties.yaml が正しくロードできる."""
        path = Path(__file__).parent.parent / "inquiry_bot" / "properties.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "properties" in data
        assert "company" in data
        # 各物件に必須フィールドがある
        for pid, prop in data["properties"].items():
            assert "name" in prop
            assert "rent" in prop
            assert "layout" in prop

    def test_config_categories_have_required_fields(self):
        """カテゴリ設定に必須フィールドがある."""
        path = Path(__file__).parent.parent / "inquiry_bot" / "config.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for cat in data["categories"]:
            assert "id" in cat
            assert "name" in cat
            assert "priority" in cat
            assert cat["priority"] in ("high", "medium", "low")

    def test_escalation_triggers_defined(self):
        """エスカレーショントリガーが定義されている."""
        path = Path(__file__).parent.parent / "inquiry_bot" / "config.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        triggers = data["escalation"]["triggers"]
        assert len(triggers) > 0
        # キーワードトリガーが1つ以上
        keyword_triggers = [t for t in triggers if "keyword" in t]
        assert len(keyword_triggers) > 0


# ═══ システムプロンプトのテスト ═══

class TestSystemPrompt:
    """システムプロンプトの検証."""

    def test_system_prompt_exists(self):
        """inquiry_bot_system.txt が存在する."""
        path = Path(__file__).parent.parent / "prompts" / "inquiry_bot_system.txt"
        assert path.exists(), "System prompt file missing"

    def test_system_prompt_not_empty(self):
        """システムプロンプトが空でない."""
        path = Path(__file__).parent.parent / "prompts" / "inquiry_bot_system.txt"
        content = path.read_text(encoding="utf-8")
        assert len(content) > 100, "System prompt too short"

    def test_system_prompt_has_key_sections(self):
        """システムプロンプトに重要セクションが含まれている."""
        path = Path(__file__).parent.parent / "prompts" / "inquiry_bot_system.txt"
        content = path.read_text(encoding="utf-8")
        # 主要なキーワードが含まれていること
        assert "物件" in content or "不動産" in content


# ═══ Analyticsモジュールのテスト ═══

class TestAnalytics:
    """分析モジュールのテスト."""

    def test_analytics_import(self):
        """InquiryAnalytics がインポートできる."""
        from inquiry_bot.analytics import InquiryAnalytics
        analytics = InquiryAnalytics()
        assert analytics is not None

    def test_generate_daily_report_no_data(self):
        """データなしで日次レポートが生成できる."""
        from inquiry_bot.analytics import InquiryAnalytics
        analytics = InquiryAnalytics()
        report = analytics.generate_daily_report("2099-01-01")
        assert "0件" in report

    def test_generate_monthly_summary_no_data(self):
        """データなしで月次サマリーが生成できる."""
        from inquiry_bot.analytics import InquiryAnalytics
        analytics = InquiryAnalytics()
        report = analytics.generate_monthly_summary()
        assert isinstance(report, str)

    def test_log_inquiry(self, tmp_path):
        """問い合わせログが記録できる."""
        from inquiry_bot.analytics import InquiryAnalytics, ANALYTICS_DIR

        analytics = InquiryAnalytics()
        analytics.log_inquiry({
            "session_id": "test_123",
            "channel": "web",
            "user_id": "test_user",
            "message": "テストメッセージ",
            "category": "general",
            "escalated": False,
            "confidence": 0.9,
        })
        # ログファイルが作成されているか
        log_files = list(ANALYTICS_DIR.glob("inquiries_*.jsonl"))
        assert len(log_files) > 0


# ═══ Schedulerのテスト ═══

class TestScheduler:
    """スケジューラーのテスト."""

    def test_scheduler_tasks_defined(self):
        """全スケジューラータスクが定義されている."""
        from inquiry_bot.scheduler import TASKS
        expected = [
            "daily_report", "health_check", "weekly_summary",
            "faq_update_check", "results_to_x", "auto_restart",
        ]
        for task in expected:
            assert task in TASKS, f"Task '{task}' not found in scheduler"


# ═══ Web Widgetのテスト ═══

class TestWebWidget:
    """Webウィジェットの静的ファイルテスト."""

    def test_index_html_exists(self):
        """index.html が存在する."""
        path = Path(__file__).parent.parent / "inquiry_bot" / "web_widget" / "index.html"
        assert path.exists()

    def test_embed_js_exists(self):
        """embed.js が存在する."""
        path = Path(__file__).parent.parent / "inquiry_bot" / "web_widget" / "embed.js"
        assert path.exists()

    def test_demo_html_exists(self):
        """demo.html が存在する."""
        path = Path(__file__).parent.parent / "inquiry_bot" / "web_widget" / "demo.html"
        assert path.exists()

    def test_demo_has_pricing(self):
        """デモページに料金プランが含まれている."""
        path = Path(__file__).parent.parent / "inquiry_bot" / "web_widget" / "demo.html"
        content = path.read_text(encoding="utf-8")
        assert "ライト" in content
        assert "スタンダード" in content
        assert "プレミアム" in content
