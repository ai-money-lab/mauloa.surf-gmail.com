"""Tests for core/quality_checker.py."""

import json
from unittest.mock import patch, MagicMock

import pytest

from core.quality_checker import QualityChecker, PROFILES


class TestQualityCheckerProfiles:
    """Test profile configuration."""

    def test_profiles_exist(self):
        assert "x_post" in PROFILES
        assert "report" in PROFILES
        assert "data_collection" in PROFILES

    def test_x_post_profile_has_12_items(self):
        assert len(PROFILES["x_post"]["items"]) == 12

    def test_x_post_threshold_is_80(self):
        assert PROFILES["x_post"]["threshold"] == 80

    def test_report_threshold_is_75(self):
        assert PROFILES["report"]["threshold"] == 75

    def test_data_collection_threshold_is_70(self):
        assert PROFILES["data_collection"]["threshold"] == 70

    def test_report_profile_has_10_items(self):
        assert len(PROFILES["report"]["items"]) == 10

    def test_data_collection_profile_has_10_items(self):
        assert len(PROFILES["data_collection"]["items"]) == 10


class TestQualityCheckerCheck:
    """Test the check method."""

    @patch("core.quality_checker.ClaudeClient")
    @patch("core.quality_checker.Notifier")
    def test_auto_approved_when_above_threshold(self, mock_notifier_cls, mock_claude_cls):
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_notifier_cls.return_value = MagicMock()

        mock_claude.generate_json.return_value = {
            "scores": {"hook_power": 9, "persona_match": 9},
            "total_score": 90,
            "threshold": 80,
            "result": "auto_approved",
            "rejection_reasons": [],
            "improvement_suggestions": [],
        }

        checker = QualityChecker(mock_claude)
        result = checker.check(profile="x_post", content="テスト投稿")

        assert result["result"] == "auto_approved"
        assert result["total_score"] >= 80

    @patch("core.quality_checker.ClaudeClient")
    @patch("core.quality_checker.Notifier")
    def test_rejected_when_below_threshold(self, mock_notifier_cls, mock_claude_cls):
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_notifier_cls.return_value = MagicMock()

        mock_claude.generate_json.return_value = {
            "scores": {"hook_power": 3, "persona_match": 4},
            "total_score": 50,
            "threshold": 80,
            "result": "rejected",
            "rejection_reasons": ["低品質"],
            "improvement_suggestions": ["改善してください"],
        }

        checker = QualityChecker(mock_claude)
        result = checker.check(profile="x_post", content="低品質テスト")

        assert result["result"] == "rejected"
        assert result["total_score"] < 80

    @patch("core.quality_checker.ClaudeClient")
    @patch("core.quality_checker.Notifier")
    def test_escalated_after_max_retries(self, mock_notifier_cls, mock_claude_cls):
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_notifier_cls.return_value = MagicMock()

        mock_claude.generate_json.side_effect = json.JSONDecodeError("fail", "", 0)

        checker = QualityChecker(mock_claude)
        result = checker.check(profile="x_post", content="テスト", max_retries=2)

        assert result["result"] == "escalated"

    def test_invalid_profile_raises_error(self):
        with patch("core.quality_checker.ClaudeClient"):
            with patch("core.quality_checker.Notifier"):
                checker = QualityChecker(MagicMock())
                with pytest.raises(ValueError, match="Unknown profile"):
                    checker.check(profile="invalid", content="test")


class TestQualityCheckerCheckWithRetry:
    """Test the check_with_retry method."""

    @patch("core.quality_checker.ClaudeClient")
    @patch("core.quality_checker.Notifier")
    def test_returns_on_first_approval(self, mock_notifier_cls, mock_claude_cls):
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_notifier_cls.return_value = MagicMock()

        mock_claude.generate_json.return_value = {
            "scores": {},
            "total_score": 90,
            "threshold": 80,
            "result": "auto_approved",
            "rejection_reasons": [],
            "improvement_suggestions": [],
        }

        checker = QualityChecker(mock_claude)
        content, result = checker.check_with_retry(
            profile="x_post", content="良いテスト"
        )

        assert result["result"] == "auto_approved"
        assert content == "良いテスト"
