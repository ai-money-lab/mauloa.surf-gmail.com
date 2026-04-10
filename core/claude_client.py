"""Claude API client wrapper for the HIROKI AI Empire."""

import os
import json
import logging
from typing import Optional, Tuple

from anthropic import Anthropic, APIStatusError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Default model — updated 2026-04-10 from claude-sonnet-4-20250514 to 4.5
# to align with current production model and prepare for future deprecation.
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


class ClaudeClient:
    """Wrapper around the Anthropic Claude API."""

    def __init__(self, model: Optional[str] = None):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model or DEFAULT_MODEL

    def health_check(self) -> Tuple[bool, str]:
        """Send a minimal 1-token request to verify the API key and credit balance.

        Returns (ok, error_message). error_message is empty when ok=True.
        Used as a pre-flight check so the pipeline fails fast with a clear
        actionable reason instead of crashing mid-generation.
        """
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

    def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Generate text using Claude API."""
        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

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
        """Generate and parse JSON response from Claude API."""
        raw = self.generate(prompt, system, max_tokens, temperature)
        # Extract JSON from potential markdown code blocks
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (code fences)
            lines = [line for line in lines[1:] if not line.strip().startswith("```")]
            text = "\n".join(lines)
        return json.loads(text)
