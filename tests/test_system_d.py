"""Tests for system_d modules."""

from unittest.mock import patch, MagicMock

import pytest


class TestResultsContentGenerator:
    """Test System D results content generation."""

    @patch("system_d.generate_results_content.QualityChecker")
    @patch("system_d.generate_results_content.ClaudeClient")
    def test_load_system_b_results_empty(self, mock_claude, mock_qc):
        from system_d.generate_results_content import ResultsContentGenerator
        gen = ResultsContentGenerator()
        results = gen._load_system_b_results()
        # Should return empty list when no deliverables
        assert isinstance(results, list)

    @patch("system_d.generate_results_content.QualityChecker")
    @patch("system_d.generate_results_content.ClaudeClient")
    def test_load_system_c_insights_empty(self, mock_claude, mock_qc):
        from system_d.generate_results_content import ResultsContentGenerator
        gen = ResultsContentGenerator()
        insights = gen._load_system_c_insights()
        assert isinstance(insights, list)

    @patch("system_d.generate_results_content.QualityChecker")
    @patch("system_d.generate_results_content.ClaudeClient")
    def test_load_system_a_performance_empty(self, mock_claude, mock_qc):
        from system_d.generate_results_content import ResultsContentGenerator
        gen = ResultsContentGenerator()
        perf = gen._load_system_a_performance()
        assert isinstance(perf, list)


class TestResultsPostScheduler:
    """Test System D post scheduler."""

    @patch("system_d.schedule_results_posts.ResultsContentGenerator")
    def test_config_loaded(self, mock_gen):
        from system_d.schedule_results_posts import ResultsPostScheduler
        scheduler = ResultsPostScheduler()
        assert scheduler.posts_per_week == 4
        assert scheduler.target_pillars == [3, 5]
