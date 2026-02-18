"""Tests for system_c modules."""

from pathlib import Path

import pytest
import yaml


class TestCrewConfig:
    """Test crew_config.yaml."""

    @pytest.fixture
    def config(self):
        config_path = Path(__file__).parent.parent / "system_c" / "crew_config.yaml"
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

    def test_tasks_defined(self, config):
        assert "tasks" in config
        expected_tasks = {
            "area_analysis", "daily_watch", "weekly_tech",
            "rental_valuation", "renovation_cost",
        }
        assert set(config["tasks"].keys()) == expected_tasks

    def test_no_banned_content(self, config):
        text = str(config).lower()
        assert "自動売買" not in text
        assert "xauusd" not in text


class TestDataSources:
    """Test data_sources.yaml."""

    @pytest.fixture
    def sources(self):
        path = Path(__file__).parent.parent / "system_c" / "data_sources.yaml"
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_has_sources(self, sources):
        assert "sources" in sources
        assert len(sources["sources"]) >= 4

    def test_mlit_api_configured(self, sources):
        assert "mlit_stats" in sources["sources"]
        assert "chika_kouji" in sources["sources"]

    def test_rate_limits_set(self, sources):
        for name, source in sources["sources"].items():
            if source["type"] == "web_scraper":
                assert "rate_limit" in source
