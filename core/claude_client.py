"""Claude text-generation client with two interchangeable backends.

Backends
--------
``claude -p`` subprocess (``cli``)
    No Anthropic API billing — it runs on the signed-in Claude Code CLI.
    Selected when ``ANTHROPIC_DISABLED`` is truthy. If the CLI is not
    available in that mode the client raises instead of falling back to the
    billed SDK, so "disabled" can never silently become "billed".

Anthropic SDK (``sdk``)
    The billed ``/v1/messages`` path. Default when ``ANTHROPIC_DISABLED``
    is unset.

Sampling parameters
-------------------
``anthropic`` 1.x removed ``temperature`` / ``top_p`` / ``top_k`` from
``messages.create()`` — passing one raises ``TypeError``. The public
``temperature=`` argument of this module is kept (callers rely on it) and is
forwarded through ``extra_body`` only for models that still accept it; for
every other model it is dropped, because Opus 4.7 and later reject the
parameter with a 400 even at its default value.
"""

import json
import logging
import os
import shutil
import subprocess
from typing import Optional, Tuple

from anthropic import Anthropic, APIStatusError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Default model — updated 2026-04-10 from claude-sonnet-4-20250514 to 4.5
# to align with current production model and prepare for future deprecation.
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"

# Model-ID prefixes that still accept temperature/top_p/top_k.
# Anything not listed here has the sampling parameter dropped — dropping is
# always safe, while sending it to a model that rejects it is a hard 400.
SAMPLING_PARAM_MODEL_PREFIXES = (
    "claude-sonnet-4-5",
    "claude-sonnet-4-6",
    "claude-sonnet-4-0",
    "claude-sonnet-4-2025",
    "claude-opus-4-5",
    "claude-opus-4-6",
    "claude-opus-4-0",
    "claude-opus-4-2025",
    "claude-haiku-4-5",
)

CLI_TIMEOUT_SECONDS = int(os.getenv("CLAUDE_CLI_TIMEOUT", "300"))

# Appended to generate_json() prompts on the CLI backend only.
JSON_ONLY_SUFFIX = (
    "\n\n---\n"
    "【出力形式の厳守】上で指定されたJSONドキュメントだけを出力すること。\n"
    "- 前置き・見出し・前提の確認・判断を仰ぐ文・補足説明を一切付けない\n"
    "- ファイルやリポジトリを調べようとせず、このプロンプトの情報だけで作る\n"
    "- 最初の文字は { で、最後の文字は } にすること\n"
)

_TRUTHY = {"1", "true", "yes", "on"}


def api_billing_disabled() -> bool:
    """True when ANTHROPIC_DISABLED forbids billed API calls."""
    return os.getenv("ANTHROPIC_DISABLED", "").strip().lower() in _TRUTHY


def model_accepts_sampling_params(model: str) -> bool:
    """True when `model` still accepts temperature/top_p/top_k."""
    return model.startswith(SAMPLING_PARAM_MODEL_PREFIXES)


def _strip_code_fence(text: str) -> str:
    """Remove a surrounding markdown code fence, if present."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.split("\n")
    kept = [line for line in lines[1:] if not line.strip().startswith("```")]
    return "\n".join(kept)


def _extract_json_text(text: str) -> str:
    """Pull the JSON document out of a model response.

    Handles a bare document, a fenced block, and a document wrapped in
    prose — `claude -p` in particular likes to add a preamble even when the
    prompt says JSON only.
    """
    stripped = _strip_code_fence(text)
    if stripped[:1] in ("{", "["):
        return stripped
    for opener, closer in (("{", "}"), ("[", "]")):
        start = stripped.find(opener)
        end = stripped.rfind(closer)
        if start != -1 and end > start:
            return stripped[start:end + 1]
    return stripped


class ClaudeClient:
    """Wrapper around Claude text generation (SDK or `claude -p` CLI)."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or DEFAULT_MODEL
        self.use_cli = api_billing_disabled()
        self._cli_path = shutil.which("claude")
        if self.use_cli and not self._cli_path:
            raise RuntimeError(
                "ANTHROPIC_DISABLED is set but the `claude` CLI was not found "
                "on PATH. Refusing to fall back to the billed Anthropic API."
            )
        # Constructing the SDK client is cheap and makes no request; skip it
        # entirely in CLI mode so a missing API key is not an error there.
        self.client = None if self.use_cli else Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )

    @property
    def backend(self) -> str:
        """"cli" when routed through `claude -p`, else "sdk"."""
        return "cli" if self.use_cli else "sdk"

    # -- backend: claude -p ------------------------------------------------

    def _run_cli(self, prompt: str, system: str = "") -> str:
        """Generate via `claude -p`. No Anthropic API billing.

        `--tools ""` and `--strict-mcp-config` keep the child process from
        running a full agent loop (tools + MCP servers) for what is a
        single-shot text generation.
        """
        argv = [
            self._cli_path, "-p", prompt,
            "--output-format", "text",
            "--model", self.model,
            "--tools", "",
            "--strict-mcp-config",
        ]
        if system:
            argv += ["--system-prompt", system]

        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=CLI_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"claude -p timed out after {CLI_TIMEOUT_SECONDS}s"
            ) from exc

        if proc.returncode != 0:
            raise RuntimeError(
                f"claude -p exited {proc.returncode}: "
                f"{(proc.stderr or '').strip()[:300]}"
            )
        out = (proc.stdout or "").strip()
        if not out:
            raise RuntimeError("claude -p returned empty output")
        return out

    # -- backend: Anthropic SDK -------------------------------------------

    def _build_sdk_kwargs(
        self, prompt: str, system: str, max_tokens: int, temperature: float
    ) -> dict:
        """Build messages.create() kwargs valid for anthropic 1.x."""
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        if model_accepts_sampling_params(self.model):
            # anthropic 1.x dropped the `temperature` keyword argument;
            # extra_body is merged into the request JSON as-is.
            kwargs["extra_body"] = {"temperature": temperature}
        else:
            logger.debug(
                "Dropping temperature=%s: model %s rejects sampling params",
                temperature, self.model,
            )
        return kwargs

    def _sdk_health_check(self) -> Tuple[bool, str]:
        """Minimal 1-token request to verify key, model and credit balance."""
        try:
            self.client.messages.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True, ""
        except APIStatusError as e:
            # Extract the API's error message for a clean diagnostic.
            try:
                body = e.response.json()
                msg = body.get("error", {}).get("message", str(e))
            except Exception:
                msg = str(e)
            return False, f"[{e.status_code}] {msg}"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    # -- public API --------------------------------------------------------

    def health_check(self) -> Tuple[bool, str]:
        """Verify the active backend answers. Returns (ok, error_message).

        error_message is empty when ok=True. Used as a pre-flight so the
        pipeline fails fast with a clear, actionable reason instead of
        crashing mid-generation.
        """
        if not self.use_cli:
            return self._sdk_health_check()
        try:
            self._run_cli("Reply with exactly: ok")
            return True, ""
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Generate text with the active backend."""
        if self.use_cli:
            try:
                return self._run_cli(prompt, system)
            except Exception as e:
                logger.error("claude -p call failed: %s", e)
                raise

        kwargs = self._build_sdk_kwargs(prompt, system, max_tokens, temperature)
        try:
            response = self.client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            logger.error("Claude API call failed: %s", e)
            raise

    def generate_json(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> dict:
        """Generate and parse a JSON response (code fences/prose tolerated)."""
        if self.use_cli:
            # `claude -p` is an agent CLI: without this it answers with a
            # report ("前提", "判断してほしいこと") instead of the document.
            prompt = prompt + JSON_ONLY_SUFFIX
        raw = self.generate(prompt, system, max_tokens, temperature)
        return json.loads(_extract_json_text(raw))
