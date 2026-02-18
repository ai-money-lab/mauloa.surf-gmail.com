"""AI Quality Checker — automated quality gate for all systems."""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from core.claude_client import ClaudeClient
from core.notifier import Notifier

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

PROFILES = {
    "x_post": {
        "items": [
            "hook_power",
            "persona_match",
            "pillar_alignment",
            "algorithm_optimization",
            "no_external_links",
            "no_banned_content",
            "character_limit",
            "number_included",
            "cta_ending",
            "originality",
            "tone_balance",
            "algorithm_hooks",
        ],
        "threshold": 80,
        "max_score": 120,
    },
    "report": {
        "items": [
            "data_accuracy",
            "structure",
            "actionable",
            "professional_tone",
            "no_banned_content",
            "hiroki_insight",
            "visual_readability",
            "completeness",
            "market_relevance",
            "deliverable_format",
        ],
        "threshold": 75,
        "max_score": 100,
    },
    "data_collection": {
        "items": [
            "source_reliability",
            "freshness",
            "completeness",
            "structure",
            "no_banned_content",
            "deduplication",
            "relevance",
            "numerical_validity",
            "metadata_complete",
            "usability",
        ],
        "threshold": 70,
        "max_score": 100,
    },
}

PROMPT_TEMPLATE_PATH = Path(__file__).parent.parent / "prompts" / "quality_check.txt"
LOG_DIR = Path(__file__).parent.parent / "data" / "quality_logs"


class QualityChecker:
    """Automated quality gate using Claude API."""

    def __init__(self, claude_client: Optional[ClaudeClient] = None):
        self.claude = claude_client or ClaudeClient()
        self.notifier = Notifier()
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _load_prompt_template(self) -> str:
        return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")

    def _build_prompt(self, profile: str, content: str, context: str = "") -> str:
        profile_cfg = PROFILES[profile]
        template = self._load_prompt_template()
        items_list = "\n".join(f"- {item}" for item in profile_cfg["items"])
        prompt = template.replace("{profile}", profile)
        prompt = prompt.replace("{チェック項目リスト（プロファイルに応じて上記から選択）}", items_list)
        prompt = prompt.replace("{threshold}", str(profile_cfg["threshold"]))
        prompt += f"\n\n## チェック対象コンテンツ:\n{content}"
        if context:
            prompt += f"\n\n## コンテキスト:\n{context}"
        return prompt

    def check(
        self,
        profile: str,
        content: str,
        context: str = "",
        max_retries: int = 3,
    ) -> dict:
        """Run quality check. Returns result dict with scores and verdict."""
        if profile not in PROFILES:
            raise ValueError(f"Unknown profile: {profile}. Must be one of {list(PROFILES.keys())}")

        profile_cfg = PROFILES[profile]

        for attempt in range(1, max_retries + 1):
            try:
                prompt = self._build_prompt(profile, content, context)
                result = self.claude.generate_json(prompt, temperature=0.2)
                result["checked_at"] = datetime.now(JST).isoformat()
                result.setdefault("threshold", profile_cfg["threshold"])

                total = result.get("total_score", 0)
                if total >= profile_cfg["threshold"]:
                    result["result"] = "auto_approved"
                else:
                    result["result"] = "rejected"

                self._save_log(profile, result, attempt)
                return result

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Quality check attempt %d failed: %s", attempt, e)
                if attempt == max_retries:
                    escalated = {
                        "result": "escalated",
                        "error": str(e),
                        "checked_at": datetime.now(JST).isoformat(),
                        "threshold": profile_cfg["threshold"],
                        "total_score": 0,
                        "scores": {},
                    }
                    self._save_log(profile, escalated, attempt)
                    self.notifier.send_line(
                        f"品質チェック失敗（{max_retries}回リトライ後）: {profile}"
                    )
                    return escalated

        # Should not reach here, but safety net
        return {"result": "escalated", "total_score": 0, "scores": {}}

    def check_with_retry(
        self,
        profile: str,
        content: str,
        regenerate_fn=None,
        context: str = "",
        max_retries: int = 3,
    ) -> tuple:
        """Check quality and optionally regenerate on failure.

        Args:
            profile: Quality profile name.
            content: Content to check.
            regenerate_fn: Callable that takes (rejection_reasons, suggestions) and
                returns new content. If None, no regeneration is attempted.
            context: Optional context string.
            max_retries: Max regeneration attempts.

        Returns:
            Tuple of (final_content, quality_result).
        """
        for attempt in range(max_retries):
            result = self.check(profile, content, context)
            if result["result"] == "auto_approved":
                return content, result

            if regenerate_fn is None or attempt == max_retries - 1:
                if attempt == max_retries - 1 and result["result"] != "auto_approved":
                    result["result"] = "escalated"
                    self.notifier.send_line(
                        f"品質チェック{max_retries}回失敗 escalated: {profile}"
                    )
                return content, result

            # Regenerate
            reasons = result.get("rejection_reasons", [])
            suggestions = result.get("improvement_suggestions", [])
            content = regenerate_fn(reasons, suggestions)

        return content, result

    def _save_log(self, profile: str, result: dict, attempt: int) -> None:
        timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
        log_path = LOG_DIR / f"{profile}_{timestamp}_attempt{attempt}.json"
        log_data = {"profile": profile, "attempt": attempt, **result}
        log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Quality log saved: %s", log_path)
