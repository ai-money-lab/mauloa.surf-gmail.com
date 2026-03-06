"""Tests for core/fact_checker.py — ensures banned content never passes."""

import pytest

from core.fact_checker import FactChecker


class TestBannedWords:
    """Critical: シミュレーション and variants must ALWAYS be rejected."""

    @pytest.fixture
    def checker(self):
        return FactChecker()

    def test_simulation_katakana_rejected(self, checker):
        result = checker.check("一度シミュレーションしてみると見え方が変わります")
        assert not result.passed
        assert any(v["code"] == "banned_word" for v in result.violations)

    def test_simulation_misspell_rejected(self, checker):
        result = checker.check("シュミレーションで確認してみましょう")
        assert not result.passed

    def test_simulator_rejected(self, checker):
        result = checker.check("うちのシミュレーターで計算できます")
        assert not result.passed

    def test_simulator_misspell_rejected(self, checker):
        result = checker.check("シュミレーターを使ってください")
        assert not result.passed

    def test_simulation_in_longer_text_rejected(self, checker):
        text = (
            "空室リスクを15%で固定計算している投資家を多く見かけますが、"
            "立地や築年数で5〜30%まで幅があります。"
            "一度シミュレーションしてみると見え方が変わりますよ。"
        )
        result = checker.check(text)
        assert not result.passed
        assert any("シミュレーション" in v["message"] for v in result.violations)

    def test_clean_post_passes(self, checker):
        result = checker.check("部屋探しで「ここだけは見ておいたほうがいい」ポイント、意外と知られてないんですよね")
        assert result.passed


class TestFabricationDetection:
    """Detect fabricated claims."""

    @pytest.fixture
    def checker(self):
        return FactChecker()

    def test_external_link_rejected(self, checker):
        result = checker.check("詳しくはhttps://example.comをご覧ください")
        assert not result.passed
        assert any(v["code"] == "external_link" for v in result.violations)

    def test_inflated_years_rejected(self, checker):
        result = checker.check("不動産業界で25年間の経験があります")
        assert not result.passed

    def test_inflated_case_count_rejected(self, checker):
        result = checker.check("これまで500件以上の物件を見てきました")
        assert not result.passed

    def test_direct_work_claim_rejected(self, checker):
        result = checker.check("自分で施工した物件は住み心地が違います")
        assert not result.passed

    def test_nonexistent_tool_rejected(self, checker):
        result = checker.check("うちのツールで簡単に計算できます")
        assert not result.passed


class TestAutoFix:
    """Test typo auto-correction."""

    @pytest.fixture
    def checker(self):
        return FactChecker()

    def test_fix_name_typo(self, checker):
        fixed = checker.auto_fix("鈴木佑介さんに教わった")
        assert "鈴木佑輔" in fixed

    def test_fix_company_name(self, checker):
        fixed = checker.auto_fix("ROCK EDGEの物件管理")
        assert "ROCKEDGE" in fixed

    def test_banned_word_not_auto_fixed(self, checker):
        """Banned words should NOT be auto-fixed — they must be rejected."""
        original = "シュミレーションしてみましょう"
        fixed = checker.auto_fix(original)
        # The banned misspelling should remain (not silently fixed)
        # because it needs to be caught by the violation check
        assert "シュミレーション" in fixed

    def test_auto_fix_list_input(self, checker):
        texts = ["ROCK EDGEの", "鈴木佑介さん"]
        fixed = checker.auto_fix(texts)
        assert isinstance(fixed, list)
        assert "ROCKEDGE" in fixed[0]
        assert "鈴木佑輔" in fixed[1]


class TestTypoDetection:
    """Test Japanese typo detection."""

    @pytest.fixture
    def checker(self):
        return FactChecker()

    def test_zutsu_typo_rejected(self, checker):
        result = checker.check("少しづつ良くなってきた")
        assert not result.passed
        assert any(v["code"] == "typo" for v in result.violations)

    def test_correct_zutsu_passes(self, checker):
        result = checker.check("少しずつ良くなってきた")
        # No typo violation for ずつ
        assert not any(v["code"] == "typo" for v in result.violations)


class TestHardNumbers:
    """Test hard number claim detection."""

    @pytest.fixture
    def checker(self):
        return FactChecker()

    def test_hard_number_without_softener(self, checker):
        result = checker.check("100万円損することもあります")
        assert not result.passed
        assert any(v["code"] == "hard_number_claim" for v in result.violations)

    def test_soft_number_passes(self, checker):
        result = checker.check("約100万円くらい変わることもあります")
        # "約" softener should make this pass
        assert not any(v["code"] == "hard_number_claim" for v in result.violations)


class TestThreadInput:
    """Test that thread (list) input works correctly."""

    @pytest.fixture
    def checker(self):
        return FactChecker()

    def test_thread_with_banned_word_rejected(self, checker):
        texts = [
            "空室リスクについて話します。",
            "一度シミュレーションしてみてください。",
        ]
        result = checker.check(texts)
        assert not result.passed
