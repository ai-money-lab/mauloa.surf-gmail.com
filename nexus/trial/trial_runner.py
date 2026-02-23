"""
TRIAL RUNNER — 稼げるかどうか実際にTRYする

フロー:
1. Crawlerが発見した機会を受け取る
2. Factoryで商品/成果物を実際に生成する
3. 結果を評価（品質、市場適合性、収益性）
4. 成功/失敗を判定しCrawlerにフィードバック
5. 失敗の場合 → Debateエンジンで原因分析 → 再挑戦

TRYの種類:
- DRY RUN: 商品を生成して評価だけ（出品はしない）
- SOFT LAUNCH: 小規模で出品テスト
- FULL LAUNCH: 本格出品
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from nexus.crawler.opportunity_crawler import Opportunity
from nexus.factory.product_generator import (
    ProductGenerator, Product, ProductCategory, ProductStatus,
)


class TrialMode(str, Enum):
    """試行モード"""
    DRY_RUN = "dry_run"           # 生成・評価のみ
    SOFT_LAUNCH = "soft_launch"   # 小規模テスト
    FULL_LAUNCH = "full_launch"   # 本格出品


class TrialResult(str, Enum):
    """試行結果"""
    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL = "partial"     # 部分的成功
    FAILURE = "failure"
    NEEDS_DEBATE = "needs_debate"  # AI議論が必要


@dataclass
class Trial:
    """1回の試行"""
    opportunity: Opportunity
    mode: TrialMode
    result: TrialResult
    product: Product | None = None
    evaluation: dict[str, Any] = field(default_factory=dict)
    revenue_actual: int = 0
    lessons: list[str] = field(default_factory=list)
    debate_requested: bool = False
    retry_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = ""
    trial_id: str = ""

    def __post_init__(self):
        if not self.trial_id:
            raw = f"{self.opportunity.opp_id}{self.mode}{self.created_at}"
            self.trial_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "trial_id": self.trial_id,
            "opportunity_id": self.opportunity.opp_id,
            "opportunity_title": self.opportunity.title,
            "mode": self.mode.value,
            "result": self.result.value,
            "product_id": self.product.product_id if self.product else None,
            "evaluation": self.evaluation,
            "revenue_actual": self.revenue_actual,
            "lessons": self.lessons,
            "debate_requested": self.debate_requested,
            "retry_count": self.retry_count,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


EVALUATION_PROMPT = """あなたは厳格な品質・市場適合性の評価者です。

以下の「収益機会」に対して生成された「商品」を評価してください。

評価基準（各10点満点）:
1. 市場適合性: ターゲット層が本当に買うか
2. 品質: 即座に販売可能な品質か
3. 差別化: 競合と比べて独自性はあるか
4. 価格妥当性: この値段で売れるか
5. スケーラビリティ: 量産・横展開が可能か

出力（JSON）:
- "scores": {"market_fit": 1-10, "quality": 1-10, "differentiation": 1-10, "pricing": 1-10, "scalability": 1-10}
- "total_score": 合計（50点満点）
- "verdict": "success" / "partial" / "failure" / "needs_debate"
- "strengths": 強み（リスト）
- "weaknesses": 弱み（リスト）
- "improvements": 改善提案（リスト）
- "would_you_buy": あなたがターゲット層なら買うか（true/false + 理由）"""


OPP_TO_CATEGORY = {
    "freelance_gig": "template_set",
    "digital_product": "prompt_pack",
    "api_service": "api_service",
    "content_monetize": "education",
    "automation_sell": "automation_script",
    "consulting": "template_set",
    "affiliate": "education",
}


class TrialRunner:
    """
    試行実行エンジン

    発見した機会を実際にTRYして、成功/失敗を判定する。
    失敗した場合はDebateエンジンへ送り、再挑戦する。
    """

    SUCCESS_THRESHOLD = 35  # 50点満点中35点以上で成功

    def __init__(self, factory: ProductGenerator | None = None, data_dir: Path | None = None):
        self.client = Anthropic()
        self.factory = factory or ProductGenerator()
        self.data_dir = data_dir or Path("nexus/data/trial")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.trials: list[Trial] = []

    def run_trial(self, opportunity: Opportunity, mode: TrialMode = TrialMode.DRY_RUN) -> Trial:
        """1つの機会をTRYする"""
        trial = Trial(
            opportunity=opportunity,
            mode=mode,
            result=TrialResult.PENDING,
        )

        # Step 1: 商品を生成
        category = self._opp_to_category(opportunity)
        product = self.factory.generate(
            theme=f"{opportunity.title}: {opportunity.description}",
            category=category,
            target_price=opportunity.estimated_revenue,
        )
        trial.product = product

        # Step 2: 品質・市場適合性を評価
        evaluation = self._evaluate(opportunity, product)
        trial.evaluation = evaluation

        # Step 3: 結果判定
        total_score = evaluation.get("total_score", 0)
        verdict = evaluation.get("verdict", "failure")

        if verdict == "success" or total_score >= self.SUCCESS_THRESHOLD:
            trial.result = TrialResult.SUCCESS
            trial.lessons = evaluation.get("strengths", [])
            product.status = ProductStatus.READY
        elif verdict == "partial" or total_score >= self.SUCCESS_THRESHOLD * 0.7:
            trial.result = TrialResult.PARTIAL
            trial.lessons = evaluation.get("improvements", [])
            trial.debate_requested = True
        elif verdict == "needs_debate":
            trial.result = TrialResult.NEEDS_DEBATE
            trial.debate_requested = True
            trial.lessons = evaluation.get("weaknesses", [])
        else:
            trial.result = TrialResult.FAILURE
            trial.debate_requested = True
            trial.lessons = evaluation.get("weaknesses", []) + evaluation.get("improvements", [])

        trial.completed_at = datetime.now(timezone.utc).isoformat()
        self.trials.append(trial)
        self._save_trial(trial)
        return trial

    def run_batch(self, opportunities: list[Opportunity], mode: TrialMode = TrialMode.DRY_RUN) -> list[Trial]:
        """複数の機会をバッチTRY"""
        # 優先度順にソート
        sorted_opps = sorted(opportunities, key=lambda o: o.priority_score, reverse=True)
        return [self.run_trial(opp, mode) for opp in sorted_opps]

    def retry_trial(self, trial_id: str, improvements: list[str] | None = None) -> Trial | None:
        """失敗したTrialを再挑戦する"""
        original = self._find_trial(trial_id)
        if not original:
            return None

        original.retry_count += 1

        # 改善指示を含めて再生成
        improvement_text = "\n".join(improvements or original.lessons)
        enhanced_description = (
            f"{original.opportunity.description}\n\n"
            f"前回の改善点:\n{improvement_text}"
        )

        # 機会の説明を改善して再TRY
        improved_opp = Opportunity(
            title=original.opportunity.title,
            opportunity_type=original.opportunity.opportunity_type,
            feasibility=original.opportunity.feasibility,
            estimated_revenue=original.opportunity.estimated_revenue,
            confidence=original.opportunity.confidence,
            description=enhanced_description,
            platform=original.opportunity.platform,
            competition_level=original.opportunity.competition_level,
            required_skills=original.opportunity.required_skills,
            action_steps=original.opportunity.action_steps,
            risks=original.opportunity.risks,
        )

        return self.run_trial(improved_opp, original.mode)

    def get_successes(self) -> list[Trial]:
        """成功したTrialのみ取得"""
        return [t for t in self.trials if t.result == TrialResult.SUCCESS]

    def get_failures_needing_debate(self) -> list[Trial]:
        """議論が必要な失敗Trial"""
        return [t for t in self.trials if t.debate_requested and t.result != TrialResult.SUCCESS]

    def get_success_rate(self) -> float:
        """成功率"""
        completed = [t for t in self.trials if t.result != TrialResult.PENDING]
        if not completed:
            return 0.0
        successes = [t for t in completed if t.result == TrialResult.SUCCESS]
        return len(successes) / len(completed)

    def get_stats(self) -> dict[str, Any]:
        """統計情報"""
        completed = [t for t in self.trials if t.result != TrialResult.PENDING]
        return {
            "total_trials": len(self.trials),
            "completed": len(completed),
            "successes": len([t for t in completed if t.result == TrialResult.SUCCESS]),
            "partials": len([t for t in completed if t.result == TrialResult.PARTIAL]),
            "failures": len([t for t in completed if t.result == TrialResult.FAILURE]),
            "needs_debate": len([t for t in completed if t.result == TrialResult.NEEDS_DEBATE]),
            "success_rate": self.get_success_rate(),
            "total_revenue": sum(t.revenue_actual for t in self.trials),
        }

    def _evaluate(self, opportunity: Opportunity, product: Product) -> dict:
        """商品を評価する"""
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=EVALUATION_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"=== 収益機会 ===\n"
                    f"タイトル: {opportunity.title}\n"
                    f"種別: {opportunity.opportunity_type.value}\n"
                    f"想定月収: {opportunity.estimated_revenue}円\n"
                    f"プラットフォーム: {opportunity.platform}\n"
                    f"競合レベル: {opportunity.competition_level}\n\n"
                    f"=== 生成された商品 ===\n"
                    f"商品名: {product.name}\n"
                    f"カテゴリ: {product.category.value}\n"
                    f"価格: {product.price}円\n"
                    f"説明: {product.description}\n"
                    f"内容（一部）:\n{product.content[:1000]}"
                ),
            }],
        )

        try:
            raw = response.content[0].text
            json_start = raw.find("{")
            json_end = raw.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(raw[json_start:json_end])
        except (json.JSONDecodeError, IndexError):
            pass
        return {"total_score": 0, "verdict": "failure"}

    def _opp_to_category(self, opp: Opportunity) -> ProductCategory:
        """機会から商品カテゴリを推定"""
        cat_str = OPP_TO_CATEGORY.get(opp.opportunity_type.value, "template_set")
        return ProductCategory(cat_str)

    def _find_trial(self, trial_id: str) -> Trial | None:
        """IDでTrialを検索"""
        for t in self.trials:
            if t.trial_id == trial_id:
                return t
        return None

    def _save_trial(self, trial: Trial) -> None:
        """Trial結果を保存"""
        output_file = self.data_dir / f"{trial.trial_id}.json"
        output_file.write_text(
            json.dumps(trial.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
