"""Tests for core/claude_client.py."""

from unittest.mock import patch, MagicMock


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
