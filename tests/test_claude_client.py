"""Tests for core/claude_client.py."""

import json
from unittest.mock import patch, MagicMock

import pytest

from core.claude_client import ClaudeClient


class TestClaudeClient:
    """Test ClaudeClient wrapper."""

    @patch("core.claude_client.Anthropic")
    def test_generate_returns_text(self, mock_anthropic):
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello World")]
        mock_client.messages.create.return_value = mock_response

        client = ClaudeClient()
        result = client.generate("test prompt")

        assert result == "Hello World"
        mock_client.messages.create.assert_called_once()

    @patch("core.claude_client.Anthropic")
    def test_generate_json_parses_response(self, mock_anthropic):
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"key": "value"}')]
        mock_client.messages.create.return_value = mock_response

        client = ClaudeClient()
        result = client.generate_json("test prompt")

        assert result == {"key": "value"}

    @patch("core.claude_client.Anthropic")
    def test_generate_json_strips_code_fences(self, mock_anthropic):
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='```json\n{"key": "value"}\n```')]
        mock_client.messages.create.return_value = mock_response

        client = ClaudeClient()
        result = client.generate_json("test prompt")

        assert result == {"key": "value"}

    @patch("core.claude_client.Anthropic")
    def test_generate_with_system_prompt(self, mock_anthropic):
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="response")]
        mock_client.messages.create.return_value = mock_response

        client = ClaudeClient()
        client.generate("test", system="system prompt")

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["system"] == "system prompt"

    @patch("core.claude_client.Anthropic")
    def test_default_model(self, mock_anthropic):
        mock_anthropic.return_value = MagicMock()
        client = ClaudeClient()
        assert client.model == "claude-sonnet-4-20250514"

    @patch("core.claude_client.Anthropic")
    def test_custom_model(self, mock_anthropic):
        mock_anthropic.return_value = MagicMock()
        client = ClaudeClient(model="claude-opus-4-20250514")
        assert client.model == "claude-opus-4-20250514"

    @patch("core.claude_client.Anthropic")
    def test_generate_json_invalid_json_raises(self, mock_anthropic):
        """generate_json returns invalid JSON — should raise JSONDecodeError."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="not valid json at all")]
        mock_client.messages.create.return_value = mock_response

        client = ClaudeClient()
        with pytest.raises(json.JSONDecodeError):
            client.generate_json("test prompt")

    @patch("core.claude_client.Anthropic")
    def test_generate_api_error_propagates(self, mock_anthropic):
        """API error should propagate, not be swallowed."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = RuntimeError("API down")

        client = ClaudeClient()
        with pytest.raises(RuntimeError, match="API down"):
            client.generate("test")

    @patch("core.claude_client.Anthropic")
    def test_generate_without_system_prompt(self, mock_anthropic):
        """Empty system prompt should not be sent to API."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="response")]
        mock_client.messages.create.return_value = mock_response

        client = ClaudeClient()
        client.generate("test", system="")

        call_kwargs = mock_client.messages.create.call_args[1]
        assert "system" not in call_kwargs

    @patch("core.claude_client.Anthropic")
    def test_generate_respects_temperature(self, mock_anthropic):
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]
        mock_client.messages.create.return_value = mock_response

        client = ClaudeClient()
        client.generate("test", temperature=0.1)

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["temperature"] == 0.1

    @patch("core.claude_client.Anthropic")
    def test_generate_respects_max_tokens(self, mock_anthropic):
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]
        mock_client.messages.create.return_value = mock_response

        client = ClaudeClient()
        client.generate("test", max_tokens=2048)

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 2048
