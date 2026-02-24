"""Standalone Claude API client for System E.

System E 専用の Anthropic Claude API クライアント。
外部モジュール（core/）に依存せず、単体で動作する。
"""

import json
import os
import logging
import time
from typing import Optional

from anthropic import Anthropic, APIError, RateLimitError, APITimeoutError

logger = logging.getLogger(__name__)


class ClaudeClient:
    """Self-contained wrapper around the Anthropic Claude API."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = model or os.getenv("SYSTEM_E_MODEL", "claude-sonnet-4-20250514")

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

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(**kwargs)
                return response.content[0].text
            except (RateLimitError, APITimeoutError) as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        "Claude API %s (attempt %d/%d), retrying in %ds: %s",
                        type(e).__name__, attempt + 1, max_retries, wait, e,
                    )
                    time.sleep(wait)
                else:
                    logger.error("Claude API %s after %d attempts: %s", type(e).__name__, max_retries, e)
                    raise
            except APIError as e:
                logger.error("Claude API call failed: %s", e)
                raise
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
        return _extract_json(raw)


def _extract_json(text: str) -> dict:
    """Extract JSON from text that may contain markdown code fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines[1:] if not line.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)
