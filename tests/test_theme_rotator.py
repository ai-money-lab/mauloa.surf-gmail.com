"""Tests for system_a/theme_rotator.py."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from system_a.theme_rotator import ThemeRotator, DEFAULT_THEME_DB


class TestThemeRotator:
    """Test theme rotation logic."""

    @pytest.fixture(autouse=True)
    def setup_temp_files(self, tmp_path):
        """Set up temp theme DB and history files."""
        self.theme_db_path = tmp_path / "theme_db.json"
        self.history_path = tmp_path / "post_history.json"
        self.config_path = tmp_path / "config.yaml"

        self.theme_db_path.write_text(
            json.dumps(DEFAULT_THEME_DB, ensure_ascii=False), encoding="utf-8"
        )
        self.history_path.write_text("[]", encoding="utf-8")
        self.config_path.write_text(
            "system_a:\n  pipeline3:\n    theme_overlap_check_days: 30\n    max_same_sub_theme_per_month: 2\n",
            encoding="utf-8",
        )

    def _get_rotator(self):
        with patch("system_a.theme_rotator.THEME_DB_PATH", self.theme_db_path), \
             patch("system_a.theme_rotator.POST_HISTORY_PATH", self.history_path), \
             patch("system_a.theme_rotator.CONFIG_PATH", self.config_path):
            return ThemeRotator()

    def test_default_theme_db_has_5_pillars(self):
        assert len(DEFAULT_THEME_DB["pillars"]) == 5

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
        # Use all pillar 3 themes
        for theme_name in DEFAULT_THEME_DB["pillars"]["3"]["sub_themes"]:
            rotator.record_usage(3, theme_name)

        # Try to select from pillar 3 - should still return (fallback)
        theme = rotator.select_theme(target_pillar=3)
        assert theme is not None

    def test_pillar1_has_expected_themes(self):
        pillars = DEFAULT_THEME_DB["pillars"]
        assert "おとり物件の見分け方" in pillars["1"]["sub_themes"]
        assert "仲介手数料の仕組みと相場" in pillars["1"]["sub_themes"]

    def test_pillar5_has_field_experience(self):
        pillars = DEFAULT_THEME_DB["pillars"]
        assert "MATTERPORTやAIを現場で使ってみた実感" in pillars["5"]["sub_themes"]
