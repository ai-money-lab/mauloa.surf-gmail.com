"""AI品質チェッカー - 全システム共通の品質ゲート"""

import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .claude_client import ClaudeClient

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
        ],
        "pass_fail_items": ["no_external_links", "no_banned_content", "character_limit"],
        "threshold": 70,
        "description": "X投稿用品質チェック",
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
        "pass_fail_items": ["no_banned_content", "deliverable_format"],
        "threshold": 75,
        "description": "レポート納品物用品質チェック",
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
        "pass_fail_items": ["no_banned_content"],
        "threshold": 70,
        "description": "情報収集結果用品質チェック",
    },
}

# 禁止キーワード: 完全一致（単語境界）で検出するもの
BANNED_KEYWORDS_EXACT = [
    r"\bEA\b", r"\bFX\b", r"\bMT4\b", r"\bMT5\b",
    r"\bXAUUSD\b", r"\bpips\b",
]

# 禁止キーワード: 部分一致で検出するもの（日本語含む）
BANNED_KEYWORDS_PARTIAL = [
    "自動売買", "ゴールド取引", "MetaTrader", "Expert Advisor",
    "為替", "通貨ペア", "ロット数",
]


class QualityCheckResult:
    """品質チェック結果"""

    def __init__(self, scores: dict, profile: str, content: str):
        self.scores = scores
        self.profile = profile
        self.content = content

        profile_config = PROFILES[profile]
        self.threshold = profile_config["threshold"]

        self.total_score = sum(scores.values())
        self.result = "auto_approved" if self.total_score >= self.threshold else "rejected"
        self.rejection_reasons = []
        self.improvement_suggestions = []
        self.checked_at = datetime.now(JST).isoformat()

    def to_dict(self) -> dict:
        return {
            "scores": self.scores,
            "total_score": self.total_score,
            "threshold": self.threshold,
            "result": self.result,
            "rejection_reasons": self.rejection_reasons,
            "improvement_suggestions": self.improvement_suggestions,
            "checked_at": self.checked_at,
        }


class QualityChecker:
    """AI品質チェッカー"""

    def __init__(self):
        self.claude = ClaudeClient()
        self.log_dir = Path(__file__).parent.parent / "data" / "quality_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _contains_banned_content(self, text: str) -> bool:
        # 完全一致（単語境界）チェック
        for pattern in BANNED_KEYWORDS_EXACT:
            if re.search(pattern, text):
                return True
        # 部分一致チェック（日本語キーワード）
        text_lower = text.lower()
        for keyword in BANNED_KEYWORDS_PARTIAL:
            if keyword.lower() in text_lower:
                return True
        return False

    def check(self, profile: str, content: str, context: str = "") -> QualityCheckResult:
        """品質チェックを実行"""
        if profile not in PROFILES:
            raise ValueError(f"Unknown profile: {profile}. Valid: {list(PROFILES.keys())}")

        profile_config = PROFILES[profile]

        if self._contains_banned_content(content):
            scores = {item: 0 for item in profile_config["items"]}
            result = QualityCheckResult(scores, profile, content)
            result.result = "rejected"
            result.rejection_reasons = ["禁止コンテンツ（EA/FX関連）が検出されました"]
            self._save_log(result, context)
            return result

        prompt = self.claude.load_prompt(
            "quality_check.txt",
            profile=profile,
            threshold=profile_config["threshold"],
        )

        check_items_text = "\n".join(
            f"- {item} (1-10)" if item not in profile_config["pass_fail_items"]
            else f"- {item} (pass/fail → 10=pass, 0=fail)"
            for item in profile_config["items"]
        )
        prompt = prompt.replace("{チェック項目リスト}", check_items_text)

        full_prompt = f"{prompt}\n\n## チェック対象コンテンツ:\n{content}"
        if context:
            full_prompt += f"\n\n## コンテキスト:\n{context}"

        try:
            raw_result = self.claude.generate_json(
                full_prompt,
                temperature=0.1,
                max_tokens=2048,
            )

            scores = {}
            for item in profile_config["items"]:
                score = raw_result.get("scores", {}).get(item, 5)
                if item in profile_config["pass_fail_items"]:
                    scores[item] = 10 if score in (10, True, "pass") else 0
                else:
                    scores[item] = max(0, min(10, int(score)))

            result = QualityCheckResult(scores, profile, content)
            result.rejection_reasons = raw_result.get("rejection_reasons", [])
            result.improvement_suggestions = raw_result.get("improvement_suggestions", [])

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Quality check parse error: {e}")
            scores = {item: 5 for item in profile_config["items"]}
            result = QualityCheckResult(scores, profile, content)
            result.result = "rejected"
            result.rejection_reasons = [f"品質チェック解析エラー: {e}"]

        self._save_log(result, context)
        return result

    def check_with_retry(
        self, profile: str, content: str, context: str = "", regenerate_fn=None
    ) -> tuple[QualityCheckResult, str]:
        """品質チェックをリトライ付きで実行"""
        current_content = content
        max_retries = 3

        for attempt in range(max_retries + 1):
            result = self.check(profile, current_content, context)

            if result.result == "auto_approved":
                return result, current_content

            if attempt < max_retries and regenerate_fn and result.improvement_suggestions:
                logger.info(
                    f"Quality check rejected (attempt {attempt + 1}), regenerating..."
                )
                current_content = regenerate_fn(
                    current_content, result.improvement_suggestions
                )
            elif attempt == max_retries:
                result.result = "escalated"
                logger.warning(f"Quality check escalated after {max_retries} retries")

        return result, current_content

    def _save_log(self, result: QualityCheckResult, context: str):
        """チェック結果をログ保存"""
        log_entry = result.to_dict()
        log_entry["context"] = context
        log_entry["content_preview"] = result.content[:200]

        date_str = datetime.now(JST).strftime("%Y-%m-%d")
        log_file = self.log_dir / f"{date_str}.jsonl"

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
