"""Tests for core/claude_client.py — ClaudeClient class.

Covers:
- generate(): text responses, system prompts, parameters
- generate_json(): JSON parsing, code fence stripping
- Error handling
- Default and custom model names
"""

import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from core.claude_client import (
    ClaudeClient,
    DEFAULT_CLI_SYSTEM_PROMPT,
    _extract_json_text,
    api_billing_disabled,
    model_accepts_sampling_params,
)


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

    def test_temperature_goes_through_extra_body(self, mock_anthropic):
        """anthropic 1.x rejects a `temperature` keyword with a TypeError."""
        mock_inner, _ = mock_anthropic
        mock_inner.messages.create.return_value = _make_response("r")

        client = ClaudeClient()
        client.generate("test", temperature=0.2)

        call_kwargs = mock_inner.messages.create.call_args[1]
        assert "temperature" not in call_kwargs
        assert call_kwargs["extra_body"] == {"temperature": 0.2}

    def test_temperature_dropped_for_models_that_reject_it(self, mock_anthropic):
        """Opus 4.7+ returns 400 for any temperature, default included."""
        mock_inner, _ = mock_anthropic
        mock_inner.messages.create.return_value = _make_response("r")

        client = ClaudeClient(model="claude-opus-4-7")
        client.generate("test", temperature=0.2)

        call_kwargs = mock_inner.messages.create.call_args[1]
        assert "temperature" not in call_kwargs
        assert "extra_body" not in call_kwargs

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
        assert call_kwargs["extra_body"] == {"temperature": 0.3}

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


# ---------------------------------------------------------------------------
# Backend selection (ANTHROPIC_DISABLED -> `claude -p`, never silent billing)
# ---------------------------------------------------------------------------

class TestBackendSelection:
    """Test which backend ClaudeClient routes through."""

    def test_sdk_backend_by_default(self, mock_anthropic):
        assert ClaudeClient().backend == "sdk"

    def test_disabled_without_cli_raises(self, monkeypatch, mock_anthropic):
        """Never fall back to the billed API when billing is disabled."""
        _, mock_cls = mock_anthropic
        monkeypatch.setenv("ANTHROPIC_DISABLED", "1")
        monkeypatch.setattr("core.claude_client.shutil.which", lambda _: None)

        with pytest.raises(RuntimeError, match="claude` CLI was not found"):
            ClaudeClient()
        mock_cls.assert_not_called()

    def test_disabled_routes_to_cli(self, monkeypatch, mock_anthropic):
        mock_inner, mock_cls = mock_anthropic
        monkeypatch.setenv("ANTHROPIC_DISABLED", "1")
        monkeypatch.setattr(
            "core.claude_client.shutil.which", lambda _: "/usr/bin/claude"
        )
        completed = MagicMock(returncode=0, stdout="cli answer\n", stderr="")
        run = MagicMock(return_value=completed)
        monkeypatch.setattr("core.claude_client.subprocess.run", run)

        client = ClaudeClient()
        assert client.backend == "cli"
        assert client.generate("test prompt") == "cli answer"

        mock_cls.assert_not_called()
        mock_inner.messages.create.assert_not_called()
        argv = run.call_args[0][0]
        assert argv[:3] == ["/usr/bin/claude", "-p", "test prompt"]
        # claude -p must be stripped down to a text-generation endpoint
        for flag in ("--strict-mcp-config", "--restricted", "--tools"):
            assert flag in argv
        assert argv[argv.index("--tools") + 1] == ""
        assert argv[argv.index("--system-prompt") + 1] == DEFAULT_CLI_SYSTEM_PROMPT
        # stdin must be closed or the CLI waits 3s for piped input each call
        assert run.call_args[1]["stdin"] is subprocess.DEVNULL

    def test_cli_system_prompt_is_passed(self, monkeypatch, mock_anthropic):
        monkeypatch.setenv("ANTHROPIC_DISABLED", "1")
        monkeypatch.setattr(
            "core.claude_client.shutil.which", lambda _: "/usr/bin/claude"
        )
        completed = MagicMock(returncode=0, stdout="ok", stderr="")
        run = MagicMock(return_value=completed)
        monkeypatch.setattr("core.claude_client.subprocess.run", run)

        ClaudeClient().generate("p", system="be terse")

        argv = run.call_args[0][0]
        assert argv[argv.index("--system-prompt") + 1] == "be terse"

    def test_cli_nonzero_exit_raises(self, monkeypatch, mock_anthropic):
        monkeypatch.setenv("ANTHROPIC_DISABLED", "1")
        monkeypatch.setattr(
            "core.claude_client.shutil.which", lambda _: "/usr/bin/claude"
        )
        completed = MagicMock(returncode=2, stdout="", stderr="boom")
        monkeypatch.setattr(
            "core.claude_client.subprocess.run", MagicMock(return_value=completed)
        )

        with pytest.raises(RuntimeError, match="exited 2"):
            ClaudeClient().generate("p")

    def test_cli_empty_output_raises(self, monkeypatch, mock_anthropic):
        monkeypatch.setenv("ANTHROPIC_DISABLED", "1")
        monkeypatch.setattr(
            "core.claude_client.shutil.which", lambda _: "/usr/bin/claude"
        )
        completed = MagicMock(returncode=0, stdout="   ", stderr="")
        monkeypatch.setattr(
            "core.claude_client.subprocess.run", MagicMock(return_value=completed)
        )

        with pytest.raises(RuntimeError, match="empty output"):
            ClaudeClient().generate("p")

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
    def test_truthy_values_disable_billing(self, value, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_DISABLED", value)
        assert api_billing_disabled() is True

    @pytest.mark.parametrize("value", ["", "0", "false", "no"])
    def test_other_values_leave_billing_enabled(self, value, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_DISABLED", value)
        assert api_billing_disabled() is False


class TestSamplingParamSupport:
    """Test the model accept-list for temperature/top_p/top_k."""

    @pytest.mark.parametrize("model", [
        "claude-sonnet-4-5-20250929",
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
        "claude-haiku-4-5",
        "claude-sonnet-4-6",
    ])
    def test_accepted(self, model):
        assert model_accepts_sampling_params(model) is True

    @pytest.mark.parametrize("model", [
        "claude-opus-4-7",
        "claude-opus-4-8",
        "claude-opus-5",
        "claude-sonnet-5",
        "claude-fable-5-1",
    ])
    def test_rejected(self, model):
        assert model_accepts_sampling_params(model) is False


# ---------------------------------------------------------------------------
# JSON extraction from messy model output
# ---------------------------------------------------------------------------

class TestJsonExtraction:
    """`claude -p` adds a preamble even when told not to."""

    def test_bare_json(self):
        assert _extract_json_text('{"a": 1}') == '{"a": 1}'

    def test_fenced_json(self):
        assert json.loads(_extract_json_text('```json\n{"a": 1}\n```')) == {"a": 1}

    def test_json_after_prose(self):
        raw = '前提を確認しました。\n\n```json\n{"a": 1}\n```\n\n以上です。'
        assert json.loads(_extract_json_text(raw)) == {"a": 1}

    def test_json_array_after_prose(self):
        assert json.loads(_extract_json_text('note:\n[1, 2, 3]\n')) == [1, 2, 3]

    def test_no_json_is_returned_unchanged_for_a_clear_error(self):
        # Keeps json.loads() raising JSONDecodeError instead of masking it.
        assert _extract_json_text("まったくJSONではない") == "まったくJSONではない"


class TestCliJsonPromptSuffix:
    """generate_json must harden the prompt only on the CLI backend."""

    def _cli_runner(self, monkeypatch, stdout):
        monkeypatch.setenv("ANTHROPIC_DISABLED", "1")
        monkeypatch.setattr(
            "core.claude_client.shutil.which", lambda _: "/usr/bin/claude"
        )
        run = MagicMock(return_value=MagicMock(returncode=0, stdout=stdout, stderr=""))
        monkeypatch.setattr("core.claude_client.subprocess.run", run)
        return run

    def test_suffix_added_on_cli(self, monkeypatch, mock_anthropic):
        run = self._cli_runner(monkeypatch, '{"ok": true}')

        assert ClaudeClient().generate_json("base prompt") == {"ok": True}

        sent = run.call_args[0][0][2]
        assert sent.startswith("base prompt")
        assert "出力形式の厳守" in sent

    def test_suffix_not_added_on_sdk(self, mock_anthropic):
        mock_inner, _ = mock_anthropic
        mock_inner.messages.create.return_value = _make_response('{"ok": true}')

        ClaudeClient().generate_json("base prompt")

        sent = mock_inner.messages.create.call_args[1]["messages"][0]["content"]
        assert sent == "base prompt"

    def test_cli_prose_wrapped_json_is_parsed(self, monkeypatch, mock_anthropic):
        self._cli_runner(
            monkeypatch,
            "確認した前提:\n- なにか\n\n```json\n{\"pillar\": 2}\n```\n\n以上。",
        )
        assert ClaudeClient().generate_json("p") == {"pillar": 2}
