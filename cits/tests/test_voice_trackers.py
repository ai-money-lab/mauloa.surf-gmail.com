"""Tests for voice tracker modules: fomc_scorer, boj_scorer, trump_tracker."""

import json
from unittest.mock import MagicMock, patch

from cits.japan.voice_tracker.fomc_scorer import FOMCScorer
from cits.japan.voice_tracker.boj_scorer import BOJScorer
from cits.japan.voice_tracker.trump_tracker import TrumpTracker


# ===== FOMCScorer =====

def test_fomc_keyword_score_hawkish():
    """_keyword_score detects hawkish keywords."""
    with patch("cits.japan.voice_tracker.fomc_scorer.anthropic.Anthropic"):
        scorer = FOMCScorer()
    raw, hawks, doves = scorer._keyword_score(
        "Inflation remains elevated and the labor market is overheating."
    )
    assert raw > 0
    assert "inflation" in hawks
    assert "overheating" in hawks


def test_fomc_keyword_score_dovish():
    """_keyword_score detects dovish keywords."""
    with patch("cits.japan.voice_tracker.fomc_scorer.anthropic.Anthropic"):
        scorer = FOMCScorer()
    raw, hawks, doves = scorer._keyword_score(
        "The committee will be patient as disinflation progresses. Downside risks remain."
    )
    assert raw < 0
    assert "patient" in doves
    assert "disinflation" in doves


def test_fomc_score_statement_hawkish():
    """score_statement returns positive hawk_dove_score for hawkish text."""
    with patch("cits.japan.voice_tracker.fomc_scorer.anthropic.Anthropic"):
        scorer = FOMCScorer()
    # Disable semantic scoring
    scorer.client = None
    result = scorer.score_statement(
        "Inflation is too high. Further increases may be needed. Higher for longer."
    )
    assert result["hawk_dove_score"] > 0
    assert result["rate_direction_signal"] == "hike"


def test_fomc_score_statement_dovish():
    """score_statement returns negative score for dovish text."""
    with patch("cits.japan.voice_tracker.fomc_scorer.anthropic.Anthropic"):
        scorer = FOMCScorer()
    scorer.client = None
    result = scorer.score_statement(
        "The committee sees balanced risks and progress on inflation. "
        "We remain data dependent with patient easing ahead. Rate cut likely."
    )
    assert result["hawk_dove_score"] < 0
    assert result["rate_direction_signal"] == "cut"


def test_fomc_score_statement_with_semantic(mock_llm_response):
    """score_statement uses semantic scoring when available."""
    with patch("cits.japan.voice_tracker.fomc_scorer.anthropic.Anthropic"):
        scorer = FOMCScorer()
    scorer.client = MagicMock()
    semantic_json = json.dumps({
        "hawk_dove_score": 8,
        "key_phrases": ["inflation persistent"],
        "rate_direction_signal": "hike",
    })
    scorer.client.messages.create.return_value = mock_llm_response(semantic_json)

    result = scorer.score_statement("Some text about inflation")
    assert result["hawk_dove_score"] == 8
    assert result["rate_direction_signal"] == "hike"


def test_fomc_diff_statements():
    """diff_statements detects shift from dovish to hawkish."""
    with patch("cits.japan.voice_tracker.fomc_scorer.anthropic.Anthropic"):
        scorer = FOMCScorer()
    scorer.client = None
    result = scorer.diff_statements(
        current="Inflation is too high. Tightening needed.",
        previous="The economy shows balanced risks. Patient approach."
    )
    assert result["change_score"] > 0
    assert any("hawkish" in p.lower() or "Added" in p for p in result["changed_phrases"])


def test_fomc_score_speech():
    """score_speech includes the speaker name in result."""
    with patch("cits.japan.voice_tracker.fomc_scorer.anthropic.Anthropic"):
        scorer = FOMCScorer()
    scorer.client = None
    result = scorer.score_speech("Powell", "We see inflation as too high.")
    assert result["speaker"] == "Powell"
    assert "hawk_dove_score" in result


# ===== BOJScorer =====

def test_boj_keyword_score_tightening():
    """_keyword_score detects tightening keywords in Japanese."""
    with patch("cits.japan.voice_tracker.boj_scorer.anthropic.Anthropic"):
        scorer = BOJScorer()
    raw, tights, eases = scorer._keyword_score(
        "物価安定の目標に向けて正常化を進める。賃金上昇が続く。"
    )
    assert raw > 0
    assert "物価安定" in tights


def test_boj_keyword_score_easing():
    """_keyword_score detects easing keywords."""
    with patch("cits.japan.voice_tracker.boj_scorer.anthropic.Anthropic"):
        scorer = BOJScorer()
    raw, tights, eases = scorer._keyword_score(
        "粘り強く金融緩和を続ける。下振れリスクに注意。時期尚早。"
    )
    assert raw < 0
    assert "粘り強く" in eases


def test_boj_score_mpm_decision_tightening():
    """score_mpm_decision returns positive score for tightening language."""
    with patch("cits.japan.voice_tracker.boj_scorer.anthropic.Anthropic"):
        scorer = BOJScorer()
    scorer.client = None
    result = scorer.score_mpm_decision(
        "利上げを決定。物価安定に向け正常化を推進。賃金上昇が確認された。出口戦略を議論。"
    )
    assert result["policy_score"] > 0
    assert result["rate_decision"] == "hike"


def test_boj_score_mpm_ycc_modification():
    """score_mpm_decision detects YCC modification (case-sensitive Japanese)."""
    with patch("cits.japan.voice_tracker.boj_scorer.anthropic.Anthropic"):
        scorer = BOJScorer()
    scorer.client = None
    # Source code checks for lowercase "ycc修正" in text and "YCC修正" in original text
    # The keyword list contains "YCC修正" which matches via _keyword_score
    result = scorer.score_mpm_decision("ycc修正を実施。ycc adjustment announced.")
    assert result["ycc_status"] == "modified"


def test_boj_diff_statements():
    """diff_mpm_statements detects policy shift."""
    with patch("cits.japan.voice_tracker.boj_scorer.anthropic.Anthropic"):
        scorer = BOJScorer()
    scorer.client = None
    result = scorer.diff_mpm_statements(
        current="正常化を進める。利上げの可能性。",
        previous="粘り強く緩和継続。時期尚早。"
    )
    assert result["change_score"] > 0


def test_boj_score_governor_speech_fallback():
    """score_governor_speech falls back to keyword scoring when semantic fails."""
    with patch("cits.japan.voice_tracker.boj_scorer.anthropic.Anthropic"):
        scorer = BOJScorer()
    scorer.client = None
    result = scorer.score_governor_speech("物価安定に向け正常化を進める")
    assert "policy_score" in result
    assert "key_phrases" in result


# ===== TrumpTracker =====

def test_trump_detect_categories_tariff():
    """_detect_categories picks up tariff keywords."""
    with patch("cits.japan.voice_tracker.trump_tracker.anthropic.Anthropic"):
        tracker = TrumpTracker()
    matched = tracker._detect_categories(
        "We will impose a 25% tariff on all imports. Trade war is easy to win."
    )
    assert "tariff" in matched
    assert "tariff" in matched["tariff"]


def test_trump_score_statement_negative():
    """score_statement returns negative market impact for tariff threats."""
    with patch("cits.japan.voice_tracker.trump_tracker.anthropic.Anthropic"):
        tracker = TrumpTracker()
    tracker.client = None
    result = tracker.score_statement(
        "We are imposing a massive tariff on China. Trade war! "
        "Anti-dumping duties and reciprocal tariffs on all imports."
    )
    assert result["market_impact_score"] < 0
    assert "tariff" in result["categories"]


def test_trump_score_statement_positive():
    """score_statement returns positive for trade deal / fiscal news."""
    with patch("cits.japan.voice_tracker.trump_tracker.anthropic.Anthropic"):
        tracker = TrumpTracker()
    tracker.client = None
    result = tracker.score_statement(
        "We reached a tremendous trade deal and agreement. "
        "Big tax cuts and infrastructure spending coming. Stimulus plan."
    )
    assert result["market_impact_score"] > 0


def test_trump_detect_tariff_threat_with_country():
    """detect_tariff_threat identifies target countries."""
    with patch("cits.japan.voice_tracker.trump_tracker.anthropic.Anthropic"):
        tracker = TrumpTracker()
    tracker.client = None
    result = tracker.detect_tariff_threat(
        "We will impose tariffs on China and Japan for unfair trade practices."
    )
    assert "China" in result["target_countries"]
    assert "Japan" in result["target_countries"]
    assert result["severity"] != "none"


def test_trump_detect_tariff_threat_none():
    """detect_tariff_threat returns none severity when no tariff keywords."""
    with patch("cits.japan.voice_tracker.trump_tracker.anthropic.Anthropic"):
        tracker = TrumpTracker()
    tracker.client = None
    result = tracker.detect_tariff_threat("The weather is nice today.")
    assert result["severity"] == "none"
    assert result["target_countries"] == []


def test_trump_pattern_escalation():
    """get_pattern_analysis detects escalation pattern."""
    with patch("cits.japan.voice_tracker.trump_tracker.anthropic.Anthropic"):
        tracker = TrumpTracker()
    tracker.client = None
    result = tracker.get_pattern_analysis("I have signed an order effective immediately.")
    assert result["pattern"] == "escalation"


def test_trump_pattern_negotiation():
    """get_pattern_analysis detects negotiation pattern."""
    with patch("cits.japan.voice_tracker.trump_tracker.anthropic.Anthropic"):
        tracker = TrumpTracker()
    tracker.client = None
    result = tracker.get_pattern_analysis("We are in talks for a great deal.")
    assert result["pattern"] == "negotiation"


def test_trump_urgency_high():
    """score_statement returns high urgency for multi-category statements."""
    with patch("cits.japan.voice_tracker.trump_tracker.anthropic.Anthropic"):
        tracker = TrumpTracker()
    tracker.client = None
    result = tracker.score_statement(
        "Tariff on China! The Fed should cut interest rates. "
        "Big tax cuts and trade deal coming. Powell is wrong."
    )
    assert result["urgency_level"] == "high"
    assert len(result["categories"]) >= 3
