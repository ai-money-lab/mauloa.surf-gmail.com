"""Tests for core/claude_client.py — ClaudeClient class.

Covers:
- generate(): text responses, system prompts, parameters
- generate_json(): JSON parsing, code fence stripping
- Error handling
- Default and custom model names
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from core.claude_client import ClaudeClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_anthropic():
    """Patch Anthropic and yield (client_instance, mock_anthropic_cls)."""
    with patch("core.claude_client.Anthropic") as mock_cls:
        mock_inner = MagicMock()
        mock_cls.return_value = mock_inner
        yield mock_inner, mock_cls


def _make_response(text):
    """Helper: build a mock Anthropic response with the given text."""
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    return resp


# ---------------------------------------------------------------------------
# generate() tests
# ---------------------------------------------------------------------------

class TestGenerate:
    """Test ClaudeClient.generate()."""

    def test_returns_text(self, mock_anthropic):
        mock_inner, _ = mock_anthropic
        mock_inner.messages.create.return_value = _make_response("Hello World")

        client = ClaudeClient()
        result = client.generate("test prompt")

        assert result == "Hello World"
        mock_inner.messages.create.assert_called_once()

    def test_passes_system_prompt_when_provided(self, mock_anthropic):
        mock_inner, _ = mock_anthropic
        mock_inner.messages.create.return_value = _make_response("response")

        client = ClaudeClient()
        client.generate("test", system="system prompt")

        call_kwargs = mock_inner.messages.create.call_args[1]
        assert call_kwargs["system"] == "system prompt"

    def test_does_not_pass_system_when_empty(self, mock_anthropic):
        mock_inner, _ = mock_anthropic
        mock_inner.messages.create.return_value = _make_response("response")

        client = ClaudeClient()
        client.generate("test", system="")

        call_kwargs = mock_inner.messages.create.call_args[1]
        assert "system" not in call_kwargs

    def test_uses_specified_max_tokens(self, mock_anthropic):
        mock_inner, _ = mock_anthropic
        mock_inner.messages.create.return_value = _make_response("r")

        client = ClaudeClient()
        client.generate("test", max_tokens=1024)

        call_kwargs = mock_inner.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 1024

    def test_uses_specified_temperature(self, mock_anthropic):
        mock_inner, _ = mock_anthropic
        mock_inner.messages.create.return_value = _make_response("r")

        client = ClaudeClient()
        client.generate("test", temperature=0.2)

        call_kwargs = mock_inner.messages.create.call_args[1]
        assert call_kwargs["temperature"] == 0.2

    def test_raises_on_api_error(self, mock_anthropic):
        mock_inner, _ = mock_anthropic
        mock_inner.messages.create.side_effect = Exception("API down")

        client = ClaudeClient()
        with pytest.raises(Exception, match="API down"):
            client.generate("test")


# ---------------------------------------------------------------------------
# generate_json() tests
# ---------------------------------------------------------------------------

class TestGenerateJson:
    """Test ClaudeClient.generate_json()."""

    def test_parses_plain_json(self, mock_anthropic):
        mock_inner, _ = mock_anthropic
        mock_inner.messages.create.return_value = _make_response('{"key": "value"}')

        client = ClaudeClient()
        result = client.generate_json("test")

        assert result == {"key": "value"}

    def test_strips_json_code_fence(self, mock_anthropic):
        mock_inner, _ = mock_anthropic
        mock_inner.messages.create.return_value = _make_response(
            '```json\n{"key": "value"}\n```'
        )

        client = ClaudeClient()
        result = client.generate_json("test")

        assert result == {"key": "value"}

    def test_strips_plain_code_fence(self, mock_anthropic):
        mock_inner, _ = mock_anthropic
        mock_inner.messages.create.return_value = _make_response(
            '```\n{"key": "value"}\n```'
        )

        client = ClaudeClient()
        result = client.generate_json("test")

        assert result == {"key": "value"}

    def test_raises_on_invalid_json(self, mock_anthropic):
        mock_inner, _ = mock_anthropic
        mock_inner.messages.create.return_value = _make_response("not json at all")

        client = ClaudeClient()
        with pytest.raises(json.JSONDecodeError):
            client.generate_json("test")

    def test_default_temperature_for_json_is_0_3(self, mock_anthropic):
        mock_inner, _ = mock_anthropic
        mock_inner.messages.create.return_value = _make_response('{"a": 1}')

        client = ClaudeClient()
        client.generate_json("test")

        call_kwargs = mock_inner.messages.create.call_args[1]
        assert call_kwargs["temperature"] == 0.3

    def test_parses_nested_json(self, mock_anthropic):
        mock_inner, _ = mock_anthropic
        data = {"scores": {"hook_power": 9, "originality": 8}, "total": 85}
        mock_inner.messages.create.return_value = _make_response(json.dumps(data))

        client = ClaudeClient()
        result = client.generate_json("test")
        assert result["scores"]["hook_power"] == 9


# ---------------------------------------------------------------------------
# Model configuration tests
# ---------------------------------------------------------------------------

class TestModelConfig:
    """Test model name configuration."""

    def test_default_model(self, mock_anthropic):
        client = ClaudeClient()
        assert client.model == "claude-sonnet-4-5-20250929"

    def test_custom_model(self, mock_anthropic):
        client = ClaudeClient(model="claude-opus-4-20250514")
        assert client.model == "claude-opus-4-20250514"

    def test_model_passed_to_api_call(self, mock_anthropic):
        mock_inner, _ = mock_anthropic
        mock_inner.messages.create.return_value = _make_response("text")

        client = ClaudeClient(model="claude-haiku-4-20250514")
        client.generate("test")

        call_kwargs = mock_inner.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-haiku-4-20250514"
