"""Tests for System A components.

Covers:
- ThemeRotator: theme DB, select_theme, record_usage, dedup
- PostSelector: pillar balance, extract_posts, time slots, pipeline ratio
- Pipeline classes: initialization, run signatures
- PerformanceAnalyzer: analyze_by_pipeline/pillar/pattern, engagement rate
- DailyPipeline: orchestration
"""

import json
from unittest.mock import patch

import pytest

from system_a.theme_rotator import ThemeRotator, DEFAULT_THEME_DB
from system_a.post_selector import PostSelector, TARGET_PILLAR_RATIO
from system_a.analyze_performance import PerformanceAnalyzer


# ===========================================================================
# ThemeRotator tests
# ===========================================================================

class TestThemeRotatorConfig:
    """Test the default theme DB configuration."""

    def test_default_theme_db_has_5_pillars(self):
        assert len(DEFAULT_THEME_DB["pillars"]) == 5

    def test_pillar1_has_expected_themes(self):
        pillars = DEFAULT_THEME_DB["pillars"]
        assert "相続した不動産、まず何をすべきか" in pillars["1"]["sub_themes"]
        assert "売却の流れと一般的なスケジュール" in pillars["1"]["sub_themes"]

    def test_pillar5_has_field_experience(self):
        pillars = DEFAULT_THEME_DB["pillars"]
        assert "MATTERPORTやAIを現場で使ってみた実感" in pillars["5"]["sub_themes"]

    def test_all_pillars_have_name_and_sub_themes(self):
        for num, data in DEFAULT_THEME_DB["pillars"].items():
            assert "name" in data
            assert "sub_themes" in data
            assert len(data["sub_themes"]) > 0

    def test_no_ea_fx_content_in_theme_db(self):
        """Theme DB must not contain EA/FX trading content."""
        text = json.dumps(DEFAULT_THEME_DB, ensure_ascii=False).lower()
        assert "自動売買" not in text
        assert "xauusd" not in text


class TestThemeRotator:
    """Test theme rotation logic."""

    @pytest.fixture(autouse=True)
    def setup_temp_files(self, tmp_path):
        self.theme_db_path = tmp_path / "theme_db.json"
        self.history_path = tmp_path / "post_history.json"
        self.config_path = tmp_path / "config.yaml"

        self.theme_db_path.write_text(
            json.dumps(DEFAULT_THEME_DB, ensure_ascii=False), encoding="utf-8"
        )
        self.history_path.write_text("[]", encoding="utf-8")
        self.config_path.write_text(
            "system_a:\n  pipeline3:\n    theme_overlap_check_days: 30\n"
            "    max_same_sub_theme_per_month: 2\n",
            encoding="utf-8",
        )

    def _get_rotator(self):
        with patch("system_a.theme_rotator.THEME_DB_PATH", self.theme_db_path), \
             patch("system_a.theme_rotator.POST_HISTORY_PATH", self.history_path), \
             patch("system_a.theme_rotator.CONFIG_PATH", self.config_path):
            return ThemeRotator()

    def test_select_theme_returns_dict(self):
        rotator = self._get_rotator()
        theme = rotator.select_theme()
        assert theme is not None
        assert "pillar_number" in theme
        assert "pillar_name" in theme
        assert "sub_theme" in theme

    def test_select_theme_with_target_pillar(self):
        rotator = self._get_rotator()
        theme = rotator.select_theme(target_pillar=3)
        assert theme["pillar_number"] == 3

    def test_record_usage_adds_to_history(self):
        rotator = self._get_rotator()
        initial_count = len(rotator.post_history)
        rotator.record_usage(1, "仲介手数料の仕組み")
        assert len(rotator.post_history) == initial_count + 1

    def test_get_recent_themes_empty_initially(self):
        rotator = self._get_rotator()
        recent = rotator.get_recent_themes()
        assert len(recent) == 0

    def test_used_theme_excluded_from_selection(self):
        rotator = self._get_rotator()
        for theme_name in DEFAULT_THEME_DB["pillars"]["3"]["sub_themes"]:
            rotator.record_usage(3, theme_name)

        # Try to select from pillar 3 - should still return (fallback)
        theme = rotator.select_theme(target_pillar=3)
        assert theme is not None

    def test_config_defaults_on_missing_file(self, tmp_path):
        """When config file is missing, defaults should be used."""
        with patch("system_a.theme_rotator.THEME_DB_PATH", self.theme_db_path), \
             patch("system_a.theme_rotator.POST_HISTORY_PATH", self.history_path), \
             patch("system_a.theme_rotator.CONFIG_PATH", tmp_path / "nonexistent.yaml"):
            rotator = ThemeRotator()
            assert rotator.overlap_check_days == 30
            assert rotator.max_same_per_month == 2


# ===========================================================================
# PostSelector tests
# ===========================================================================

class TestPostSelectorConfig:
    """Test PostSelector configuration and constants."""

    def test_target_pillar_ratio_sums_to_one(self):
        total = sum(TARGET_PILLAR_RATIO.values())
        assert abs(total - 1.0) < 0.01

    def test_target_pillar_ratio_has_5_pillars(self):
        assert len(TARGET_PILLAR_RATIO) == 5

    def test_pillar1_has_highest_ratio(self):
        assert TARGET_PILLAR_RATIO[1] == 0.30
        assert TARGET_PILLAR_RATIO[1] == max(TARGET_PILLAR_RATIO.values())


class TestPostSelector:
    """Test post selection logic."""

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
    def test_extract_posts_with_abc_keys(self, mock_claude, mock_qc):
        """Test extraction when patterns use A/B/C keys."""
        selector = PostSelector()
        candidate = {
            "A": {"text": "TextA"},
            "B": {"text": "TextB"},
            "pipeline": "P1",
            "theme": {"pillar_number": 1},
        }
        posts = selector._extract_posts(candidate)
        assert len(posts) == 2

    @patch("system_a.post_selector.QualityChecker")
    @patch("system_a.post_selector.ClaudeClient")
    def test_assign_time_slots(self, mock_claude, mock_qc):
        selector = PostSelector()
        posts = [{"text": "a"}]
        result = selector.assign_time_slots(posts)
        assert result[0]["scheduled_time"] == "19:00"

    @patch("system_a.post_selector.QualityChecker")
    @patch("system_a.post_selector.ClaudeClient")
    def test_assign_time_slots_excess_uses_last_time(self, mock_claude, mock_qc):
        selector = PostSelector()
        posts = [{"text": str(i)} for i in range(5)]
        result = selector.assign_time_slots(posts)
        # All should use "19:00" since there's only one time slot
        assert result[3]["scheduled_time"] == "19:00"
        assert result[4]["scheduled_time"] == "19:00"

    @patch("system_a.post_selector.QualityChecker")
    @patch("system_a.post_selector.ClaudeClient")
    def test_select_with_pillar_balance_limits_to_posts_per_day(self, mock_claude, mock_qc):
        selector = PostSelector()
        approved = [
            {"text": f"post{i}", "pillar": (i % 5) + 1, "quality_score": 90}
            for i in range(10)
        ]
        selected = selector.select_with_pillar_balance(approved)
        assert len(selected) == selector.posts_per_day

    @patch("system_a.post_selector.QualityChecker")
    @patch("system_a.post_selector.ClaudeClient")
    def test_select_returns_all_if_fewer_than_limit(self, mock_claude, mock_qc):
        selector = PostSelector()
        approved = [{"text": "a", "pillar": 1, "quality_score": 90}]
        selected = selector.select_with_pillar_balance(approved)
        assert len(selected) == 1

    @patch("system_a.post_selector.QualityChecker")
    @patch("system_a.post_selector.ClaudeClient")
    def test_pipeline_ratio_config_loaded(self, mock_claude, mock_qc):
        selector = PostSelector()
        assert "P1" in selector.pipeline_ratio
        assert "P2" in selector.pipeline_ratio
        assert "P3" in selector.pipeline_ratio
        total = sum(selector.pipeline_ratio.values())
        assert abs(total - 1.0) < 0.01


# ===========================================================================
# PerformanceAnalyzer tests
# ===========================================================================

class TestPerformanceAnalyzer:
    """Test performance analysis and metrics."""

    @patch("system_a.analyze_performance.yaml")
    def test_analyze_by_pipeline(self, mock_yaml):
        mock_yaml.safe_load.return_value = {"system_a": {"pipeline_ratio_limits": {}}}
        analyzer = PerformanceAnalyzer()

        posts = [
            {"pipeline": "P1", "engagement_rate": 0.05},
            {"pipeline": "P1", "engagement_rate": 0.03},
            {"pipeline": "P2", "engagement_rate": 0.08},
            {"pipeline": "P3", "engagement_rate": 0.02},
        ]

        result = analyzer.analyze_by_pipeline(posts)
        assert result["P1"]["count"] == 2
        assert result["P2"]["avg_engagement_rate"] == 0.08
        assert result["P2"]["max_engagement_rate"] == 0.08

    @patch("system_a.analyze_performance.yaml")
    def test_analyze_by_pillar(self, mock_yaml):
        mock_yaml.safe_load.return_value = {"system_a": {"pipeline_ratio_limits": {}}}
        analyzer = PerformanceAnalyzer()

        posts = [
            {"pillar": 1, "engagement_rate": 0.05},
            {"pillar": 1, "engagement_rate": 0.03},
            {"pillar": 3, "engagement_rate": 0.08},
        ]

        result = analyzer.analyze_by_pillar(posts)
        assert result[1]["count"] == 2
        assert result[3]["count"] == 1
        assert result[1]["avg_engagement_rate"] == 0.04

    @patch("system_a.analyze_performance.yaml")
    def test_analyze_by_pattern(self, mock_yaml):
        mock_yaml.safe_load.return_value = {"system_a": {"pipeline_ratio_limits": {}}}
        analyzer = PerformanceAnalyzer()

        posts = [
            {"pattern": "A", "engagement_rate": 0.05},
            {"pattern": "B", "engagement_rate": 0.08},
            {"pattern": "C", "engagement_rate": 0.03},
        ]

        result = analyzer.analyze_by_pattern(posts)
        assert "A" in result
        assert "B" in result
        assert "C" in result

    @patch("system_a.analyze_performance.yaml")
    def test_calc_engagement_rate(self, mock_yaml):
        mock_yaml.safe_load.return_value = {"system_a": {"pipeline_ratio_limits": {}}}
        analyzer = PerformanceAnalyzer()

        metrics = {
            "like_count": 100,
            "retweet_count": 50,
            "reply_count": 25,
            "impression_count": 10000,
        }
        rate = analyzer._calc_engagement_rate(metrics)
        assert rate == 0.0175

    @patch("system_a.analyze_performance.yaml")
    def test_calc_engagement_rate_zero_impressions(self, mock_yaml):
        mock_yaml.safe_load.return_value = {"system_a": {"pipeline_ratio_limits": {}}}
        analyzer = PerformanceAnalyzer()

        metrics = {
            "like_count": 0, "retweet_count": 0,
            "reply_count": 0, "impression_count": 0,
        }
        rate = analyzer._calc_engagement_rate(metrics)
        assert rate == 0.0

    @patch("system_a.analyze_performance.yaml")
    def test_update_winning_patterns_filters_by_threshold(self, mock_yaml, tmp_path):
        mock_yaml.safe_load.return_value = {"system_a": {"pipeline_ratio_limits": {}}}

        with patch("system_a.analyze_performance.WINNING_PATTERNS_PATH",
                   tmp_path / "winning.json"):
            analyzer = PerformanceAnalyzer()
            posts = [
                {"pipeline": "P1", "pillar": 1, "pattern": "A",
                 "engagement_rate": 0.10, "text": "winning post"},
                {"pipeline": "P2", "pillar": 2, "pattern": "B",
                 "engagement_rate": 0.01, "text": "losing post"},
            ]
            analyzer.update_winning_patterns(posts)

            data = json.loads(
                (tmp_path / "winning.json").read_text(encoding="utf-8")
            )
            # Only post with ER > 0.05 should be saved
            assert len(data) == 1
            assert data[0]["pipeline"] == "P1"


# ===========================================================================
# Pipeline initialization tests
# ===========================================================================

class TestPipelineInitialization:
    """Test that pipeline classes can be instantiated with mocked deps."""

    @patch("system_a.pipeline1_jp_buzz.QualityChecker")
    @patch("system_a.pipeline1_jp_buzz.ClaudeClient")
    def test_pipeline1_init(self, mock_claude, mock_qc):
        from system_a.pipeline1_jp_buzz import Pipeline1JpBuzz
        p1 = Pipeline1JpBuzz()
        assert p1.min_likes == 10000
        assert p1.lookback_hours == 72
        assert p1.max_results == 30

    @patch("system_a.pipeline2_data_driven.JpTrendsCollector")
    @patch("system_a.pipeline2_data_driven.QualityChecker")
    @patch("system_a.pipeline2_data_driven.ClaudeClient")
    def test_pipeline2_init(self, mock_claude, mock_qc, mock_trends):
        from system_a.pipeline2_data_driven import Pipeline2DataDriven
        p2 = Pipeline2DataDriven()
        assert p2.claude is not None

    @patch("system_a.pipeline3_ai_original.ThemeRotator")
    @patch("system_a.pipeline3_ai_original.QualityChecker")
    @patch("system_a.pipeline3_ai_original.ClaudeClient")
    def test_pipeline3_init(self, mock_claude, mock_qc, mock_rotator):
        from system_a.pipeline3_ai_original import Pipeline3AIOriginal
        p3 = Pipeline3AIOriginal()
        assert p3.claude is not None


# ===========================================================================
# DailyPipeline tests
# ===========================================================================

class TestDailyPipeline:
    """Test DailyPipeline orchestration."""

    @patch("system_a.daily_pipeline.Notifier")
    @patch("system_a.daily_pipeline.AutoPoster")
    @patch("system_a.daily_pipeline.PostSelector")
    @patch("system_a.daily_pipeline.Pipeline3AIOriginal")
    @patch("system_a.daily_pipeline.Pipeline2DataDriven")
    @patch("system_a.daily_pipeline.Pipeline1JpBuzz")
    def test_run_generation_returns_counts(self, mock_p1, mock_p2, mock_p3,
                                            mock_sel, mock_poster, mock_notif):
        from system_a.daily_pipeline import DailyPipeline

        mock_p1.return_value.run.return_value = [{"text": "a"}] * 3
        mock_p2.return_value.run.return_value = [{"text": "b"}] * 2
        mock_p3.return_value.run.return_value = [{"text": "c"}] * 1

        dp = DailyPipeline()
        results = dp.run_generation()

        assert results["P1"] == 3
        assert results["P2"] == 2
        assert results["P3"] == 1

    @patch("system_a.daily_pipeline.Notifier")
    @patch("system_a.daily_pipeline.AutoPoster")
    @patch("system_a.daily_pipeline.PostSelector")
    @patch("system_a.daily_pipeline.Pipeline3AIOriginal")
    @patch("system_a.daily_pipeline.Pipeline2DataDriven")
    @patch("system_a.daily_pipeline.Pipeline1JpBuzz")
    def test_run_generation_handles_pipeline_failure(self, mock_p1, mock_p2, mock_p3,
                                                      mock_sel, mock_poster, mock_notif):
        from system_a.daily_pipeline import DailyPipeline

        mock_p1.return_value.run.side_effect = Exception("P1 crash")
        mock_p2.return_value.run.return_value = [{"text": "b"}]
        mock_p3.return_value.run.return_value = [{"text": "c"}]

        dp = DailyPipeline()
        results = dp.run_generation()

        assert results["P1"] == 0  # Failed pipeline returns 0
        assert results["P2"] == 1
        assert results["P3"] == 1
