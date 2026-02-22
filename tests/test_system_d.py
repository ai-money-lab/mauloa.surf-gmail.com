"""Tests for System D modules — ResultsContentGenerator, ResultsPostScheduler.

Covers:
- ResultsContentGenerator: data loading, post generation, quality checking
- ResultsPostScheduler: config loading, scheduling, pipeline tagging
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ===========================================================================
# ResultsContentGenerator tests
# ===========================================================================

class TestResultsContentGenerator:
    """Test System D results content generation."""

    @patch("system_d.generate_results_content.QualityChecker")
    @patch("system_d.generate_results_content.ClaudeClient")
    def test_load_system_b_results_empty(self, mock_claude, mock_qc):
        from system_d.generate_results_content import ResultsContentGenerator
        gen = ResultsContentGenerator()
        results = gen._load_system_b_results()
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

    @patch("system_d.generate_results_content.QualityChecker")
    @patch("system_d.generate_results_content.ClaudeClient")
    def test_load_system_b_results_with_data(self, mock_claude_cls, mock_qc_cls,
                                               tmp_path):
        from system_d.generate_results_content import ResultsContentGenerator

        # Create fake deliverables
        with patch("system_d.generate_results_content.DATA_DIR", tmp_path):
            deliverables_dir = tmp_path / "system_b" / "deliverables" / "ORD-001"
            deliverables_dir.mkdir(parents=True)
            (deliverables_dir / "result.json").write_text(
                json.dumps({"status": "delivered"}), encoding="utf-8"
            )

            gen = ResultsContentGenerator()
            results = gen._load_system_b_results()

        assert len(results) == 1
        assert results[0]["type"] == "order_result"
        assert results[0]["order_id"] == "ORD-001"

    @patch("system_d.generate_results_content.QualityChecker")
    @patch("system_d.generate_results_content.ClaudeClient")
    def test_load_system_c_insights_with_data(self, mock_claude_cls, mock_qc_cls,
                                                tmp_path):
        from system_d.generate_results_content import ResultsContentGenerator

        with patch("system_d.generate_results_content.DATA_DIR", tmp_path):
            daily_dir = tmp_path / "system_c" / "daily"
            daily_dir.mkdir(parents=True)
            (daily_dir / "market_watch_2026-02-22.json").write_text(
                json.dumps({"type": "daily_market_watch"}), encoding="utf-8"
            )

            gen = ResultsContentGenerator()
            insights = gen._load_system_c_insights()

        assert len(insights) == 1
        assert insights[0]["type"] == "system_c_daily"

    @patch("system_d.generate_results_content.QualityChecker")
    @patch("system_d.generate_results_content.ClaudeClient")
    def test_generate_posts_quality_filters(self, mock_claude_cls, mock_qc_cls):
        """Only quality-approved posts should be returned."""
        from system_d.generate_results_content import ResultsContentGenerator

        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_claude.generate_json.return_value = {
            "text": "テスト実績投稿",
            "pipeline": "D",
        }

        mock_qc = MagicMock()
        mock_qc_cls.return_value = mock_qc
        # Reject all posts
        mock_qc.check.return_value = {"result": "rejected", "total_score": 50}

        gen = ResultsContentGenerator()
        gen._load_system_b_results = MagicMock(return_value=[])
        gen._load_system_c_insights = MagicMock(return_value=[])
        gen._load_system_a_performance = MagicMock(return_value=[])

        with patch("pathlib.Path.read_text", return_value="template content"):
            posts = gen.generate_posts()

        # All rejected, so no posts returned
        assert len(posts) == 0


# ===========================================================================
# ResultsPostScheduler tests
# ===========================================================================

class TestResultsPostScheduler:
    """Test System D post scheduler."""

    @patch("system_d.schedule_results_posts.ResultsContentGenerator")
    def test_config_defaults(self, mock_gen):
        from system_d.schedule_results_posts import ResultsPostScheduler
        scheduler = ResultsPostScheduler()
        assert scheduler.posts_per_week == 4
        assert scheduler.target_pillars == [3, 5]

    @patch("system_d.schedule_results_posts.ResultsContentGenerator")
    def test_generate_and_schedule_limits_posts(self, mock_gen_cls, tmp_path):
        from system_d.schedule_results_posts import ResultsPostScheduler

        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        mock_gen.run.return_value = [
            {"text": f"post{i}", "pipeline": "D"} for i in range(10)
        ]

        with patch("system_d.schedule_results_posts.BASE_DIR", tmp_path):
            scheduler = ResultsPostScheduler()
            scheduler.posts_per_week = 4
            selected = scheduler.generate_and_schedule()

        assert len(selected) <= 4

    @patch("system_d.schedule_results_posts.ResultsContentGenerator")
    def test_pipeline_tagged_as_d(self, mock_gen_cls, tmp_path):
        from system_d.schedule_results_posts import ResultsPostScheduler

        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        mock_gen.run.return_value = [{"text": "test", "pipeline": "P3"}]

        with patch("system_d.schedule_results_posts.BASE_DIR", tmp_path):
            scheduler = ResultsPostScheduler()
            selected = scheduler.generate_and_schedule()

        for post in selected:
            assert post["pipeline"] == "D"

    @patch("system_d.schedule_results_posts.ResultsContentGenerator")
    def test_appends_to_existing_pipeline3_data(self, mock_gen_cls, tmp_path):
        from system_d.schedule_results_posts import ResultsPostScheduler

        # Create existing pipeline3 data
        out_dir = tmp_path / "data" / "system_a" / "pipeline3" / "generated"
        out_dir.mkdir(parents=True)

        from datetime import datetime, timezone, timedelta
        JST = timezone(timedelta(hours=9))
        today = datetime.now(JST).strftime("%Y-%m-%d")
        existing_path = out_dir / f"{today}.json"
        existing_path.write_text(
            json.dumps([{"text": "existing", "pipeline": "P3"}]),
            encoding="utf-8",
        )

        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        mock_gen.run.return_value = [{"text": "new_d", "pipeline": "D"}]

        with patch("system_d.schedule_results_posts.BASE_DIR", tmp_path):
            scheduler = ResultsPostScheduler()
            scheduler.generate_and_schedule()

        saved = json.loads(existing_path.read_text(encoding="utf-8"))
        assert len(saved) == 2
        assert saved[0]["pipeline"] == "P3"
        assert saved[1]["pipeline"] == "D"

    @patch("system_d.schedule_results_posts.ResultsContentGenerator")
    def test_run_delegates_to_generate_and_schedule(self, mock_gen_cls, tmp_path):
        from system_d.schedule_results_posts import ResultsPostScheduler

        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        mock_gen.run.return_value = []

        with patch("system_d.schedule_results_posts.BASE_DIR", tmp_path):
            scheduler = ResultsPostScheduler()
            result = scheduler.run()

        assert isinstance(result, list)
