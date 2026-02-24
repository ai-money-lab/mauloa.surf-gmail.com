"""
DEBATE ENGINE — AI同士が稼げるまで議論し続ける

フロー:
1. 失敗したTrialを受け取る
2. ALPHA（楽観・実行派）とOMEGA（批判・分析派）が議論
3. 3ラウンドの議論で合意形成
4. 改善策を出力 → Trialに再投入
5. 成功するまでループ

ALPHAは「こうすれば売れる」を提案し、
OMEGAは「それじゃダメだ、こうしろ」と反論する。
この緊張関係が最適解を生む。
"""

from __future__ import annotations

import json
import hashlib
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path

from nexus.common import call_api, parse_json
from nexus.trial.trial_runner import Trial

logger = logging.getLogger("nexus.debate")


@dataclass
class DebateRound:
    """議論の1ラウンド"""
    round_number: int
    alpha_argument: str
    omega_argument: str
    points_of_agreement: list[str] = field(default_factory=list)
    points_of_disagreement: list[str] = field(default_factory=list)


@dataclass
class DebateResult:
    """議論の最終結果"""
    trial_id: str
    rounds: list[DebateRound] = field(default_factory=list)
    consensus: str = ""
    improvements: list[str] = field(default_factory=list)
    new_strategy: str = ""
    should_retry: bool = False
    pivot_suggestion: str = ""
    confidence: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    debate_id: str = ""

    def __post_init__(self):
        if not self.debate_id:
            raw = f"{self.trial_id}{self.timestamp}"
            self.debate_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "debate_id": self.debate_id,
            "trial_id": self.trial_id,
            "rounds": [
                {
                    "round": r.round_number,
                    "alpha": r.alpha_argument[:200],
                    "omega": r.omega_argument[:200],
                    "agree": r.points_of_agreement,
                    "disagree": r.points_of_disagreement,
                }
                for r in self.rounds
            ],
            "consensus": self.consensus,
            "improvements": self.improvements,
            "new_strategy": self.new_strategy,
            "should_retry": self.should_retry,
            "pivot_suggestion": self.pivot_suggestion,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


ALPHA_DEBATE_PROMPT = """あなたはALPHA — 創造と実行を重視するAIです。

議論のルール:
- あなたは楽観的で実行重視
- 「どうすれば成功するか」に焦点を当てる
- 具体的な改善案を必ず提示する
- OMEGAの批判に対して、建設的な反論をする
- 最終的には合意を目指す

出力（JSON）:
- "argument": あなたの主張
- "proposed_improvements": 具体的な改善案リスト
- "counter_to_omega": OMEGAへの反論（あれば）
- "concessions": OMEGAの意見で認めるべき点"""

OMEGA_DEBATE_PROMPT = """あなたはOMEGA — 批判的分析と最適化を重視するAIです。

議論のルール:
- あなたは批判的だが建設的
- 「なぜ失敗したか」「何が足りないか」に焦点を当てる
- 市場データや論理に基づく指摘をする
- ALPHAの提案の穴を突く
- 最終的には合意を目指す

出力（JSON）:
- "argument": あなたの主張
- "critical_issues": 重大な問題点リスト
- "counter_to_alpha": ALPHAへの反論
- "constructive_suggestions": 建設的な改善提案"""

SYNTHESIS_PROMPT = """あなたはALPHAとOMEGAの議論を統合する仲裁者です。

3ラウンドの議論結果から、最終的な合意と改善戦略を導いてください。

出力（JSON）:
- "consensus": 合意点のまとめ
- "improvements": 具体的な改善策リスト（優先順位付き）
- "new_strategy": 新しいアプローチの概要
- "should_retry": この機会を再挑戦すべきか（true/false）
- "pivot_suggestion": ピボットするなら何に（空欄なら不要）
- "confidence": この改善策の成功確率（0-1）
- "key_insight": 議論から得られた最重要インサイト"""


class DebateEngine:
    """
    AI同士の議論エンジン

    失敗したTrialについてALPHA-OMEGAが3ラウンド議論し、
    改善策を導き出す。稼げるまで議論を繰り返す。
    """

    MAX_ROUNDS = 3

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path("nexus/data/debate")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.debate_history: list[DebateResult] = []

    def debate(self, trial: Trial) -> DebateResult:
        """失敗したTrialについて議論する"""
        logger.info("Starting debate for trial %s", trial.trial_id)
        context = self._build_context(trial)
        rounds: list[DebateRound] = []
        alpha_history = ""
        omega_history = ""

        for round_num in range(1, self.MAX_ROUNDS + 1):
            logger.info("Debate round %d/%d", round_num, self.MAX_ROUNDS)

            # ALPHA の主張
            alpha_input = self._build_round_input(
                round_num, context, alpha_history, omega_history, is_alpha=True
            )
            alpha_response = self._call_ai(ALPHA_DEBATE_PROMPT, alpha_input)

            # OMEGA の主張
            omega_input = self._build_round_input(
                round_num, context, alpha_history + f"\n\nALPHA Round {round_num}: {json.dumps(alpha_response, ensure_ascii=False)}",
                omega_history, is_alpha=False
            )
            omega_response = self._call_ai(OMEGA_DEBATE_PROMPT, omega_input)

            # ラウンド記録
            debate_round = DebateRound(
                round_number=round_num,
                alpha_argument=alpha_response.get("argument", ""),
                omega_argument=omega_response.get("argument", ""),
                points_of_agreement=alpha_response.get("concessions", []),
                points_of_disagreement=omega_response.get("critical_issues", []),
            )
            rounds.append(debate_round)

            # 履歴更新
            alpha_history += f"\nRound {round_num} ALPHA: {alpha_response.get('argument', '')[:200]}"
            omega_history += f"\nRound {round_num} OMEGA: {omega_response.get('argument', '')[:200]}"

            # Adaptive termination: if round 2 shows high agreement, skip round 3
            if round_num == 2 and len(rounds) >= 2:
                concessions = alpha_response.get("concessions", [])
                constructive = omega_response.get("constructive_suggestions", [])
                if len(concessions) >= 2 and len(constructive) >= 2:
                    logger.info("High agreement detected after round 2 — skipping round 3")
                    break

        # 統合・合意形成
        logger.info("Synthesizing debate results from %d rounds", len(rounds))
        synthesis = self._synthesize(rounds, context)

        result = DebateResult(
            trial_id=trial.trial_id,
            rounds=rounds,
            consensus=synthesis.get("consensus", ""),
            improvements=synthesis.get("improvements", []),
            new_strategy=synthesis.get("new_strategy", ""),
            should_retry=synthesis.get("should_retry", False),
            pivot_suggestion=synthesis.get("pivot_suggestion", ""),
            confidence=synthesis.get("confidence", 0.0),
        )

        self.debate_history.append(result)
        self._save_debate(result)
        return result

    def get_improvement_plan(self, debate_result: DebateResult) -> list[str]:
        """議論結果から改善計画を抽出"""
        return debate_result.improvements

    def _build_context(self, trial: Trial) -> str:
        """Trial情報からコンテキストを構築"""
        context = (
            f"=== 失敗したTrial ===\n"
            f"機会: {trial.opportunity.title}\n"
            f"種別: {trial.opportunity.opportunity_type.value}\n"
            f"想定月収: {trial.opportunity.estimated_revenue}円\n"
            f"プラットフォーム: {trial.opportunity.platform}\n"
            f"結果: {trial.result.value}\n"
            f"試行回数: {trial.retry_count + 1}\n\n"
        )

        if trial.evaluation:
            context += f"評価スコア: {trial.evaluation.get('total_score', 'N/A')}/50\n"
            context += f"強み: {trial.evaluation.get('strengths', [])}\n"
            context += f"弱み: {trial.evaluation.get('weaknesses', [])}\n"

        if trial.lessons:
            context += f"教訓: {trial.lessons}\n"

        if trial.product:
            context += (
                f"\n=== 生成された商品 ===\n"
                f"商品名: {trial.product.name}\n"
                f"価格: {trial.product.price}円\n"
                f"説明: {trial.product.description}\n"
            )

        return context

    def _build_round_input(
        self,
        round_num: int,
        context: str,
        own_history: str,
        other_history: str,
        is_alpha: bool,
    ) -> str:
        """ラウンド入力を構築"""
        other_name = "OMEGA" if is_alpha else "ALPHA"

        content = f"ラウンド {round_num}/{self.MAX_ROUNDS}\n\n{context}"

        if own_history:
            content += f"\n\nあなたの過去の発言:\n{own_history}"
        if other_history:
            content += f"\n\n{other_name}の発言:\n{other_history}"

        if round_num == self.MAX_ROUNDS:
            content += "\n\n【最終ラウンド】合意に向けてまとめてください。"

        return content

    def _call_ai(self, system_prompt: str, user_content: str) -> dict:
        """Claude APIを呼び出す"""
        logger.debug("Calling API with system prompt: %s...", system_prompt[:60])
        raw = call_api(
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
            max_tokens=2048,
        )
        return parse_json(raw, default={"argument": raw})

    def _synthesize(self, rounds: list[DebateRound], context: str) -> dict:
        """議論を統合して合意を形成する"""
        rounds_text = "\n\n".join(
            f"--- Round {r.round_number} ---\n"
            f"ALPHA: {r.alpha_argument[:300]}\n"
            f"OMEGA: {r.omega_argument[:300]}\n"
            f"合意点: {r.points_of_agreement}\n"
            f"対立点: {r.points_of_disagreement}"
            for r in rounds
        )

        logger.debug("Synthesizing %d rounds of debate", len(rounds))
        raw = call_api(
            system=SYNTHESIS_PROMPT,
            messages=[{
                "role": "user",
                "content": f"元のコンテキスト:\n{context}\n\n議論履歴:\n{rounds_text}",
            }],
            max_tokens=2048,
        )
        return parse_json(raw, default={"consensus": raw, "should_retry": True, "improvements": [], "confidence": 0.5})

    def _save_debate(self, result: DebateResult) -> None:
        """議論結果を保存"""
        output_file = self.data_dir / f"{result.debate_id}.json"
        output_file.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
