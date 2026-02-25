"""Tests for Bot Insights Bridge and Code Test Harness."""

import json
from unittest.mock import MagicMock, patch

from system_e.bot_insights_bridge import BotInsightsBridge
from system_e.code_test_harness import CodeTestHarness
from system_e.orchestrator import Orchestrator


# ─── BotInsightsBridge Tests ──────────────────────────────


class TestBotInsightsLoadLogs:
    def test_load_empty_dir(self, tmp_path):
        bridge = BotInsightsBridge(
            claude_client=MagicMock(),
            bot_logs_dir=tmp_path / "nonexistent",
        )
        assert bridge.load_bot_logs() == []

    def test_load_valid_logs(self, tmp_path):
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        from datetime import datetime, timezone, timedelta
        JST = timezone(timedelta(hours=9))
        today = datetime.now(JST).strftime("%Y%m%d")

        entries = [
            {"message": "営業時間は？", "category": "faq", "confidence": 0.9, "escalated": False, "channel": "line", "hour": 10},
            {"message": "物件の詳細を教えて", "category": "property", "confidence": 0.3, "escalated": True, "channel": "web", "hour": 14},
        ]
        log_file = logs_dir / f"inquiries_{today}.jsonl"
        log_file.write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in entries),
            encoding="utf-8",
        )

        bridge = BotInsightsBridge(claude_client=MagicMock(), bot_logs_dir=logs_dir)
        result = bridge.load_bot_logs(days=1)
        assert len(result) == 2
        assert result[0]["category"] == "faq"

    def test_load_skips_malformed(self, tmp_path):
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        from datetime import datetime, timezone, timedelta
        JST = timezone(timedelta(hours=9))
        today = datetime.now(JST).strftime("%Y%m%d")

        log_file = logs_dir / f"inquiries_{today}.jsonl"
        log_file.write_text(
            '{"message": "test"}\nINVALID\n{"message": "test2"}\n',
            encoding="utf-8",
        )

        bridge = BotInsightsBridge(claude_client=MagicMock(), bot_logs_dir=logs_dir)
        result = bridge.load_bot_logs(days=1)
        assert len(result) == 2


class TestBotInsightsMetrics:
    def test_empty_metrics(self, tmp_path):
        bridge = BotInsightsBridge(
            claude_client=MagicMock(),
            bot_logs_dir=tmp_path / "nonexistent",
        )
        metrics = bridge.compute_bot_metrics([])
        assert metrics["total_inquiries"] == 0
        assert metrics["auto_resolve_rate"] == 0.0
        assert metrics["saved_hours"] == 0.0

    def test_compute_metrics(self):
        logs = [
            {"category": "faq", "confidence": 0.9, "escalated": False, "channel": "line", "hour": 10},
            {"category": "faq", "confidence": 0.8, "escalated": False, "channel": "line", "hour": 10},
            {"category": "property", "confidence": 0.3, "escalated": True, "channel": "web", "hour": 14},
            {"category": "billing", "confidence": 0.2, "escalated": True, "channel": "web", "hour": 15},
            {"category": "faq", "confidence": 0.7, "escalated": False, "channel": "line", "hour": 11},
        ]
        bridge = BotInsightsBridge(claude_client=MagicMock())
        metrics = bridge.compute_bot_metrics(logs)

        assert metrics["total_inquiries"] == 5
        assert metrics["auto_resolve_rate"] == 0.6
        assert metrics["escalation_rate"] == 0.4
        assert metrics["low_confidence_count"] == 2  # 0.3 and 0.2
        assert "faq" in metrics["category_distribution"]
        assert 10 in metrics["peak_hours"]
        assert metrics["saved_hours"] == round(3 * 5 / 60, 1)  # 3 auto-resolved * 5min / 60

    def test_avg_confidence(self):
        logs = [
            {"confidence": 0.5},
            {"confidence": 1.0},
        ]
        bridge = BotInsightsBridge(claude_client=MagicMock())
        metrics = bridge.compute_bot_metrics(logs)
        assert abs(metrics["avg_confidence"] - 0.75) < 0.01


class TestBotInsightsPatterns:
    def test_empty_patterns(self):
        bridge = BotInsightsBridge(claude_client=MagicMock())
        patterns = bridge.detect_improvement_patterns([])
        assert patterns["faq_gaps"] == []
        assert patterns["escalation_hotspots"] == []
        assert patterns["confidence_issues"] == []

    def test_detect_patterns(self):
        logs = [
            {"category": "faq", "confidence": 0.3, "escalated": False, "message": "営業時間は何時ですか"},
            {"category": "faq", "confidence": 0.4, "escalated": False, "message": "営業時間は何時ですか"},
            {"category": "faq", "confidence": 0.4, "escalated": False, "message": "営業時間は何時ですか"},
            {"category": "property", "confidence": 0.8, "escalated": True, "message": "物件の詳細"},
            {"category": "property", "confidence": 0.7, "escalated": True, "message": "物件の見学"},
            {"category": "billing", "confidence": 0.2, "escalated": False, "message": "支払い方法は"},
        ]
        bridge = BotInsightsBridge(claude_client=MagicMock())
        patterns = bridge.detect_improvement_patterns(logs)

        # FAQ gaps: "営業時間" pattern occurs 3 times with low confidence
        assert len(patterns["faq_gaps"]) >= 1
        assert patterns["faq_gaps"][0]["count"] >= 2

        # Escalation hotspots
        assert len(patterns["escalation_hotspots"]) >= 1
        assert patterns["escalation_hotspots"][0]["category"] == "property"

        # Very low confidence (< 0.3 threshold)
        assert len(patterns["confidence_issues"]) >= 1  # 0.2 is below 0.3


class TestBotInsightsFeedback:
    def test_evolution_feedback_empty(self, tmp_path):
        import system_e.bot_insights_bridge as bib
        original = bib.INSIGHTS_DIR
        bib.INSIGHTS_DIR = tmp_path / "insights"
        bib.INSIGHTS_DIR.mkdir()

        try:
            bridge = BotInsightsBridge(
                claude_client=MagicMock(),
                bot_logs_dir=tmp_path / "nonexistent",
            )
            feedback = bridge.generate_evolution_feedback()
            assert feedback["source"] == "bot_insights_bridge"
            assert "bot_weekly_metrics" in feedback
            assert "bot_monthly_metrics" in feedback
            assert "improvement_patterns" in feedback
            assert "bot_health_indicators" in feedback
        finally:
            bib.INSIGHTS_DIR = original

    def test_health_indicators(self, tmp_path):
        import system_e.bot_insights_bridge as bib
        original = bib.INSIGHTS_DIR
        bib.INSIGHTS_DIR = tmp_path / "insights"
        bib.INSIGHTS_DIR.mkdir()

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        from datetime import datetime, timezone, timedelta
        JST = timezone(timedelta(hours=9))
        today = datetime.now(JST).strftime("%Y%m%d")

        # Good metrics: 80% auto-resolve, high confidence
        entries = [
            {"category": "faq", "confidence": 0.9, "escalated": False, "channel": "line", "hour": 10},
            {"category": "faq", "confidence": 0.8, "escalated": False, "channel": "line", "hour": 11},
            {"category": "faq", "confidence": 0.85, "escalated": False, "channel": "web", "hour": 12},
            {"category": "faq", "confidence": 0.7, "escalated": False, "channel": "web", "hour": 13},
            {"category": "property", "confidence": 0.4, "escalated": True, "channel": "web", "hour": 14},
        ]
        (logs_dir / f"inquiries_{today}.jsonl").write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in entries),
            encoding="utf-8",
        )

        try:
            bridge = BotInsightsBridge(claude_client=MagicMock(), bot_logs_dir=logs_dir)
            feedback = bridge.generate_evolution_feedback()
            indicators = feedback["bot_health_indicators"]
            assert indicators["auto_resolve_rate_healthy"] is True
            assert indicators["escalation_rate_healthy"] is True
        finally:
            bib.INSIGHTS_DIR = original


class TestBotInsightsCycle:
    @patch("system_e.bot_insights_bridge.ClaudeClient")
    def test_insight_cycle(self, mock_cls, tmp_path):
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({"analysis": "ok"})

        import system_e.bot_insights_bridge as bib
        original = bib.INSIGHTS_DIR
        bib.INSIGHTS_DIR = tmp_path / "insights"
        bib.INSIGHTS_DIR.mkdir()

        try:
            bridge = BotInsightsBridge(
                claude_client=mock_client,
                bot_logs_dir=tmp_path / "nonexistent",
            )
            result = bridge.run_insight_cycle()
            assert "metrics" in result
            assert "patterns" in result
            assert "strategy_analysis" in result
            assert "evolution_feedback" in result
        finally:
            bib.INSIGHTS_DIR = original


# ─── CodeTestHarness Tests ────────────────────────────────


class TestHarnessBasic:
    def test_valid_module(self):
        code = '''"""Test module."""

def hello(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}"


class Greeter:
    """A greeter class."""

    def __init__(self):
        self.count = 0

    def greet(self, name: str) -> str:
        self.count += 1
        return f"Hi, {name}"
'''
        harness = CodeTestHarness()
        result = harness.run_tests(code, "test_greeter")
        assert result.passed is True
        assert result.passed_tests > 0
        assert result.module_name == "test_greeter"

    def test_syntax_error(self):
        code = "def broken(\n    pass"
        harness = CodeTestHarness()
        result = harness.run_tests(code, "broken_module")
        assert result.passed is False
        assert any(tc.category == "structure" and not tc.passed for tc in result.test_cases)

    def test_empty_module(self):
        code = '"""Empty module."""\n'
        harness = CodeTestHarness()
        result = harness.run_tests(code, "empty_mod")
        # Has docstring but no definitions
        assert any(tc.name == "has_definitions" for tc in result.test_cases)

    def test_no_docstring(self):
        code = "x = 1\n"
        harness = CodeTestHarness()
        result = harness.run_tests(code, "no_doc")
        docstring_case = next(
            (tc for tc in result.test_cases if tc.name == "has_module_docstring"),
            None,
        )
        assert docstring_case is not None
        assert docstring_case.passed is False


class TestHarnessImport:
    def test_importable_module(self):
        code = '''"""Simple module."""

import json
import logging

logger = logging.getLogger(__name__)


def process(data: dict) -> str:
    return json.dumps(data)
'''
        harness = CodeTestHarness()
        result = harness.run_tests(code, "importable_mod")
        import_case = next(
            (tc for tc in result.test_cases if tc.name == "sandbox_import"),
            None,
        )
        assert import_case is not None
        assert import_case.passed is True

    def test_import_error_module(self):
        code = '''"""Module with bad import."""

import nonexistent_package_xyz_123

def do_thing():
    pass
'''
        harness = CodeTestHarness()
        result = harness.run_tests(code, "bad_import_mod")
        import_case = next(
            (tc for tc in result.test_cases if tc.name == "sandbox_import"),
            None,
        )
        assert import_case is not None
        assert import_case.passed is False


class TestHarnessCallable:
    def test_class_instantiation(self):
        code = '''"""Module with simple class."""

class SimpleConfig:
    def __init__(self):
        self.value = 42
'''
        harness = CodeTestHarness()
        result = harness.run_tests(code, "simple_class")
        inst_case = next(
            (tc for tc in result.test_cases if tc.name == "instantiate_SimpleConfig"),
            None,
        )
        assert inst_case is not None
        assert inst_case.passed is True

    def test_class_requiring_args(self):
        code = '''"""Module with class requiring args."""

class Database:
    def __init__(self, connection_string: str):
        self.conn = connection_string
'''
        harness = CodeTestHarness()
        result = harness.run_tests(code, "arg_class")
        inst_case = next(
            (tc for tc in result.test_cases if tc.name == "instantiate_Database"),
            None,
        )
        assert inst_case is not None
        # Should not fail — just skip when args needed
        assert inst_case.passed is True


class TestHarnessTypeHints:
    def test_good_type_hints(self):
        code = '''"""Module with type hints."""

def add(a: int, b: int) -> int:
    return a + b

def multiply(x: float, y: float) -> float:
    return x * y
'''
        harness = CodeTestHarness()
        result = harness.run_tests(code, "typed_mod")
        hint_case = next(
            (tc for tc in result.test_cases if tc.name == "type_hint_coverage"),
            None,
        )
        assert hint_case is not None
        assert hint_case.passed is True

    def test_no_type_hints(self):
        code = '''"""Module without type hints."""

def add(a, b):
    return a + b

def multiply(x, y):
    return x * y

def divide(a, b):
    return a / b

def subtract(a, b):
    return a - b
'''
        harness = CodeTestHarness()
        result = harness.run_tests(code, "untyped_mod")
        hint_case = next(
            (tc for tc in result.test_cases if tc.name == "type_hint_coverage"),
            None,
        )
        assert hint_case is not None
        assert hint_case.passed is False


class TestHarnessResultDict:
    def test_to_dict(self):
        code = '''"""Simple module."""

def hello() -> str:
    return "world"
'''
        harness = CodeTestHarness()
        result = harness.run_tests(code, "dict_test")
        d = result.to_dict()
        assert "module_name" in d
        assert "passed" in d
        assert "total_tests" in d
        assert "test_cases" in d
        assert isinstance(d["test_cases"], list)


# ─── Orchestrator Integration Tests ─────────────────────


class TestOrchestratorBotInsight:
    @patch("system_e.orchestrator.ClaudeClient")
    def test_has_bot_insights(self, mock_cls):
        mock_client = MagicMock()
        orch = Orchestrator(claude_client=mock_client)
        assert hasattr(orch, "bot_insights")
        assert isinstance(orch.bot_insights, BotInsightsBridge)

    @patch("system_e.orchestrator.ClaudeClient")
    def test_has_test_harness(self, mock_cls):
        mock_client = MagicMock()
        orch = Orchestrator(claude_client=mock_client)
        assert hasattr(orch, "test_harness")
        assert isinstance(orch.test_harness, CodeTestHarness)

    @patch("system_e.orchestrator.ClaudeClient")
    def test_run_bot_insight(self, mock_cls, tmp_path):
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({"ok": True})

        import system_e.bot_insights_bridge as bib
        original = bib.INSIGHTS_DIR
        bib.INSIGHTS_DIR = tmp_path / "insights"
        bib.INSIGHTS_DIR.mkdir()

        try:
            orch = Orchestrator(claude_client=mock_client)
            result = orch.run_bot_insight()
            assert "metrics" in result
            assert "patterns" in result
        finally:
            bib.INSIGHTS_DIR = original

    @patch("system_e.orchestrator.ClaudeClient")
    def test_smart_evolve_includes_bot_feedback(self, mock_cls, tmp_path):
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({
            "changes": [], "posting_strategy": {}, "content_strategy": {},
        })

        import system_e.nexus_bridge as nb
        import system_e.self_improve as si
        import system_e.bot_insights_bridge as bib

        original_bridge = nb.BRIDGE_LOG_DIR
        original_strategy = si.STRATEGY_FILE
        original_evo = si.EVOLUTION_DIR
        original_insights = bib.INSIGHTS_DIR

        nb.BRIDGE_LOG_DIR = tmp_path / "bridge"
        nb.BRIDGE_LOG_DIR.mkdir()
        si.STRATEGY_FILE = tmp_path / "strategy.json"
        si.EVOLUTION_DIR = tmp_path / "evolution"
        si.EVOLUTION_DIR.mkdir()
        bib.INSIGHTS_DIR = tmp_path / "insights"
        bib.INSIGHTS_DIR.mkdir()

        try:
            orch = Orchestrator(claude_client=mock_client)
            result = orch.run_smart_evolve()
            assert "bot_feedback" in result
            assert "nexus_feedback" in result
            assert "performance_metrics" in result
            assert "evolution" in result
        finally:
            nb.BRIDGE_LOG_DIR = original_bridge
            si.STRATEGY_FILE = original_strategy
            si.EVOLUTION_DIR = original_evo
            bib.INSIGHTS_DIR = original_insights
