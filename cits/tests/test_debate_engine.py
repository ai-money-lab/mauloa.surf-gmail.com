"""Tests for the DebateEngine."""

import json
from unittest.mock import MagicMock, patch

from cits.core.debate.debate_engine import DebateEngine


def _make_judge_json(winner="bull", score=5):
    """Return a valid judge JSON string."""
    return json.dumps({
        "round_winner": winner,
        "round_score": score,
        "bull_strengths": ["strong earnings"],
        "bear_strengths": ["high valuation"],
        "key_insight": "Earnings momentum favours bulls.",
    })


# ----- Tests -----

def test_init_defaults():
    """DebateEngine initialises with correct defaults."""
    with patch("cits.core.debate.debate_engine.anthropic.Anthropic"):
        engine = DebateEngine()
        assert engine.max_rounds == 2
        assert engine.MODEL == "claude-opus-4-6"


def test_init_custom_rounds():
    """DebateEngine accepts custom max_rounds."""
    with patch("cits.core.debate.debate_engine.anthropic.Anthropic"):
        engine = DebateEngine(max_rounds=5)
        assert engine.max_rounds == 5


def test_parse_json_valid():
    """_parse_json handles clean JSON."""
    with patch("cits.core.debate.debate_engine.anthropic.Anthropic"):
        engine = DebateEngine()
        result = engine._parse_json('{"round_winner": "bull", "round_score": 3}')
        assert result["round_winner"] == "bull"
        assert result["round_score"] == 3


def test_parse_json_with_fences():
    """_parse_json strips markdown code fences."""
    with patch("cits.core.debate.debate_engine.anthropic.Anthropic"):
        engine = DebateEngine()
        raw = '```json\n{"round_winner": "bear", "round_score": -2}\n```'
        result = engine._parse_json(raw)
        assert result["round_winner"] == "bear"


def test_parse_json_invalid_returns_tie():
    """_parse_json returns a tie dict when JSON is malformed."""
    with patch("cits.core.debate.debate_engine.anthropic.Anthropic"):
        engine = DebateEngine()
        result = engine._parse_json("this is not json at all")
        assert result["round_winner"] == "tie"
        assert result["round_score"] == 0
        assert result.get("parse_error") is True


def test_run_debate_bull_wins():
    """run_debate returns bull winner when scores are positive."""
    with patch("cits.core.debate.debate_engine.anthropic.Anthropic"):
        engine = DebateEngine(max_rounds=2)
        # Mock _call_llm: bull rebuttal, bear rebuttal, judge (x2 rounds)
        engine._call_llm = MagicMock(side_effect=[
            "Bull rebuttal round 1",
            "Bear rebuttal round 1",
            _make_judge_json("bull", 5),
            "Bull rebuttal round 2",
            "Bear rebuttal round 2",
            _make_judge_json("bull", 4),
        ])

        result = engine.run_debate(
            bull_case={"summary": "Strong growth"},
            bear_case={"summary": "Overvalued"},
            analyst_reports={"fundamental": {"score": 7}},
        )

        assert result["winner"] == "bull"
        assert result["final_score"] == 9  # 5+4, clamped to 10 max
        assert len(result["debate_transcript"]) == 2


def test_run_debate_bear_wins():
    """run_debate returns bear winner when scores are negative."""
    with patch("cits.core.debate.debate_engine.anthropic.Anthropic"):
        engine = DebateEngine(max_rounds=2)
        engine._call_llm = MagicMock(side_effect=[
            "Bull rebuttal round 1",
            "Bear rebuttal round 1",
            _make_judge_json("bear", -6),
            "Bull rebuttal round 2",
            "Bear rebuttal round 2",
            _make_judge_json("bear", -5),
        ])

        result = engine.run_debate(
            bull_case={"summary": "Growth"},
            bear_case={"summary": "Recession risk"},
            analyst_reports={},
        )

        assert result["winner"] == "bear"
        assert result["final_score"] == -10  # -11 clamped to -10


def test_run_debate_neutral():
    """run_debate returns neutral when avg score is within [-2, 2]."""
    with patch("cits.core.debate.debate_engine.anthropic.Anthropic"):
        engine = DebateEngine(max_rounds=2)
        engine._call_llm = MagicMock(side_effect=[
            "Bull rebuttal", "Bear rebuttal",
            _make_judge_json("tie", 1),
            "Bull rebuttal", "Bear rebuttal",
            _make_judge_json("tie", -1),
        ])

        result = engine.run_debate(
            bull_case={}, bear_case={}, analyst_reports={},
        )

        assert result["winner"] == "neutral"
        assert result["final_score"] == 0


def test_run_debate_consensus_view():
    """run_debate builds a human-readable consensus_view string."""
    with patch("cits.core.debate.debate_engine.anthropic.Anthropic"):
        engine = DebateEngine(max_rounds=1)
        engine._call_llm = MagicMock(side_effect=[
            "Bull rebuttal", "Bear rebuttal",
            _make_judge_json("bull", 7),
        ])

        result = engine.run_debate(
            bull_case={}, bear_case={}, analyst_reports={},
        )

        assert "bullish" in result["consensus_view"]
        assert "strong earnings" in result["consensus_view"]


def test_run_debate_collects_strengths():
    """run_debate accumulates bull and bear strengths across rounds."""
    with patch("cits.core.debate.debate_engine.anthropic.Anthropic"):
        engine = DebateEngine(max_rounds=2)
        engine._call_llm = MagicMock(side_effect=[
            "Bull 1", "Bear 1",
            _make_judge_json("bull", 3),
            "Bull 2", "Bear 2",
            _make_judge_json("bull", 2),
        ])

        result = engine.run_debate(bull_case={}, bear_case={}, analyst_reports={})

        assert len(result["key_points_bull"]) == 2  # one per round
        assert len(result["key_points_bear"]) == 2
