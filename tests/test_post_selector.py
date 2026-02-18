"""Tests for system_a/post_selector.py."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from system_a.post_selector import PostSelector, TARGET_PILLAR_RATIO


class TestPostSelector:
    """Test post selection logic."""

    def test_target_pillar_ratio_sums_to_one(self):
        total = sum(TARGET_PILLAR_RATIO.values())
        assert abs(total - 1.0) < 0.01

    def test_target_pillar_ratio_has_5_pillars(self):
        assert len(TARGET_PILLAR_RATIO) == 5

    @patch("system_a.post_selector.QualityChecker")
    @patch("system_a.post_selector.ClaudeClient")
    def test_extract_posts_from_patterns(self, mock_claude, mock_qc):
        selector = PostSelector()
        candidate = {
            "pattern_a": "テストA",
            "pattern_b": "テストB",
            "pattern_c": "テストC",
            "pipeline": "P1",
            "theme": {"pillar_number": 1},
        }
        posts = selector._extract_posts(candidate)
        assert len(posts) == 3

    @patch("system_a.post_selector.QualityChecker")
    @patch("system_a.post_selector.ClaudeClient")
    def test_extract_posts_fallback_to_text(self, mock_claude, mock_qc):
        selector = PostSelector()
        candidate = {
            "text": "直接テキスト",
            "pipeline": "P3",
            "theme": {"pillar_number": 2},
        }
        posts = selector._extract_posts(candidate)
        assert len(posts) == 1
        assert posts[0]["text"] == "直接テキスト"

    @patch("system_a.post_selector.QualityChecker")
    @patch("system_a.post_selector.ClaudeClient")
    def test_assign_time_slots(self, mock_claude, mock_qc):
        selector = PostSelector()
        posts = [{"text": "a"}, {"text": "b"}, {"text": "c"}]
        result = selector.assign_time_slots(posts)
        assert result[0]["scheduled_time"] == "07:00"
        assert result[1]["scheduled_time"] == "12:00"
        assert result[2]["scheduled_time"] == "19:00"

    @patch("system_a.post_selector.QualityChecker")
    @patch("system_a.post_selector.ClaudeClient")
    def test_select_with_pillar_balance_limits_to_3(self, mock_claude, mock_qc):
        selector = PostSelector()
        approved = [
            {"text": f"post{i}", "pillar": (i % 5) + 1, "quality_score": 90}
            for i in range(10)
        ]
        selected = selector.select_with_pillar_balance(approved)
        assert len(selected) == 3

    @patch("system_a.post_selector.QualityChecker")
    @patch("system_a.post_selector.ClaudeClient")
    def test_pipeline_ratio_config_loaded(self, mock_claude, mock_qc):
        selector = PostSelector()
        assert "P1" in selector.pipeline_ratio
        assert "P2" in selector.pipeline_ratio
        assert "P3" in selector.pipeline_ratio
        total = sum(selector.pipeline_ratio.values())
        assert abs(total - 1.0) < 0.01
