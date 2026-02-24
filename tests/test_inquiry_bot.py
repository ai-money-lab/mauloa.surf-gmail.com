"""問い合わせBot — 自動テスト."""

import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

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


# ═══ BotEngine config failureのテスト ═══

class TestBotEngineConfigFailure:
    """_load_config が空/不正ファイルで例外を発生させることを検証."""

    def test_load_config_empty_file_raises(self, tmp_path):
        """空のYAMLファイルで ValueError が発生する."""
        from inquiry_bot.bot_engine import BotEngine
        config_file = tmp_path / "config.yaml"
        config_file.write_text("", encoding="utf-8")
        with pytest.raises(Exception):
            BotEngine(config_path=config_file)

    def test_load_config_invalid_yaml_raises(self, tmp_path):
        """不正なYAMLで例外が発生する."""
        from inquiry_bot.bot_engine import BotEngine
        config_file = tmp_path / "config.yaml"
        config_file.write_text(": : : invalid yaml {{{", encoding="utf-8")
        with pytest.raises(Exception):
            BotEngine(config_path=config_file)

    def test_load_config_missing_file_raises(self, tmp_path):
        """存在しないファイルで例外が発生する."""
        from inquiry_bot.bot_engine import BotEngine
        with pytest.raises(Exception):
            BotEngine(config_path=tmp_path / "nonexistent.yaml")


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


# ═══ KnowledgeBase ユニットテスト ═══

class TestKnowledgeBase:
    """KnowledgeBase の全パブリックメソッドをテスト."""

    def test_search_faq_exact_match(self):
        from inquiry_bot.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        results = kb.search_faq("初期費用")
        assert len(results) > 0
        assert results[0]["score"] >= 10  # 完全一致

    def test_search_faq_no_match(self):
        from inquiry_bot.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        results = kb.search_faq("zzzzz_no_match_zzzzz")
        assert results == []

    def test_get_faq_context_all(self):
        from inquiry_bot.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        ctx = kb.get_faq_context()
        assert len(ctx) > 0
        assert "###" in ctx  # ヘッダーが含まれる

    def test_get_faq_context_by_category(self):
        from inquiry_bot.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        # 存在しないカテゴリでは空
        ctx = kb.get_faq_context(category="nonexistent_category")
        assert ctx == ""

    def test_get_property_info_found(self):
        from inquiry_bot.knowledge_base import KnowledgeBase
        kb = KnowledgeBase(property_data={"P001": {"name": "テスト物件", "rent": 80000}})
        info = kb.get_property_info("P001")
        assert info["name"] == "テスト物件"

    def test_get_property_info_not_found(self):
        from inquiry_bot.knowledge_base import KnowledgeBase
        kb = KnowledgeBase(property_data={})
        assert kb.get_property_info("XXXX") == {}

    def test_get_all_properties_summary_empty(self):
        from inquiry_bot.knowledge_base import KnowledgeBase
        kb = KnowledgeBase(property_data={})
        summary = kb.get_all_properties_summary()
        assert "未登録" in summary

    def test_get_all_properties_summary_with_data(self):
        from inquiry_bot.knowledge_base import KnowledgeBase
        kb = KnowledgeBase(property_data={
            "P001": {"name": "サンプルマンション", "rent": 85000, "vacancy_status": "空室あり"},
        })
        summary = kb.get_all_properties_summary()
        assert "サンプルマンション" in summary
        assert "85000" in summary

    def test_fill_template(self):
        from inquiry_bot.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        kb.company = {"name": "テスト不動産"}
        result = kb.fill_template("会社名: {company_name}", {})
        assert result == "会社名: テスト不動産"

    def test_fill_template_with_data(self):
        from inquiry_bot.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        kb.company = {}
        result = kb.fill_template("物件名: {property_name}", {"property_name": "ABCマンション"})
        assert result == "物件名: ABCマンション"

    def test_update_property_data(self):
        from inquiry_bot.knowledge_base import KnowledgeBase
        kb = KnowledgeBase(property_data={})
        kb.update_property_data("P999", {"name": "新物件", "rent": 70000})
        assert kb.property_data["P999"]["name"] == "新物件"

    def test_load_properties_from_yaml(self, tmp_path):
        from inquiry_bot.knowledge_base import KnowledgeBase
        yaml_file = tmp_path / "props.yaml"
        yaml_file.write_text(yaml.dump({
            "properties": {"P001": {"name": "YAML物件", "rent": 90000}},
        }), encoding="utf-8")
        kb = KnowledgeBase(property_data={})
        kb.load_properties_from_yaml(yaml_file)
        assert kb.property_data["P001"]["name"] == "YAML物件"

    def test_load_faq_missing_file(self, tmp_path):
        from inquiry_bot.knowledge_base import KnowledgeBase
        kb = KnowledgeBase(faq_path=tmp_path / "nonexistent.yaml")
        assert kb.faqs == []
        assert kb.company == {}


# ═══ ConversationManager ユニットテスト ═══

class TestConversationManager:
    """ConversationManager の全パブリックメソッドをテスト."""

    def test_create_session(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        session = cm.get_or_create_session("s1", "web", "user1")
        assert session.session_id == "s1"
        assert session.channel == "web"
        assert session.user_id == "user1"

    def test_get_existing_session(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        s1 = cm.get_or_create_session("s1", "web", "user1")
        s2 = cm.get_or_create_session("s1", "web", "user1")
        assert s1 is s2

    def test_session_timeout_creates_new(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        s1 = cm.get_or_create_session("s1", "web", "user1")
        # Fake timeout
        s1.last_activity = time.time() - 7200
        s2 = cm.get_or_create_session("s1", "web", "user1")
        assert s2 is not s1

    def test_add_message(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        cm.get_or_create_session("s1", "web", "user1")
        cm.add_message("s1", "user", "こんにちは")
        assert len(cm.sessions["s1"].messages) == 1
        assert cm.sessions["s1"].messages[0].content == "こんにちは"

    def test_add_message_nonexistent_session(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        cm.add_message("nonexistent", "user", "test")  # should not raise

    def test_add_message_respects_history_limit(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager(history_limit=3)
        cm.get_or_create_session("s1", "web", "user1")
        for i in range(10):
            cm.add_message("s1", "user", f"msg{i}")
        # history_limit * 2 = 6, so only 6 messages should remain
        assert len(cm.sessions["s1"].messages) == 6

    def test_get_conversation_history(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        cm.get_or_create_session("s1", "web", "user1")
        cm.add_message("s1", "user", "質問")
        cm.add_message("s1", "assistant", "回答")
        history = cm.get_conversation_history("s1")
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "質問"}
        assert history[1] == {"role": "assistant", "content": "回答"}

    def test_get_conversation_history_nonexistent(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        assert cm.get_conversation_history("nonexistent") == []

    def test_check_escalation_keyword(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        cm.get_or_create_session("s1", "web", "user1")
        should, reason = cm.check_escalation("s1", "弁護士に相談します")
        assert should is True
        assert "弁護士" in reason

    def test_check_escalation_no_trigger(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        cm.get_or_create_session("s1", "web", "user1")
        should, reason = cm.check_escalation("s1", "家賃を教えてください")
        assert should is False
        assert reason == ""

    def test_check_escalation_already_escalated(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        session = cm.get_or_create_session("s1", "web", "user1")
        session.escalated = True
        session.escalation_reason = "テスト"
        should, reason = cm.check_escalation("s1", "普通のメッセージ")
        assert should is True
        assert reason == "テスト"

    def test_check_escalation_nonexistent_session(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        should, reason = cm.check_escalation("nonexistent", "test")
        assert should is False

    def test_get_session_stats(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        cm.get_or_create_session("s1", "web", "user1")
        cm.add_message("s1", "user", "hello")
        cm.add_message("s1", "assistant", "hi")
        stats = cm.get_session_stats("s1")
        assert stats["session_id"] == "s1"
        assert stats["message_count"] == 2
        assert stats["user_messages"] == 1
        assert stats["escalated"] is False

    def test_get_session_stats_nonexistent(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        assert cm.get_session_stats("nonexistent") == {}

    def test_cleanup_expired_sessions(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        s1 = cm.get_or_create_session("s1", "web", "user1")
        cm.get_or_create_session("s2", "line", "user2")
        s1.last_activity = time.time() - 7200  # expired
        cleaned = cm.cleanup_expired_sessions()
        assert cleaned == 1
        assert "s1" not in cm.sessions
        assert "s2" in cm.sessions

    def test_session_message_count(self):
        from inquiry_bot.conversation_manager import Session
        session = Session(session_id="s1", channel="web", user_id="u1")
        assert session.message_count == 0
        assert session.user_message_count == 0


# ═══ BotEngine ユニットテスト（モック） ═══

class TestBotEngineHandleMessage:
    """BotEngine.handle_message の全分岐をテスト."""

    @patch("inquiry_bot.bot_engine.InquiryAnalytics")
    @patch("inquiry_bot.bot_engine.Notifier")
    @patch("inquiry_bot.bot_engine.ClaudeClient")
    def test_handle_message_normal(self, mock_claude_cls, mock_notifier_cls, mock_analytics_cls):
        from inquiry_bot.bot_engine import BotEngine
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_notifier_cls.return_value = MagicMock()
        mock_analytics_cls.return_value = MagicMock()

        mock_claude.generate.return_value = json.dumps({
            "reply": "テスト回答です",
            "category": "general",
            "confidence": 0.9,
            "escalate": False,
        })

        engine = BotEngine()
        result = engine.handle_message("こんにちは", "session1")
        assert result["reply"] == "テスト回答です"
        assert result["category"] == "general"
        assert result["escalated"] is False

    @patch("inquiry_bot.bot_engine.InquiryAnalytics")
    @patch("inquiry_bot.bot_engine.Notifier")
    @patch("inquiry_bot.bot_engine.ClaudeClient")
    def test_handle_message_escalation_keyword(self, mock_claude_cls, mock_notifier_cls, mock_analytics_cls):
        from inquiry_bot.bot_engine import BotEngine
        mock_claude_cls.return_value = MagicMock()
        mock_notifier_cls.return_value = MagicMock()
        mock_analytics_cls.return_value = MagicMock()

        engine = BotEngine()
        result = engine.handle_message("弁護士に相談する", "session2")
        assert result["escalated"] is True
        assert "弁護士" in result["escalation_reason"]

    @patch("inquiry_bot.bot_engine.InquiryAnalytics")
    @patch("inquiry_bot.bot_engine.Notifier")
    @patch("inquiry_bot.bot_engine.ClaudeClient")
    def test_handle_message_api_error_fallback(self, mock_claude_cls, mock_notifier_cls, mock_analytics_cls):
        from inquiry_bot.bot_engine import BotEngine
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_notifier_cls.return_value = MagicMock()
        mock_analytics_cls.return_value = MagicMock()

        mock_claude.generate.side_effect = RuntimeError("API down")

        engine = BotEngine()
        result = engine.handle_message("質問です", "session3")
        assert result["escalated"] is True
        assert result["category"] == "error"

    @patch("inquiry_bot.bot_engine.InquiryAnalytics")
    @patch("inquiry_bot.bot_engine.Notifier")
    @patch("inquiry_bot.bot_engine.ClaudeClient")
    def test_handle_message_non_json_response(self, mock_claude_cls, mock_notifier_cls, mock_analytics_cls):
        from inquiry_bot.bot_engine import BotEngine
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_notifier_cls.return_value = MagicMock()
        mock_analytics_cls.return_value = MagicMock()

        mock_claude.generate.return_value = "普通のテキスト回答です"

        engine = BotEngine()
        result = engine.handle_message("何かの質問", "session4")
        assert result["reply"] == "普通のテキスト回答です"
        assert result["confidence"] == 0.5  # fallback confidence

    @patch("inquiry_bot.bot_engine.InquiryAnalytics")
    @patch("inquiry_bot.bot_engine.Notifier")
    @patch("inquiry_bot.bot_engine.ClaudeClient")
    def test_handle_message_non_dict_json_response(self, mock_claude_cls, mock_notifier_cls, mock_analytics_cls):
        """Claude returns valid JSON that is not a dict (e.g., a list)."""
        from inquiry_bot.bot_engine import BotEngine
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_notifier_cls.return_value = MagicMock()
        mock_analytics_cls.return_value = MagicMock()

        mock_claude.generate.return_value = '["item1", "item2"]'

        engine = BotEngine()
        result = engine.handle_message("質問", "session_ndict")
        # Should wrap non-dict in a fallback response
        assert result["reply"] != ""
        assert result["confidence"] == 0.5

    @patch("inquiry_bot.bot_engine.InquiryAnalytics")
    @patch("inquiry_bot.bot_engine.Notifier")
    @patch("inquiry_bot.bot_engine.ClaudeClient")
    def test_get_analytics_empty(self, mock_claude_cls, mock_notifier_cls, mock_analytics_cls):
        from inquiry_bot.bot_engine import BotEngine
        mock_claude_cls.return_value = MagicMock()
        mock_notifier_cls.return_value = MagicMock()
        mock_analytics_cls.return_value = MagicMock()

        engine = BotEngine()
        stats = engine.get_analytics()
        assert stats["total_sessions"] == 0
        assert stats["active_sessions"] == 0
        assert stats["escalated_sessions"] == 0

    @patch("inquiry_bot.bot_engine.InquiryAnalytics")
    @patch("inquiry_bot.bot_engine.Notifier")
    @patch("inquiry_bot.bot_engine.ClaudeClient")
    def test_get_analytics_with_sessions(self, mock_claude_cls, mock_notifier_cls, mock_analytics_cls):
        from inquiry_bot.bot_engine import BotEngine
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_notifier_cls.return_value = MagicMock()
        mock_analytics_cls.return_value = MagicMock()

        mock_claude.generate.return_value = json.dumps({
            "reply": "ok", "category": "rent", "confidence": 0.9, "escalate": False,
        })

        engine = BotEngine()
        engine.handle_message("test", "s1", channel="web")
        engine.handle_message("test", "s2", channel="line")

        stats = engine.get_analytics()
        assert stats["total_sessions"] == 2
        assert stats["channels"]["web"] == 1
        assert stats["channels"]["line"] == 1


# ═══ ConversationManager 類似判定テスト ═══

class TestConversationManagerSimilarity:
    """SequenceMatcherベースの類似判定をテスト."""

    def test_repeated_same_message_triggers_escalation(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        cm.get_or_create_session("s1", "web", "user1")
        # 同じメッセージを3回追加
        for _ in range(3):
            cm.add_message("s1", "user", "家賃を教えてください")
        should, reason = cm.check_escalation("s1", "家賃を教えてください")
        assert should is True
        assert "繰り返" in reason

    def test_different_messages_no_escalation(self):
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        cm.get_or_create_session("s1", "web", "user1")
        cm.add_message("s1", "user", "家賃はいくらですか")
        cm.add_message("s1", "user", "駐車場はありますか")
        cm.add_message("s1", "user", "ペット可の物件はどれですか")
        should, reason = cm.check_escalation("s1", "別の質問です")
        assert should is False

    def test_similarity_single_chars_no_escalation(self):
        """短い異なるメッセージではエスカレーションしない."""
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        cm.get_or_create_session("s1", "web", "user1")
        cm.add_message("s1", "user", "あ")
        cm.add_message("s1", "user", "い")
        cm.add_message("s1", "user", "う")
        should, _ = cm.check_escalation("s1", "え")
        assert should is False

    def test_similar_japanese_messages_trigger_escalation(self):
        """日本語で類似した質問が3回続くとエスカレーション（スペースなし）."""
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        cm.get_or_create_session("s1", "web", "user1")
        cm.add_message("s1", "user", "空いていますか？")
        cm.add_message("s1", "user", "空いてますか？")
        cm.add_message("s1", "user", "空いてますか？")
        should, reason = cm.check_escalation("s1", "空いてますか？")
        assert should is True
        assert "繰り返" in reason

    def test_slightly_different_japanese_no_escalation(self):
        """意味が全く異なる日本語メッセージではエスカレーションしない."""
        from inquiry_bot.conversation_manager import ConversationManager
        cm = ConversationManager()
        cm.get_or_create_session("s1", "web", "user1")
        cm.add_message("s1", "user", "物件を見たいです")
        cm.add_message("s1", "user", "いつ引っ越しできますか？")
        cm.add_message("s1", "user", "何時に見学できますか？")
        should, _ = cm.check_escalation("s1", "何時に見学できますか？")
        assert should is False


# ═══ LineHandler セキュリティテスト ═══

class TestLineHandlerSecurity:
    """LINE署名検証のセキュリティテスト."""

    @patch("inquiry_bot.line_handler.BotEngine")
    def test_verify_signature_no_secret_rejects(self, mock_bot_cls):
        """LINE_CHANNEL_SECRETが未設定の場合、検証は拒否される."""
        from inquiry_bot.line_handler import LineHandler
        mock_bot_cls.return_value = MagicMock()
        handler = LineHandler(bot_engine=MagicMock())
        handler.channel_secret = ""
        result = handler.verify_signature("body", "sig")
        assert result is False

    @patch("inquiry_bot.line_handler.BotEngine")
    def test_verify_signature_valid(self, mock_bot_cls):
        """正しい署名で検証成功."""
        import hmac as _hmac
        import hashlib as _hashlib
        import base64 as _base64

        from inquiry_bot.line_handler import LineHandler
        mock_bot_cls.return_value = MagicMock()
        handler = LineHandler(bot_engine=MagicMock())
        handler.channel_secret = "test-secret"

        body = '{"events":[]}'
        digest = _hmac.new(b"test-secret", body.encode("utf-8"), _hashlib.sha256).digest()
        valid_sig = _base64.b64encode(digest).decode("utf-8")

        assert handler.verify_signature(body, valid_sig) is True

    @patch("inquiry_bot.line_handler.BotEngine")
    def test_verify_signature_invalid_rejects(self, mock_bot_cls):
        """不正な署名は拒否される."""
        from inquiry_bot.line_handler import LineHandler
        mock_bot_cls.return_value = MagicMock()
        handler = LineHandler(bot_engine=MagicMock())
        handler.channel_secret = "test-secret"

        assert handler.verify_signature('{"events":[]}', "wrong-signature") is False

    @patch("inquiry_bot.line_handler.BotEngine")
    def test_handle_webhook_invalid_json(self, mock_bot_cls):
        """不正なJSONはエラーを返す."""
        from inquiry_bot.line_handler import LineHandler
        mock_bot_cls.return_value = MagicMock()
        handler = LineHandler(bot_engine=MagicMock())
        handler.channel_secret = ""
        result = handler.handle_webhook("{bad json", "")
        # No secret → signature rejected first
        assert result.get("status") in (400, 403)

    @patch("inquiry_bot.line_handler.BotEngine")
    def test_handle_webhook_empty_events(self, mock_bot_cls):
        """空のeventsは正常に処理される."""
        from inquiry_bot.line_handler import LineHandler
        mock_bot_cls.return_value = MagicMock()
        handler = LineHandler(bot_engine=MagicMock())
        handler.channel_secret = "secret"

        import hmac as _hmac
        import hashlib as _hashlib
        import base64 as _base64
        body = '{"events":[]}'
        digest = _hmac.new(b"secret", body.encode(), _hashlib.sha256).digest()
        sig = _base64.b64encode(digest).decode()

        result = handler.handle_webhook(body, sig)
        assert result["status"] == 200
        assert result["results"] == []
