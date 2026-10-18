"""Tests for system_a/theme_rotator.py."""

import json

import pytest

from system_a.theme_rotator import ThemeRotator, DEFAULT_THEME_DB


class TestThemeRotator:
    """Test theme rotation logic."""

    @pytest.fixture(autouse=True)
    def setup_temp_files(self, tmp_path, monkeypatch):
        """Point the module paths at temp files for the whole test.

        monkeypatch is required here, not a `with patch(...)` block inside a
        helper: ThemeRotator writes on every record_usage() call, so a patch
        that expires when the helper returns lets those writes land on the
        real data/system_a/*.json and truncate production history.
        """
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

        monkeypatch.setattr("system_a.theme_rotator.THEME_DB_PATH", self.theme_db_path)
        monkeypatch.setattr("system_a.theme_rotator.POST_HISTORY_PATH", self.history_path)
        monkeypatch.setattr("system_a.theme_rotator.CONFIG_PATH", self.config_path)

    def _get_rotator(self):
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
        assert "相続した不動産、まず何をすべきか" in pillars["1"]["sub_themes"]
        assert "売却の流れと一般的なスケジュール" in pillars["1"]["sub_themes"]

    def test_pillar5_has_field_experience(self):
        pillars = DEFAULT_THEME_DB["pillars"]
        assert "MATTERPORTやAIを現場で使ってみた実感" in pillars["5"]["sub_themes"]

    def test_record_usage_writes_only_to_patched_path(self):
        """record_usage must write to the patched temp file, never to data/.

        Regression guard: running the suite once truncated the real
        data/system_a/post_history.json because the path patch expired
        before record_usage() ran.
        """
        from system_a import theme_rotator

        rotator = self._get_rotator()
        rotator.record_usage(1, "仲介手数料の仕組み")

        assert theme_rotator.POST_HISTORY_PATH == self.history_path
        written = json.loads(self.history_path.read_text(encoding="utf-8"))
        assert any(r["sub_theme"] == "仲介手数料の仕組み" for r in written)
