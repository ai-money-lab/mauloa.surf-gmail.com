"""Tests for core/quality_checker.py — QualityChecker class.

Covers:
- Profile configuration (thresholds 84/75/70, items, max_score)
- check(): approval, rejection, threshold boundary, escalation
- check_with_retry(): regeneration, escalation, notification
- EA/FX banned content check item presence
- Log file creation
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from core.quality_checker import QualityChecker, PROFILES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_claude():
    """Return a mocked ClaudeClient instance."""
    return MagicMock()


@pytest.fixture
def checker(mock_claude, tmp_path):
    """Return a QualityChecker with mocked dependencies and temp log dir."""
    with patch("core.quality_checker.LOG_DIR", tmp_path / "quality_logs"), \
         patch("core.quality_checker.PROMPT_TEMPLATE_PATH") as mock_tpl:
        mock_tpl.read_text.return_value = (
            "Profile: {profile}\n"
            "Items:\n{チェック項目リスト（プロファイルに応じて上記から選択）}\n"
            "Threshold: {threshold}"
        )
        qc = QualityChecker(claude_client=mock_claude)
        qc.notifier = MagicMock()
        yield qc


# ---------------------------------------------------------------------------
# PROFILES configuration tests
# ---------------------------------------------------------------------------

class TestProfilesConfig:
    """Verify the three quality profiles are correctly configured."""

    def test_three_profiles_exist(self):
        assert "x_post" in PROFILES
        assert "report" in PROFILES
        assert "data_collection" in PROFILES

    def test_x_post_threshold_is_84(self):
        assert PROFILES["x_post"]["threshold"] == 84

    def test_report_threshold_is_75(self):
        assert PROFILES["report"]["threshold"] == 75

    def test_data_collection_threshold_is_70(self):
        assert PROFILES["data_collection"]["threshold"] == 70

    def test_x_post_max_score_is_120(self):
        assert PROFILES["x_post"]["max_score"] == 120

    def test_report_max_score_is_100(self):
        assert PROFILES["report"]["max_score"] == 100

    def test_data_collection_max_score_is_100(self):
        assert PROFILES["data_collection"]["max_score"] == 100

    def test_x_post_has_12_items(self):
        assert len(PROFILES["x_post"]["items"]) == 12

    def test_report_has_10_items(self):
        assert len(PROFILES["report"]["items"]) == 10

    def test_data_collection_has_10_items(self):
        assert len(PROFILES["data_collection"]["items"]) == 10

    def test_all_profiles_have_required_keys(self):
        for name, cfg in PROFILES.items():
            assert "items" in cfg, f"{name} missing 'items'"
            assert "threshold" in cfg, f"{name} missing 'threshold'"
            assert "max_score" in cfg, f"{name} missing 'max_score'"

    def test_no_banned_content_item_in_all_profiles(self):
        """Every profile must include the no_banned_content check."""
        for name, cfg in PROFILES.items():
            assert "no_banned_content" in cfg["items"], (
                f"Profile '{name}' is missing 'no_banned_content' item"
            )

    def test_x_post_contains_hook_power_and_originality(self):
        items = PROFILES["x_post"]["items"]
        assert "hook_power" in items
        assert "originality" in items

    def test_report_contains_data_accuracy(self):
        assert "data_accuracy" in PROFILES["report"]["items"]

    def test_data_collection_contains_source_reliability(self):
        assert "source_reliability" in PROFILES["data_collection"]["items"]


# ---------------------------------------------------------------------------
# check() — approval / rejection / boundary
# ---------------------------------------------------------------------------

class TestCheck:
    """Tests for QualityChecker.check()."""

    def test_auto_approved_when_above_threshold(self, checker, mock_claude):
        mock_claude.generate_json.return_value = {
            "total_score": 90,
            "scores": {"hook_power": 9},
        }
        result = checker.check("x_post", "テストポスト")
        assert result["result"] == "auto_approved"
        assert result["total_score"] == 90

    def test_rejected_when_below_threshold(self, checker, mock_claude):
        mock_claude.generate_json.return_value = {
            "total_score": 50,
            "scores": {"hook_power": 5},
        }
        result = checker.check("x_post", "弱いポスト")
        assert result["result"] == "rejected"

    def test_exactly_at_x_post_threshold_84_is_approved(self, checker, mock_claude):
        mock_claude.generate_json.return_value = {"total_score": 84, "scores": {}}
        result = checker.check("x_post", "ぎりぎりポスト")
        assert result["result"] == "auto_approved"

    def test_one_below_x_post_threshold_is_rejected(self, checker, mock_claude):
        mock_claude.generate_json.return_value = {"total_score": 83, "scores": {}}
        result = checker.check("x_post", "テスト")
        assert result["result"] == "rejected"

    def test_report_threshold_boundary_75(self, checker, mock_claude):
        mock_claude.generate_json.return_value = {"total_score": 74, "scores": {}}
        assert checker.check("report", "レポート")["result"] == "rejected"

        mock_claude.generate_json.return_value = {"total_score": 75, "scores": {}}
        assert checker.check("report", "レポート")["result"] == "auto_approved"

    def test_data_collection_threshold_boundary_70(self, checker, mock_claude):
        mock_claude.generate_json.return_value = {"total_score": 69, "scores": {}}
        assert checker.check("data_collection", "データ")["result"] == "rejected"

        mock_claude.generate_json.return_value = {"total_score": 70, "scores": {}}
        assert checker.check("data_collection", "データ")["result"] == "auto_approved"

    def test_unknown_profile_raises_value_error(self, checker):
        with pytest.raises(ValueError, match="Unknown profile"):
            checker.check("nonexistent_profile", "content")

    def test_result_contains_checked_at_and_threshold(self, checker, mock_claude):
        mock_claude.generate_json.return_value = {"total_score": 90, "scores": {}}
        result = checker.check("x_post", "テスト")
        assert "checked_at" in result
        assert result["threshold"] == 84

    def test_threshold_defaults_from_profile_if_not_in_response(self, checker, mock_claude):
        mock_claude.generate_json.return_value = {"total_score": 80, "scores": {}}
        result = checker.check("report", "テスト")
        assert result["threshold"] == 75


# ---------------------------------------------------------------------------
# Escalation / retry logic
# ---------------------------------------------------------------------------

class TestEscalation:
    """Tests for retry/escalation when Claude returns bad JSON."""

    def test_escalated_after_max_retries_on_json_error(self, checker, mock_claude):
        mock_claude.generate_json.side_effect = json.JSONDecodeError("", "", 0)
        result = checker.check("x_post", "content", max_retries=3)
        assert result["result"] == "escalated"
        assert result["total_score"] == 0
        assert "error" in result

    def test_escalation_sends_line_notification(self, checker, mock_claude):
        mock_claude.generate_json.side_effect = json.JSONDecodeError("", "", 0)
        checker.check("x_post", "content", max_retries=2)
        checker.notifier.send_line.assert_called_once()

    def test_retries_exact_count_before_escalation(self, checker, mock_claude):
        mock_claude.generate_json.side_effect = json.JSONDecodeError("", "", 0)
        checker.check("x_post", "content", max_retries=3)
        assert mock_claude.generate_json.call_count == 3

    def test_success_on_second_attempt_stops_retrying(self, checker, mock_claude):
        mock_claude.generate_json.side_effect = [
            json.JSONDecodeError("", "", 0),
            {"total_score": 90, "scores": {}},
        ]
        result = checker.check("x_post", "content", max_retries=3)
        assert result["result"] == "auto_approved"
        assert mock_claude.generate_json.call_count == 2

    def test_key_error_also_triggers_retry(self, checker, mock_claude):
        mock_claude.generate_json.side_effect = KeyError("missing_field")
        result = checker.check("x_post", "content", max_retries=2)
        assert result["result"] == "escalated"
        assert mock_claude.generate_json.call_count == 2


# ---------------------------------------------------------------------------
# check_with_retry()
# ---------------------------------------------------------------------------

class TestCheckWithRetry:
    """Tests for QualityChecker.check_with_retry()."""

    def test_returns_immediately_on_first_approval(self, checker, mock_claude):
        mock_claude.generate_json.return_value = {"total_score": 90, "scores": {}}
        content, result = checker.check_with_retry("x_post", "良い投稿")
        assert result["result"] == "auto_approved"
        assert content == "良い投稿"

    def test_regenerate_fn_called_on_rejection(self, checker, mock_claude):
        call_count = [0]

        def mock_regenerate(reasons, suggestions):
            call_count[0] += 1
            return "改善された投稿"

        mock_claude.generate_json.side_effect = [
            {
                "total_score": 50,
                "scores": {},
                "rejection_reasons": ["弱い"],
                "improvement_suggestions": ["もっと強く"],
            },
            {"total_score": 90, "scores": {}},
        ]

        content, result = checker.check_with_retry(
            "x_post", "弱い投稿", regenerate_fn=mock_regenerate, max_retries=3
        )
        assert call_count[0] == 1
        assert content == "改善された投稿"
        assert result["result"] == "auto_approved"

    def test_escalated_without_regenerate_fn(self, checker, mock_claude):
        mock_claude.generate_json.return_value = {"total_score": 50, "scores": {}}
        content, result = checker.check_with_retry(
            "x_post", "弱い投稿", regenerate_fn=None, max_retries=1
        )
        assert result["result"] == "escalated"

    def test_escalation_notification_sent_on_max_retry(self, checker, mock_claude):
        mock_claude.generate_json.return_value = {"total_score": 50, "scores": {}}
        checker.check_with_retry("x_post", "弱い投稿", max_retries=1)
        checker.notifier.send_line.assert_called()

    def test_original_content_returned_when_no_regenerate(self, checker, mock_claude):
        mock_claude.generate_json.return_value = {"total_score": 50, "scores": {}}
        content, _ = checker.check_with_retry(
            "x_post", "元のテキスト", regenerate_fn=None, max_retries=1
        )
        assert content == "元のテキスト"


# ---------------------------------------------------------------------------
# Log file tests
# ---------------------------------------------------------------------------

class TestLogSaving:
    """Tests for quality log file creation."""

    def test_log_file_created_on_check(self, checker, mock_claude, tmp_path):
        mock_claude.generate_json.return_value = {"total_score": 90, "scores": {}}
        checker.check("x_post", "テスト")
        log_dir = tmp_path / "quality_logs"
        log_files = list(log_dir.glob("*.json"))
        assert len(log_files) == 1

    def test_log_file_contains_profile_and_attempt(self, checker, mock_claude, tmp_path):
        mock_claude.generate_json.return_value = {"total_score": 90, "scores": {}}
        checker.check("report", "レポート")
        log_dir = tmp_path / "quality_logs"
        log_files = list(log_dir.glob("*.json"))
        data = json.loads(log_files[0].read_text(encoding="utf-8"))
        assert data["profile"] == "report"
        assert data["attempt"] == 1

    def test_escalation_log_file_created(self, checker, mock_claude, tmp_path):
        mock_claude.generate_json.side_effect = json.JSONDecodeError("", "", 0)
        checker.check("x_post", "content", max_retries=1)
        log_dir = tmp_path / "quality_logs"
        log_files = list(log_dir.glob("*.json"))
        assert len(log_files) == 1
        data = json.loads(log_files[0].read_text(encoding="utf-8"))
        assert data["result"] == "escalated"
