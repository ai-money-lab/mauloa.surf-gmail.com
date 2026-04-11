"""Base agent class for CITS multi-agent trading pipeline."""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod

import anthropic


logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all LLM-based trading agents.

    Each agent wraps an Anthropic Claude model and implements a specific
    analytical role in the trading pipeline.  Two model tiers are available:

    - quick_think: Claude Sonnet for fast, cost-effective analysis
    - deep_think:  Claude Opus for complex reasoning and final decisions
    """

    MODEL_MAP = {
        "quick_think": "claude-sonnet-4-20250514",
        "deep_think": "claude-opus-4-6",
    }

    def __init__(self, name: str, role: str, llm_type: str = "quick_think"):
        self.name = name
        self.role = role
        self.llm_type = llm_type
        self.logger = logging.getLogger(f"cits.agents.{name}")
        self._client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )

    def _get_model_id(self) -> str:
        """Return the Claude model ID for this agent's thinking tier."""
        model_id = self.MODEL_MAP.get(self.llm_type)
        if model_id is None:
            raise ValueError(
                f"Unknown llm_type '{self.llm_type}'. "
                f"Must be one of: {list(self.MODEL_MAP.keys())}"
            )
        return model_id

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> str:
        """Send a request to the Anthropic Claude API and return the text response.

        Uses ReAct-style prompting: the system prompt establishes the agent's
        role and reasoning framework, the user prompt provides the concrete
        data to analyse.
        """
        self.logger.info(
            "Calling LLM model=%s temperature=%.2f",
            self._get_model_id(),
            temperature,
        )

        message = self._client.messages.create(
            model=self._get_model_id(),
            max_tokens=4096,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = message.content[0].text
        self.logger.debug("LLM response length=%d", len(response_text))
        return response_text

    def _parse_json_response(self, text: str) -> dict:
        """Extract a JSON object from the LLM response text.

        The LLM may wrap the JSON in markdown code fences or precede it
        with reasoning text; this helper handles both cases.
        """
        cleaned = text.strip()

        # Try 1: direct parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Try 2: extract from ```json ... ``` fences
        if "```" in cleaned:
            import re
            fence_match = re.search(r"```(?:json)?\s*\n(.*?)```", cleaned, re.DOTALL)
            if fence_match:
                try:
                    return json.loads(fence_match.group(1).strip())
                except json.JSONDecodeError:
                    pass

        # Try 3: find first { ... last } in the text
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(cleaned[first_brace:last_brace + 1])
            except json.JSONDecodeError:
                pass

        self.logger.warning(
            "Failed to parse JSON from LLM response, returning raw text"
        )
        return {"raw_response": text, "parse_error": True}

    def _validate_and_parse(
        self,
        text: str,
        required_fields: dict[str, type] | None = None,
        defaults: dict | None = None,
    ) -> dict:
        """Parse LLM JSON response with schema validation.

        Args:
            text: Raw LLM response text.
            required_fields: Mapping of field name -> expected type.
            defaults: Default values for missing fields.

        Returns:
            Validated dict with all required fields present.
        """
        result = self._parse_json_response(text)

        if result.get("parse_error"):
            self.logger.warning("JSON parse failed for %s; using defaults", self.name)
            return {**(defaults or {}), "parse_error": True, "raw_response": text}

        if required_fields:
            for field, expected_type in required_fields.items():
                if field not in result:
                    default_val = (defaults or {}).get(field)
                    if default_val is not None:
                        result[field] = default_val
                        self.logger.warning(
                            "%s: missing field '%s', using default %s",
                            self.name, field, default_val,
                        )
                    else:
                        self.logger.warning(
                            "%s: missing required field '%s'", self.name, field
                        )
                elif not isinstance(result[field], expected_type):
                    # Try type coercion for common cases
                    try:
                        if expected_type in (int, float):
                            result[field] = expected_type(result[field])
                        elif expected_type is bool:
                            result[field] = bool(result[field])
                        elif expected_type is str:
                            result[field] = str(result[field])
                    except (TypeError, ValueError):
                        self.logger.warning(
                            "%s: field '%s' has wrong type (expected %s, got %s)",
                            self.name, field, expected_type.__name__,
                            type(result[field]).__name__,
                        )

        return result

    @abstractmethod
    def analyze(self, context: dict) -> dict:
        """Run this agent's analysis on the provided context.

        Args:
            context: A dictionary whose contents depend on the concrete agent.
                     Typically includes ``ticker``, market data, and any
                     upstream agent outputs.

        Returns:
            A dictionary containing the agent's analytical output.
        """
        ...
