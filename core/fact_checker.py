"""Fact checker — prevents fabricated claims and typos from being posted.

Detects:
- References to non-existent tools/URLs/services
- Unverifiable statistics presented as fact
- Inflated experience numbers (years, case counts)
- Claims about services HIROKI doesn't actually offer
- Typos and incorrect names/terms
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Things HIROKI actually has/does (verified from persona)
VERIFIED_FACTS = {
    "company": "ROCKEDGE Property Management",
    "dog_name": "KOA",
    "dog_breed": "プラシュスキー・クリサジーク",
    "dog_weight_kg": 3,
    "hobbies": ["サーフィン", "コーデックス栽培", "コーヒーの木"],
    "tools": ["MATTERPORT"],
    "role": "施工コーディネーター",  # NOT a direct contractor
    "services_coordinated": [
        "リフォーム", "AI防犯カメラ", "太陽光",
        "特殊清掃", "遺品整理", "クリーニング",
    ],
    "business_areas": ["賃貸管理", "売買仲介", "施工コーディネート"],
    "gym": "B.A.D GYM",
    "gym_supervisor": "鈴木佑輔",  # ベンチプレス世界王者。「佑介」は誤字
}

# Known correct spellings for names/terms that are commonly mistyped
CORRECT_SPELLINGS = {
    "鈴木佑介": "鈴木佑輔",  # 正しくは「佑輔」
    "鈴木祐介": "鈴木佑輔",
    "鈴木祐輔": "鈴木佑輔",
    "鈴木雄介": "鈴木佑輔",
    "鈴木雄輔": "鈴木佑輔",
    "プラシュスキークリサジーク": "プラシュスキー・クリサジーク",
    "ROCK EDGE": "ROCKEDGE",
    "Rock Edge": "ROCKEDGE",
    "ロックエッジ": "ROCKEDGE",
    "マターポート": "MATTERPORT",
    "シュミレーション": "",  # 使用禁止語。auto_fixで削除はしない（violationで弾く）
    "シュミレーター": "",
    "コーディック": "コーデックス",
    "コーデクス": "コーデックス",
}

# Words completely banned from X posts
BANNED_WORDS = [
    (r"シミュレーション|シュミレーション", "banned_word",
     "「シミュレーション」は使用禁止。存在しないサービスを連想させるため即不合格"),
    (r"シミュレーター|シュミレーター", "banned_word",
     "「シミュレーター」は使用禁止。存在しないサービスを連想させるため即不合格"),
]

# Common Japanese typos and incorrect expressions
TYPO_PATTERNS = [
    (r"ずつ(?!し)", None, None),  # 「ずつ」は正しい（「づつ」が誤り）
    (r"づつ", "typo", "「づつ」→「ずつ」が正しい表記です"),
    (r"言う(?:事|こと)(?:が|は|を|も)", None, None),  # OK
    (r"いう事が", "typo", "「いう事が」→「いうことが」（ひらがなが自然）"),
    (r"ヶ月(?!間)", None, None),  # OK
    (r"ヵ月", "typo", "「ヵ月」→「ヶ月」が一般的"),
    (r"([一-龥])を行な([うっいえ])", "typo", "「行なう」→「行う」が一般的"),
]

# Patterns that indicate fabricated content
FABRICATION_PATTERNS = [
    # Non-existent tools/services mentioned vaguely
    (r"ツール|アプリ|計算機",
     "tool_reference",
     "存在しないツール・アプリへの言及の可能性"),
    # Inflated personal experience numbers
    (r"(\d{2,})\s*年間?で?\s*(\d{3,})\s*件",
     "inflated_experience",
     "経験年数・件数の誇大表現"),
    (r"(\d{2,})\s*年[以上間]",
     "years_claim",
     "具体的な年数表現（ペルソナルールで禁止）"),
    # Definitive statistics without source
    (r"(\d+)\s*割が|(\d+)%が|(\d+)パーセントが",
     "unsourced_stat",
     "出典のない断定的な統計"),
    # Claims of direct construction work
    (r"自分で(施工|工事|取り付け|設置)した|俺が(やった|作った|直した)",
     "false_role",
     "自分で施工したかのような表現（コーディネーターの立場に反する）"),
    # External URL/link patterns
    (r"https?://|\.com|\.jp|\.net|\.org",
     "external_link",
     "外部リンクが含まれている"),
]

# Numbers that should always be softened
# Softener words that make number claims acceptable
_SOFTENERS = ("約", "くらい", "ほど", "体感で", "体感では", "だいたい", "およそ")

HARD_NUMBER_PATTERNS = [
    (r"(\d+)万円(損|得|節約|儲|増)",
     "hard_number_claim",
     "数字が柔らかいニュアンスなしに断定されている"),
]


@dataclass
class FactCheckResult:
    """Result of a fact check."""
    passed: bool = True
    violations: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    auto_fixes: dict = field(default_factory=dict)

    def add_violation(self, code: str, message: str, matched_text: str = ""):
        self.passed = False
        self.violations.append({
            "code": code,
            "message": message,
            "matched_text": matched_text,
        })

    def add_warning(self, code: str, message: str, matched_text: str = ""):
        self.warnings.append({
            "code": code,
            "message": message,
            "matched_text": matched_text,
        })


class FactChecker:
    """Check posts for fabricated or unverifiable claims."""

    def check(self, text: str) -> FactCheckResult:
        """Run all fact checks on post text.

        Args:
            text: Post text (str or joined list for threads).

        Returns:
            FactCheckResult with violations and warnings.
        """
        if isinstance(text, list):
            text = "\n".join(text)

        result = FactCheckResult()

        self._check_banned_words(text, result)
        self._check_fabrication_patterns(text, result)
        self._check_hard_numbers(text, result)
        self._check_tool_references(text, result)
        self._check_role_accuracy(text, result)
        self._check_experience_claims(text, result)
        self._check_typos_and_names(text, result)

        if result.violations:
            logger.warning(
                "Fact check FAILED: %d violations found",
                len(result.violations),
            )
            for v in result.violations:
                logger.warning("  [%s] %s: %s", v["code"], v["message"], v["matched_text"])

        return result

    def _check_banned_words(self, text: str, result: FactCheckResult):
        """Check for completely banned words."""
        for pattern, code, message in BANNED_WORDS:
            match = re.search(pattern, text)
            if match:
                result.add_violation(code, message, match.group())

    def _check_fabrication_patterns(self, text: str, result: FactCheckResult):
        """Check for known fabrication patterns."""
        for pattern, code, message in FABRICATION_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                matched_str = str(matches[0]) if matches else ""
                # Tool references are warnings (might be legitimate)
                if code == "tool_reference":
                    result.add_warning(code, message, matched_str)
                else:
                    result.add_violation(code, message, matched_str)

    def _check_hard_numbers(self, text: str, result: FactCheckResult):
        """Check for hard number claims without softeners."""
        for pattern, code, message in HARD_NUMBER_PATTERNS:
            for match in re.finditer(pattern, text):
                # Check if any softener word appears before the number
                start = max(0, match.start() - 10)
                prefix = text[start:match.start()]
                if not any(s in prefix for s in _SOFTENERS):
                    result.add_violation(code, message, match.group())

    def _check_tool_references(self, text: str, result: FactCheckResult):
        """Check if referenced tools/services actually exist."""
        # Check for vague tool references that don't match known tools
        vague_tool_patterns = [
            r"(?:うちの|弊社の|自社の)(?:シミュレーター|ツール|アプリ|システム|計算機|サービス)",
            r"(?:こちらの|この)(?:シミュレーター|ツール|アプリ|計算機)",
        ]
        for pattern in vague_tool_patterns:
            match = re.search(pattern, text)
            if match:
                result.add_violation(
                    "nonexistent_tool",
                    "存在しない自社ツール・サービスへの言及",
                    match.group(),
                )

    def _check_role_accuracy(self, text: str, result: FactCheckResult):
        """Ensure HIROKI's role is accurately represented."""
        # He coordinates, not does the work directly
        direct_work_patterns = [
            r"(?:自分で|私が|俺が)\s*(?:施工|工事|取り付け|設置|修理|清掃|解体)(?:した|しました|してきた)",
            r"(?:現場で|自ら)\s*(?:手を動かし|作業し)",
        ]
        for pattern in direct_work_patterns:
            match = re.search(pattern, text)
            if match:
                result.add_violation(
                    "false_role",
                    "施工コーディネーターが直接作業したかのような表現",
                    match.group(),
                )

    def _check_experience_claims(self, text: str, result: FactCheckResult):
        """Check for inflated or specific experience claims."""
        # Specific year counts are prohibited
        year_match = re.search(r"(\d+)\s*年[間以上]?\s*(?:の経験|やって|従事|携わ)", text)
        if year_match:
            result.add_violation(
                "specific_years",
                "具体的な業界歴の年数表現は禁止（「長年」を使う）",
                year_match.group(),
            )

        # Large case count claims
        case_match = re.search(r"(\d+)\s*件\s*(?:以上|を超える|見てき|対応してき|扱ってき)", text)
        if case_match:
            count = int(case_match.group(1))
            if count >= 100:
                result.add_violation(
                    "inflated_case_count",
                    f"大きな実績数字（{count}件）はマウントに聞こえる。禁止",
                    case_match.group(),
                )

    def _check_typos_and_names(self, text: str, result: FactCheckResult):
        """Check for typos, especially in names and key terms.

        This is critical — misspelling names destroys credibility.
        """
        # Check known misspellings
        for wrong, correct in CORRECT_SPELLINGS.items():
            if wrong in text:
                result.add_violation(
                    "name_typo",
                    f"表記ミス: 「{wrong}」→「{correct}」に修正必須",
                    wrong,
                )
                result.auto_fixes[wrong] = correct

        # Check common Japanese typos
        for pattern, code, message in TYPO_PATTERNS:
            if code is None:
                continue
            match = re.search(pattern, text)
            if match:
                result.add_violation(code, message, match.group())

        # Check for repeated characters that might be accidental
        repeated = re.search(r"(.)\1{3,}", text)
        if repeated and repeated.group()[0] not in "。、！？…ーー":
            result.add_warning(
                "repeated_chars",
                f"同じ文字が4回以上連続: 「{repeated.group()}」",
                repeated.group(),
            )

    def auto_fix(self, text: str) -> str:
        """Apply automatic fixes for known typos.

        Returns corrected text. Only fixes unambiguous errors.
        Banned words (empty correction) are NOT auto-fixed — they must be rejected.
        """
        if isinstance(text, list):
            return [self.auto_fix(t) for t in text]

        for wrong, correct in CORRECT_SPELLINGS.items():
            if correct:  # Skip banned words (empty correction)
                text = text.replace(wrong, correct)
        return text
