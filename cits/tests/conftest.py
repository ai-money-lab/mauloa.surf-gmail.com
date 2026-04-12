"""Shared fixtures for the CITS test suite."""

import sys
from unittest.mock import MagicMock

import pytest

# The ``ta`` library requires C extensions that may not be available in CI.
# Inject a mock module so that ``cits.japan.data.yfinance_jp`` can import
# ``ta.trend``, ``ta.momentum``, ``ta.volatility`` without error.
if "ta" not in sys.modules:
    _ta = MagicMock()
    sys.modules["ta"] = _ta
    sys.modules["ta.trend"] = _ta.trend
    sys.modules["ta.momentum"] = _ta.momentum
    sys.modules["ta.volatility"] = _ta.volatility


@pytest.fixture(autouse=True)
def _set_api_keys(monkeypatch):
    """Ensure all API keys are set to safe test values for every test."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("JQUANTS_API_KEY", "test-jquants-key")
    monkeypatch.setenv("EDINET_API_KEY", "test-edinet-key")
    monkeypatch.setenv("KABU_API_PASSWORD", "test-kabu-pw")
    monkeypatch.setenv("KABU_ORDER_PASSWORD", "test-kabu-order-pw")


@pytest.fixture()
def sample_ticker_context():
    """Return a minimal ticker context dict used across pipeline stages."""
    return {
        "ticker": "7203",
        "date": "2026-03-22",
        "paper_mode": True,
        "config": {
            "llm_provider": "anthropic",
            "deep_think_llm": "claude-opus-4-6",
            "quick_think_llm": "claude-sonnet-4-20250514",
            "max_debate_rounds": 2,
            "paper_mode": True,
            "log_dir": "cits/logs",
            "analyst_temperature": 0.3,
            "debate_temperature": 0.4,
            "trader_temperature": 0.2,
        },
    }


@pytest.fixture()
def sample_analyst_reports():
    """Return mock Stage I analyst reports."""
    return {
        "fundamental": {"summary": "Strong earnings", "score": 7},
        "sentiment": {"summary": "Positive sentiment", "score": 6},
        "news": {"summary": "Positive news cycle", "score": 5},
        "technical": {"summary": "Bullish trend", "score": 8},
    }


@pytest.fixture()
def mock_llm_response():
    """Return a factory that creates a mock Anthropic message response."""

    def _make(text: str = '{"result": "ok"}'):
        msg = MagicMock()
        msg.content = [MagicMock(text=text)]
        return msg

    return _make


@pytest.fixture()
def mock_anthropic_client(mock_llm_response):
    """Return a mock Anthropic client whose messages.create returns a canned response."""
    client = MagicMock()
    client.messages.create.return_value = mock_llm_response()
    return client
