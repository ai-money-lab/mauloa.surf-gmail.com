"""
REVENUE DEBATE — 高品質なAI議論システム

旧DebateEngineとの違い:
- 旧: 「楽観 vs 悲観」の芝居をするだけ。データなし。
- 新: 5つの専門家ペルソナが、実データと市場知識に基づいて議論する。

ペルソナ:
1. PRODUCER — コンテンツ制作の専門家（何を作るべきか）
2. ANALYST — 市場データの分析者（数字で語る）
3. DISTRIBUTOR — プラットフォーム戦略家（どこで売るか）
4. CRITIC — リスク・品質管理者（何がダメか）
5. SYNTHESIZER — 統合・意思決定者（最終判断）

旧システムの「ALPHA楽観 vs OMEGA悲観」は所詮ロールプレイ。
新システムは各ペルソナが異なる専門知識を持ち、
具体的なデータに基づいて建設的に議論する。
"""

from __future__ import annotations

import json
import hashlib
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus.common import call_api, parse_json

logger = logging.getLogger("nexus.v2.revenue_debate")


@dataclass
class ExpertOpinion:
    """専門家の意見"""
    expert: str
    position: str
    evidence: list[str]
    recommendations: list[str]
    concerns: list[str]
    confidence: float  # 0-1


@dataclass
class DebateResult:
    """議論結果"""
    topic: str
    opinions: list[ExpertOpinion]
    consensus: str
    action_plan: list[dict[str, str]]
    priority_assets: list[dict[str, Any]]
    estimated_monthly_revenue: int
    key_risks: list[str]
    debate_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if not self.debate_id:
            raw = f"{self.topic}{self.timestamp}"
            self.debate_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "debate_id": self.debate_id,
            "topic": self.topic,
            "opinions": [
                {
                    "expert": o.expert,
                    "position": o.position[:300],
                    "evidence": o.evidence,
                    "recommendations": o.recommendations,
                    "concerns": o.concerns,
                    "confidence": o.confidence,
                }
                for o in self.opinions
            ],
            "consensus": self.consensus,
            "action_plan": self.action_plan,
            "priority_assets": self.priority_assets,
            "estimated_monthly_revenue": self.estimated_monthly_revenue,
            "key_risks": self.key_risks,
            "timestamp": self.timestamp,
        }


EXPERT_PROMPTS: dict[str, str] = {
    "PRODUCER": """あなたはデジタルコンテンツのプロデューサーです。

専門知識:
- AI音楽生成（Suno, Udio）の実際の品質と制約
- YouTube動画制作（TTS, 映像生成, 編集）の工程
- デジタル商品（テンプレート、eBook、ツール）の制作効率
- ストック素材の品質要件と承認基準

あなたの役割: 「何を、どのくらいの品質で、どれだけ速く作れるか」を判断する。
希望的観測ではなく、AIの現実的な生成能力に基づいて発言すること。

出力（JSON）:
- "position": あなたの主張（200文字以内）
- "evidence": 根拠のリスト
- "recommendations": 具体的な推奨アクション
- "concerns": 制作上の懸念点
- "confidence": この意見への自信度（0-1）""",

    "ANALYST": """あなたは市場データアナリストです。

専門知識:
- Spotifyストリーミング収益: $0.003-0.005/再生
- YouTube CPM: $2-10（ニッチ依存）
- Gumroad手数料: 10% + $0.50/取引
- Adobe Stock: ロイヤリティ33%
- Pond5: ロイヤリティ40-60%
- オーガニック検索トラフィック: 2026年に15-25%減少（AIオーバービュー影響）
- デジタル商品のコンバージョン率: 1-5%

あなたの役割: 数字で語る。感覚的な「稼げるかも」ではなく、
具体的な計算式で収益見込みを示すこと。

出力（JSON）:
- "position": あなたの分析（200文字以内）
- "evidence": 計算式と数値根拠
- "recommendations": データに基づく推奨
- "concerns": 数字が示すリスク
- "confidence": この分析への自信度（0-1）""",

    "DISTRIBUTOR": """あなたはプラットフォーム戦略の専門家です。

専門知識:
- DistroKid（$22.99/年で全ストリーミング配信）
- YouTube Data API（動画アップロード自動化可能）
- Gumroad（Discover機能で自然流入あり）
- Adobe Stock（AIコンテンツ受入OK、明示必須）
- Pond5（クリエイター価格設定可、40-60%ロイヤリティ）
- Lemon Squeezy（5%+$0.50、Stripe傘下）

あなたの役割: どのプラットフォームに、何を、いつ出すかを最適化する。
各プラットフォームのアルゴリズム、審査基準、収益モデルに精通している。

出力（JSON）:
- "position": あなたの戦略（200文字以内）
- "evidence": プラットフォーム選定の根拠
- "recommendations": 配信戦略の具体案
- "concerns": プラットフォームリスク
- "confidence": この戦略への自信度（0-1）""",

    "CRITIC": """あなたはリスク管理と品質管理の専門家です。

専門知識:
- AIコンテンツの法的リスク（著作権、商標、AI規制）
- プラットフォーム規約変更リスク（過去の事例多数）
- 品質が低いAIコンテンツの淘汰（スパム判定）
- 収益の過大見積もりのパターン
- 競合の増加速度

あなたの役割: 他の専門家の提案の穴を見つけ、現実的なリスクを指摘する。
ただし批判だけでなく、「ではどうすべきか」の代替案も必ず提示すること。

出力（JSON）:
- "position": あなたの批判的評価（200文字以内）
- "evidence": リスクの具体的根拠
- "recommendations": リスク軽減策
- "concerns": 最重要リスク
- "confidence": この評価への自信度（0-1）""",
}

SYNTHESIS_PROMPT = """あなたは4人の専門家の議論を統合する意思決定者です。

以下の専門家が議論しました:
- PRODUCER: コンテンツ制作の専門家
- ANALYST: 市場データアナリスト
- DISTRIBUTOR: プラットフォーム戦略家
- CRITIC: リスク管理者

全員の意見を踏まえて、最終的な行動計画を策定してください。

ルール:
- 全員の意見を公平に検討すること
- CRITICの懸念には必ず対処策を含めること
- ANALYSTの数字に基づいた現実的な計画にすること
- 「今日から何をするか」を明確にすること

出力（JSON）:
- "consensus": 全体の合意まとめ
- "action_plan": [
    {"step": 1, "action": "具体的アクション", "channel": "チャネル", "deadline": "期限"}
  ]
- "priority_assets": [
    {"asset_type": "タイプ", "theme": "テーマ", "reason": "なぜ優先か", "expected_revenue": 円}
  ]
- "estimated_monthly_revenue": 月間収益見込み（円・保守的に）
- "key_risks": ["リスク1", "リスク2"]
- "mitigation": ["対策1", "対策2"]"""


class RevenueDebate:
    """
    高品質なAI議論システム

    4つの専門家ペルソナが、実データに基づいて
    収益化戦略について議論し、合意を形成する。
    """

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path("nexus/data/v2/debate")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history: list[DebateResult] = []

    def debate(self, topic: str, context: str = "") -> DebateResult:
        """トピックについて4専門家が議論する"""
        logger.info("Starting revenue debate: %s", topic[:50])

        # Phase 1: 各専門家が独立に意見を出す
        opinions = self._gather_opinions(topic, context)

        # Phase 2: 統合して合意形成
        result = self._synthesize(topic, opinions)

        self.history.append(result)
        self._save_debate(result)
        logger.info("Debate complete: %s (revenue estimate: ¥%d/月)", result.debate_id, result.estimated_monthly_revenue)
        return result

    def quick_evaluate(self, asset_spec: dict[str, Any]) -> dict[str, Any]:
        """アセット仕様の簡易評価（ANALYST + CRITICのみ）"""
        topic = f"アセット評価: {asset_spec.get('theme', 'unknown')}"
        context = json.dumps(asset_spec, ensure_ascii=False, indent=2)

        analyst = self._get_opinion("ANALYST", topic, context)
        critic = self._get_opinion("CRITIC", topic, context)

        return {
            "analyst_score": analyst.confidence,
            "critic_score": critic.confidence,
            "avg_confidence": (analyst.confidence + critic.confidence) / 2,
            "should_create": (analyst.confidence + critic.confidence) / 2 > 0.5,
            "analyst_concerns": analyst.concerns,
            "critic_concerns": critic.concerns,
            "recommendations": analyst.recommendations + critic.recommendations,
        }

    def _gather_opinions(self, topic: str, context: str) -> list[ExpertOpinion]:
        """全専門家から意見を収集"""
        opinions = []
        # 前の専門家の意見を後の専門家に共有して議論の質を上げる
        prev_opinions_text = ""

        for expert_name, system_prompt in EXPERT_PROMPTS.items():
            user_content = f"議論テーマ: {topic}"
            if context:
                user_content += f"\n\nコンテキスト:\n{context}"
            if prev_opinions_text:
                user_content += f"\n\n他の専門家の意見:\n{prev_opinions_text}"

            raw = call_api(
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
                max_tokens=2048,
            )
            parsed = parse_json(raw, default={"position": raw})

            opinion = ExpertOpinion(
                expert=expert_name,
                position=parsed.get("position", ""),
                evidence=parsed.get("evidence", []),
                recommendations=parsed.get("recommendations", []),
                concerns=parsed.get("concerns", []),
                confidence=parsed.get("confidence", 0.5),
            )
            opinions.append(opinion)

            # 次の専門家に共有
            prev_opinions_text += f"\n{expert_name}: {opinion.position[:200]}"

        return opinions

    def _get_opinion(self, expert_name: str, topic: str, context: str) -> ExpertOpinion:
        """単一の専門家から意見を取得"""
        system_prompt = EXPERT_PROMPTS.get(expert_name, "")
        if not system_prompt:
            return ExpertOpinion(expert=expert_name, position="Unknown expert", evidence=[], recommendations=[], concerns=[], confidence=0.0)

        raw = call_api(
            system=system_prompt,
            messages=[{"role": "user", "content": f"議論テーマ: {topic}\n\nコンテキスト:\n{context}"}],
            max_tokens=2048,
        )
        parsed = parse_json(raw, default={"position": raw})

        return ExpertOpinion(
            expert=expert_name,
            position=parsed.get("position", ""),
            evidence=parsed.get("evidence", []),
            recommendations=parsed.get("recommendations", []),
            concerns=parsed.get("concerns", []),
            confidence=parsed.get("confidence", 0.5),
        )

    def _synthesize(self, topic: str, opinions: list[ExpertOpinion]) -> DebateResult:
        """全意見を統合して最終結果を生成"""
        opinions_text = "\n\n".join(
            f"=== {o.expert} ===\n"
            f"主張: {o.position}\n"
            f"根拠: {o.evidence}\n"
            f"推奨: {o.recommendations}\n"
            f"懸念: {o.concerns}\n"
            f"自信度: {o.confidence}"
            for o in opinions
        )

        raw = call_api(
            system=SYNTHESIS_PROMPT,
            messages=[{
                "role": "user",
                "content": f"テーマ: {topic}\n\n専門家の議論:\n{opinions_text}",
            }],
            max_tokens=4096,
        )
        parsed = parse_json(raw)

        return DebateResult(
            topic=topic,
            opinions=opinions,
            consensus=parsed.get("consensus", ""),
            action_plan=parsed.get("action_plan", []),
            priority_assets=parsed.get("priority_assets", []),
            estimated_monthly_revenue=parsed.get("estimated_monthly_revenue", 0),
            key_risks=parsed.get("key_risks", []),
        )

    def _save_debate(self, result: DebateResult) -> None:
        """議論結果を保存"""
        output_file = self.data_dir / f"{result.debate_id}.json"
        output_file.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
