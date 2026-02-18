"""Tests for configuration files."""

import json
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).parent.parent


class TestConfigYaml:
    """Test config/config.yaml."""

    @pytest.fixture
    def config(self):
        with open(PROJECT_ROOT / "config" / "config.yaml", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_timezone_is_tokyo(self, config):
        assert config["general"]["timezone"] == "Asia/Tokyo"

    def test_language_is_japanese(self, config):
        assert config["general"]["language"] == "ja"

    def test_quality_thresholds(self, config):
        thresholds = config["quality_checker"]["thresholds"]
        assert thresholds["x_post"] == 84
        assert thresholds["report"] == 75
        assert thresholds["data_collection"] == 70

    def test_system_a_posts_per_day(self, config):
        assert config["system_a"]["posts_per_day"] == 3

    def test_system_a_post_times(self, config):
        times = config["system_a"]["post_times"]
        assert times == ["07:00", "12:00", "19:00"]

    def test_pipeline_ratios_sum_to_100(self, config):
        ratio = config["system_a"]["pipeline_ratio"]
        total = sum(ratio.values())
        assert total == 100

    def test_pipeline_ratio_limits(self, config):
        limits = config["system_a"]["pipeline_ratio_limits"]
        assert limits["min_per_pipeline"] == 15
        assert limits["max_per_pipeline"] == 60

    def test_system_d_config(self, config):
        assert config["system_d"]["results_posts_per_week"] == 4
        assert config["system_d"]["target_pillars"] == [3, 5]

    def test_no_banned_content(self, config):
        text = str(config).lower()
        assert "自動売買" not in text
        assert "xauusd" not in text
        assert "fx" not in text.split()


class TestEnvExample:
    """Test .env.example has all required variables."""

    @pytest.fixture
    def env_content(self):
        return (PROJECT_ROOT / "config" / ".env.example").read_text(encoding="utf-8")

    def test_has_x_api_keys(self, env_content):
        assert "X_API_KEY=" in env_content
        assert "X_BEARER_TOKEN=" in env_content

    def test_has_anthropic_key(self, env_content):
        assert "ANTHROPIC_API_KEY=" in env_content

    def test_has_google_sheets(self, env_content):
        assert "SHEETS_POST_MANAGEMENT_ID=" in env_content

    def test_has_line_notify(self, env_content):
        assert "LINE_NOTIFY_TOKEN=" in env_content

    def test_no_actual_keys(self, env_content):
        """Ensure no actual API keys are committed."""
        lines = env_content.strip().split("\n")
        for line in lines:
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                # Value should be empty or a path placeholder
                assert value == "" or value.startswith("./"), \
                    f"Possible leaked key in {key}"


class TestGitignore:
    """Test .gitignore."""

    @pytest.fixture
    def gitignore(self):
        return (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    def test_env_excluded(self, gitignore):
        assert ".env" in gitignore

    def test_credentials_excluded(self, gitignore):
        assert "credentials.json" in gitignore

    def test_data_excluded(self, gitignore):
        assert "data/" in gitignore

    def test_pycache_excluded(self, gitignore):
        assert "__pycache__" in gitignore


class TestPromptFiles:
    """Test all prompt files exist and don't contain banned content."""

    PROMPT_FILES = [
        "quality_check.txt",
        "analyze_jp_buzz.txt",
        "rewrite_jp_buzz.txt",
        "data_to_post.txt",
        "ai_original.txt",
        "generate_report.txt",
        "professional_insight.txt",
        "results_to_post.txt",
    ]

    @pytest.mark.parametrize("prompt_file", PROMPT_FILES)
    def test_prompt_file_exists(self, prompt_file):
        path = PROJECT_ROOT / "prompts" / prompt_file
        assert path.exists(), f"Missing prompt file: {prompt_file}"

    @pytest.mark.parametrize("prompt_file", PROMPT_FILES)
    def test_prompt_no_banned_content(self, prompt_file):
        path = PROJECT_ROOT / "prompts" / prompt_file
        content = path.read_text(encoding="utf-8").lower()
        # Check specific banned patterns
        assert "xauusd" not in content
        # "EA" check should be context-aware (skip if in normal words)


class TestThemeDB:
    """Test theme database."""

    @pytest.fixture
    def theme_db(self):
        path = PROJECT_ROOT / "data" / "system_a" / "theme_db.json"
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_has_5_pillars(self, theme_db):
        assert len(theme_db["pillars"]) == 5

    def test_each_pillar_has_themes(self, theme_db):
        for p_num, p_data in theme_db["pillars"].items():
            assert len(p_data["sub_themes"]) >= 5, \
                f"Pillar {p_num} has too few themes"

    def test_each_pillar_has_name(self, theme_db):
        for p_num, p_data in theme_db["pillars"].items():
            assert "name" in p_data
            assert len(p_data["name"]) > 0
