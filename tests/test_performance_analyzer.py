"""Tests for system_a/analyze_performance.py."""

from unittest.mock import patch, MagicMock

import pytest

from system_a.analyze_performance import PerformanceAnalyzer


class TestPerformanceAnalyzer:
    """Test performance analysis and ratio adjustment."""

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
        assert "P1" in result
        assert "P2" in result
        assert "P3" in result
        assert result["P1"]["count"] == 2
        assert result["P2"]["avg_engagement_rate"] == 0.08

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
        assert 1 in result
        assert 3 in result
        assert result[1]["count"] == 2

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

        metrics = {"like_count": 0, "retweet_count": 0, "reply_count": 0, "impression_count": 0}
        rate = analyzer._calc_engagement_rate(metrics)
        assert rate == 0.0
