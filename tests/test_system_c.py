"""Tests for System C modules — Scheduler, Agents.

Covers:
- SystemCScheduler: task routing, agent initialization
- RealEstateDataAgent: initialization, rate_limit, data structures
- MarketAnalysisAgent: daily_market_watch, analyze_area_market
- RegulationWatchAgent: check_sources, analyze_impact
- TechTrendAgent: search_x_for_trends, generate_weekly_report
- EA/FX content filtering
"""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml


# ===========================================================================
# SystemCScheduler tests
# ===========================================================================

class TestSystemCScheduler:
    """Test scheduler task routing and initialization."""

    @patch("system_c.scheduler.TechTrendAgent")
    @patch("system_c.scheduler.RegulationWatchAgent")
    @patch("system_c.scheduler.MarketAnalysisAgent")
    @patch("system_c.scheduler.RealEstateDataAgent")
    @patch("system_c.scheduler.Notifier")
    def test_init_creates_all_agents(self, mock_notif, mock_re, mock_ma,
                                      mock_rw, mock_tt):
        from system_c.scheduler import SystemCScheduler
        scheduler = SystemCScheduler()
        assert scheduler.realestate_agent is not None
        assert scheduler.market_agent is not None
        assert scheduler.regulation_agent is not None
        assert scheduler.tech_agent is not None

    @patch("system_c.scheduler.TechTrendAgent")
    @patch("system_c.scheduler.RegulationWatchAgent")
    @patch("system_c.scheduler.MarketAnalysisAgent")
    @patch("system_c.scheduler.RealEstateDataAgent")
    @patch("system_c.scheduler.Notifier")
    def test_run_task_daily_watch(self, mock_notif, mock_re, mock_ma,
                                   mock_rw, mock_tt):
        from system_c.scheduler import SystemCScheduler
        scheduler = SystemCScheduler()
        scheduler.run_daily_watch = MagicMock()
        scheduler.run_task("daily_watch")
        scheduler.run_daily_watch.assert_called_once()

    @patch("system_c.scheduler.TechTrendAgent")
    @patch("system_c.scheduler.RegulationWatchAgent")
    @patch("system_c.scheduler.MarketAnalysisAgent")
    @patch("system_c.scheduler.RealEstateDataAgent")
    @patch("system_c.scheduler.Notifier")
    def test_run_task_weekly_tech(self, mock_notif, mock_re, mock_ma,
                                   mock_rw, mock_tt):
        from system_c.scheduler import SystemCScheduler
        scheduler = SystemCScheduler()
        scheduler.run_weekly_tech = MagicMock()
        scheduler.run_task("weekly_tech")
        scheduler.run_weekly_tech.assert_called_once()

    @patch("system_c.scheduler.TechTrendAgent")
    @patch("system_c.scheduler.RegulationWatchAgent")
    @patch("system_c.scheduler.MarketAnalysisAgent")
    @patch("system_c.scheduler.RealEstateDataAgent")
    @patch("system_c.scheduler.Notifier")
    def test_run_task_unknown_does_not_raise(self, mock_notif, mock_re,
                                              mock_ma, mock_rw, mock_tt):
        from system_c.scheduler import SystemCScheduler
        scheduler = SystemCScheduler()
        # Should not raise, just log error
        scheduler.run_task("nonexistent_task")

    @patch("system_c.scheduler.TechTrendAgent")
    @patch("system_c.scheduler.RegulationWatchAgent")
    @patch("system_c.scheduler.MarketAnalysisAgent")
    @patch("system_c.scheduler.RealEstateDataAgent")
    @patch("system_c.scheduler.Notifier")
    def test_run_daily_watch_calls_agents(self, mock_notif, mock_re,
                                           mock_ma, mock_rw, mock_tt):
        from system_c.scheduler import SystemCScheduler
        scheduler = SystemCScheduler()
        scheduler.run_daily_watch()
        scheduler.market_agent.daily_market_watch.assert_called_once()
        scheduler.regulation_agent.run_daily.assert_called_once()

    @patch("system_c.scheduler.TechTrendAgent")
    @patch("system_c.scheduler.RegulationWatchAgent")
    @patch("system_c.scheduler.MarketAnalysisAgent")
    @patch("system_c.scheduler.RealEstateDataAgent")
    @patch("system_c.scheduler.Notifier")
    def test_run_daily_watch_sends_notification(self, mock_notif, mock_re,
                                                  mock_ma, mock_rw, mock_tt):
        from system_c.scheduler import SystemCScheduler
        scheduler = SystemCScheduler()
        scheduler.run_daily_watch()
        scheduler.notifier.send_line.assert_called_once()


# ===========================================================================
# RealEstateDataAgent tests
# ===========================================================================

class TestRealEstateDataAgent:
    """Test real estate data collection agent."""

    @patch("system_c.agents.realestate_data_agent.QualityChecker")
    @patch("system_c.agents.realestate_data_agent.ClaudeClient")
    def test_init_sets_rate_limit(self, mock_claude, mock_qc):
        from system_c.agents.realestate_data_agent import RealEstateDataAgent
        agent = RealEstateDataAgent()
        assert agent.rate_limit == 0.5

    @patch("system_c.agents.realestate_data_agent.QualityChecker")
    @patch("system_c.agents.realestate_data_agent.ClaudeClient")
    def test_init_sets_user_agent(self, mock_claude, mock_qc):
        from system_c.agents.realestate_data_agent import RealEstateDataAgent
        agent = RealEstateDataAgent()
        assert "HIROKI" in agent.user_agent

    @patch("system_c.agents.realestate_data_agent.requests.get")
    @patch("system_c.agents.realestate_data_agent.QualityChecker")
    @patch("system_c.agents.realestate_data_agent.ClaudeClient")
    def test_fetch_land_prices_returns_dict(self, mock_claude, mock_qc, mock_get):
        from system_c.agents.realestate_data_agent import RealEstateDataAgent

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": [{"price": 100000}]}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        agent = RealEstateDataAgent()
        agent.rate_limit = 0  # speed up test
        result = agent.fetch_land_prices("港区")

        assert result["source"] == "mlit_land_prices"
        assert result["area"] == "港区"
        assert "records" in result

    @patch("system_c.agents.realestate_data_agent.requests.get")
    @patch("system_c.agents.realestate_data_agent.QualityChecker")
    @patch("system_c.agents.realestate_data_agent.ClaudeClient")
    def test_fetch_land_prices_handles_error(self, mock_claude, mock_qc, mock_get):
        from system_c.agents.realestate_data_agent import RealEstateDataAgent
        mock_get.side_effect = Exception("Network error")

        agent = RealEstateDataAgent()
        agent.rate_limit = 0
        result = agent.fetch_land_prices("渋谷区")

        assert "error" in result

    @patch("system_c.agents.realestate_data_agent.QualityChecker")
    @patch("system_c.agents.realestate_data_agent.ClaudeClient")
    def test_fetch_population_data_without_key(self, mock_claude, mock_qc):
        from system_c.agents.realestate_data_agent import RealEstateDataAgent
        with patch.dict("os.environ", {"ESTAT_API_KEY": ""}):
            agent = RealEstateDataAgent()
            result = agent.fetch_population_data("13101")
            assert result["error"] == "API key not configured"


# ===========================================================================
# MarketAnalysisAgent tests
# ===========================================================================

class TestMarketAnalysisAgent:
    """Test market analysis agent."""

    @patch("system_c.agents.market_analysis_agent.QualityChecker")
    @patch("system_c.agents.market_analysis_agent.ClaudeClient")
    def test_daily_market_watch_returns_dict(self, mock_claude_cls, mock_qc_cls):
        from system_c.agents.market_analysis_agent import MarketAnalysisAgent

        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_claude.generate_json.return_value = {"interest_rates": "stable"}

        mock_qc = MagicMock()
        mock_qc_cls.return_value = mock_qc
        mock_qc.check.return_value = {"result": "auto_approved", "total_score": 80}

        with patch("system_c.agents.market_analysis_agent.DATA_DIR", MagicMock()):
            with patch("pathlib.Path.mkdir"):
                with patch("pathlib.Path.write_text"):
                    agent = MarketAnalysisAgent()
                    result = agent.daily_market_watch()

        assert result["type"] == "daily_market_watch"
        assert "data" in result
        assert "quality_check" in result

    @patch("system_c.agents.market_analysis_agent.QualityChecker")
    @patch("system_c.agents.market_analysis_agent.ClaudeClient")
    def test_analyze_area_market_returns_analysis(self, mock_claude_cls, mock_qc_cls):
        from system_c.agents.market_analysis_agent import MarketAnalysisAgent

        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_claude.generate_json.return_value = {
            "market_overview": "test",
            "price_trend": "upward",
        }

        agent = MarketAnalysisAgent()
        result = agent.analyze_area_market("港区", {"price": 100})

        assert result["area"] == "港区"
        assert "analysis" in result

    @patch("system_c.agents.market_analysis_agent.QualityChecker")
    @patch("system_c.agents.market_analysis_agent.ClaudeClient")
    def test_analyze_area_market_handles_error(self, mock_claude_cls, mock_qc_cls):
        from system_c.agents.market_analysis_agent import MarketAnalysisAgent

        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_claude.generate_json.side_effect = Exception("API error")

        agent = MarketAnalysisAgent()
        result = agent.analyze_area_market("港区", {})

        assert "error" in result


# ===========================================================================
# RegulationWatchAgent tests
# ===========================================================================

class TestRegulationWatchAgent:
    """Test regulation watch agent."""

    @patch("system_c.agents.regulation_watch_agent.ClaudeClient")
    def test_analyze_impact_empty_findings(self, mock_claude):
        from system_c.agents.regulation_watch_agent import RegulationWatchAgent
        agent = RegulationWatchAgent()
        result = agent.analyze_impact([])
        assert result["findings"] == []
        assert "No notable changes" in result["analysis"]

    @patch("system_c.agents.regulation_watch_agent.ClaudeClient")
    def test_analyze_impact_with_findings(self, mock_claude_cls):
        from system_c.agents.regulation_watch_agent import RegulationWatchAgent

        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_claude.generate_json.return_value = {
            "items": [{"impact_level": "high"}],
        }

        agent = RegulationWatchAgent()
        findings = [{"title": "新法規制", "source": "国交省"}]
        result = agent.analyze_impact(findings)

        assert len(result["findings"]) == 1
        assert "analysis" in result
        assert "checked_at" in result

    @patch("system_c.agents.regulation_watch_agent.requests.get")
    @patch("system_c.agents.regulation_watch_agent.ClaudeClient")
    def test_fetch_handles_network_error(self, mock_claude, mock_get):
        from system_c.agents.regulation_watch_agent import RegulationWatchAgent
        mock_get.side_effect = Exception("Connection refused")

        agent = RegulationWatchAgent()
        result = agent._fetch("https://example.com")
        assert result == ""


# ===========================================================================
# TechTrendAgent tests
# ===========================================================================

class TestTechTrendAgent:
    """Test tech trend scouting agent."""

    @patch("system_c.agents.tech_trend_agent.QualityChecker")
    @patch("system_c.agents.tech_trend_agent.ClaudeClient")
    def test_search_x_without_api_key_returns_empty(self, mock_claude, mock_qc):
        from system_c.agents.tech_trend_agent import TechTrendAgent
        with patch.dict("os.environ", {"TWITTERAPI_IO_KEY": ""}):
            agent = TechTrendAgent()
            agent.twitter_api_key = ""
            result = agent.search_x_for_trends()
            assert result == []

    @patch("system_c.agents.tech_trend_agent.QualityChecker")
    @patch("system_c.agents.tech_trend_agent.ClaudeClient")
    def test_generate_weekly_report_structure(self, mock_claude_cls, mock_qc_cls):
        from system_c.agents.tech_trend_agent import TechTrendAgent

        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_claude.generate_json.return_value = {
            "trends": [{"title": "PropTech"}],
            "key_insight": "test",
        }

        mock_qc = MagicMock()
        mock_qc_cls.return_value = mock_qc
        mock_qc.check.return_value = {"result": "auto_approved", "total_score": 80}

        with patch("pathlib.Path.mkdir"), patch("pathlib.Path.write_text"):
            agent = TechTrendAgent()
            result = agent.generate_weekly_report(raw_data=[])

        assert result["type"] == "weekly_tech_trends"
        assert "report" in result
        assert "quality_check" in result

    @patch("system_c.agents.tech_trend_agent.QualityChecker")
    @patch("system_c.agents.tech_trend_agent.ClaudeClient")
    def test_generate_weekly_report_counts_raw_data(self, mock_claude_cls, mock_qc_cls):
        from system_c.agents.tech_trend_agent import TechTrendAgent

        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_claude.generate_json.return_value = {"trends": []}

        mock_qc = MagicMock()
        mock_qc_cls.return_value = mock_qc
        mock_qc.check.return_value = {"result": "auto_approved", "total_score": 80}

        raw = [{"text": "a"}, {"text": "b"}]
        with patch("pathlib.Path.mkdir"), patch("pathlib.Path.write_text"):
            agent = TechTrendAgent()
            result = agent.generate_weekly_report(raw_data=raw)

        assert result["raw_data_count"] == 2


# ===========================================================================
# Crew config tests
# ===========================================================================

class TestCrewConfig:
    """Test crew_config.yaml if it exists."""

    @pytest.fixture
    def config(self):
        config_path = Path(__file__).parent.parent / "system_c" / "crew_config.yaml"
        if not config_path.exists():
            pytest.skip("crew_config.yaml not found")
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_has_4_agents(self, config):
        assert len(config["agents"]) == 4

    def test_agent_names(self, config):
        names = {a["name"] for a in config["agents"]}
        expected = {
            "realestate_data_agent",
            "market_analysis_agent",
            "regulation_watch_agent",
            "tech_trend_agent",
        }
        assert names == expected

    def test_all_agents_have_required_fields(self, config):
        required = ["name", "role", "goal", "backstory", "tools"]
        for agent in config["agents"]:
            for field in required:
                assert field in agent, f"Agent {agent['name']} missing {field}"

    def test_no_banned_content_in_config(self, config):
        text = str(config).lower()
        assert "自動売買" not in text
        assert "xauusd" not in text
