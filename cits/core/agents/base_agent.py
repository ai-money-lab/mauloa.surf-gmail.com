"""Base agent class for CITS multi-agent trading pipeline."""

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

        The LLM may wrap the JSON in markdown code fences; this helper
        strips them before parsing.
        """
        cleaned = text.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (possibly ```json)
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            self.logger.warning(
                "Failed to parse JSON from LLM response, returning raw text"
            )
            return {"raw_response": text, "parse_error": True}

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
