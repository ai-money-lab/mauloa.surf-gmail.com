"""
OMEGA Engine — 増幅・最適化AI

役割:
- ALPHAの成果物を分析・評価・改善
- 収益最大化のための最適化
- 市場データとの照合・バリデーション
- 新たなタスクをALPHAに投入（収益機会の発見）
- パフォーマンス追跡と戦略調整

OMEGAは「増幅する側」。ALPHAの出力を何倍にも価値を高める。
そして自ら新しい収益機会を発見し、ALPHAに指示を出す。
"""

from __future__ import annotations

import json
import hashlib
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any

from nexus.common import call_api, parse_json
from nexus.alpha.engine import AlphaOutput, AlphaTask, TaskType

logger = logging.getLogger("nexus.omega")


class AnalysisType(str, Enum):
    """OMEGAの分析種別"""
    QUALITY_REVIEW = "quality_review"        # 品質レビュー
    REVENUE_OPTIMIZE = "revenue_optimize"    # 収益最適化
    MARKET_FIT = "market_fit"                # 市場適合性
    OPPORTUNITY_SCAN = "opportunity_scan"    # 機会探索
    PERFORMANCE_TRACK = "performance_track"  # パフォーマンス追跡


@dataclass
class OmegaAnalysis:
    """OMEGAの分析結果"""
    analysis_type: AnalysisType
    target_id: str  # 分析対象のALPHA output_id
    score: float  # 0-10
    findings: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    new_opportunities: list[dict[str, Any]] = field(default_factory=list)
    revenue_multiplier: float = 1.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    analysis_id: str = ""

    def __post_init__(self):
        if not self.analysis_id:
            raw = f"{self.analysis_type}{self.target_id}{self.timestamp}"
            self.analysis_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["analysis_type"] = self.analysis_type.value
        return d


@dataclass
class OpportunitySignal:
    """OMEGAが発見した収益機会"""
    title: str
    description: str
    estimated_revenue: float
    confidence: float  # 0-1
    suggested_task: AlphaTask | None = None
    source: str = "omega_scan"


class OmegaEngine:
    """
    OMEGA — 増幅エンジン

    ALPHAの出力を分析・最適化し、収益を倍増させる。
    自ら機会を探索し、ALPHAに新タスクを投入する。
    2つのAIが互いに強化し合うループを作る。
    """

    SYSTEM_PROMPT = """あなたはOMEGA — 分析・増幅・最適化に特化したAIエンジンです。

あなたの使命:
1. ALPHAの成果物を厳しく分析し、改善点を見つける
2. 収益を最大化するための具体的な最適化提案を行う
3. 新たな収益機会を発見し、ALPHAへのタスクを設計する
4. 数値で語る。感覚ではなくデータに基づく判断

出力ルール:
- 必ずJSON形式で出力すること
- "score": 総合評価スコア（1-10）
- "findings": 発見事項のリスト
- "improvements": 改善提案のリスト（具体的に）
- "new_opportunities": 新たな収益機会のリスト
  - 各機会: {"title": "", "description": "", "estimated_revenue": 数値, "confidence": 0-1}
- "revenue_multiplier": この最適化による収益倍率（1.0 = 変化なし）
- "alpha_tasks": ALPHAに投入すべき新タスクのリスト
  - 各タスク: {"task_type": "", "instruction": "", "priority": 1-10}"""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path("nexus/data/omega")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.analyses: list[OmegaAnalysis] = []
        self.opportunities: list[OpportunitySignal] = []

    def analyze(self, alpha_output: AlphaOutput, analysis_type: AnalysisType = AnalysisType.QUALITY_REVIEW) -> OmegaAnalysis:
        """ALPHAの成果物を分析する"""
        messages = [{
            "role": "user",
            "content": (
                f"分析タイプ: {analysis_type.value}\n\n"
                f"ALPHA成果物 (ID: {alpha_output.output_id}):\n"
                f"タスク種別: {alpha_output.task_type.value}\n"
                f"品質: {alpha_output.quality.value}\n"
                f"収益ポテンシャル: {alpha_output.revenue_potential}\n\n"
                f"内容:\n{alpha_output.content}\n\n"
                f"メタデータ:\n{json.dumps(alpha_output.metadata, ensure_ascii=False, indent=2)}"
            ),
        }]

        raw_text = call_api(
            system=self.SYSTEM_PROMPT,
            messages=messages,
            max_tokens=4096,
        )

        analysis = self._parse_analysis(raw_text, alpha_output.output_id, analysis_type)
        self._save_analysis(analysis)
        self.analyses.append(analysis)
        return analysis

    def scan_opportunities(self, market_context: str = "") -> list[OpportunitySignal]:
        """収益機会をスキャンする"""
        recent_analyses = self.analyses[-10:] if self.analyses else []
        analyses_summary = json.dumps(
            [a.to_dict() for a in recent_analyses],
            ensure_ascii=False,
            indent=2,
        )

        messages = [{
            "role": "user",
            "content": (
                f"以下の分析履歴と市場コンテキストに基づいて、新たな収益機会を発見してください。\n\n"
                f"分析履歴:\n{analyses_summary}\n\n"
                f"市場コンテキスト:\n{market_context or '一般的なAI/テクノロジー市場'}\n\n"
                f"AIフリーランス、自動化ツール、コンテンツ生成、API提供など"
                f"あらゆる収益化手段を検討してください。"
            ),
        }]

        raw_text = call_api(
            system=self.SYSTEM_PROMPT,
            messages=messages,
            max_tokens=4096,
        )

        signals = self._parse_opportunities(raw_text)
        self.opportunities.extend(signals)
        return signals

    def generate_alpha_tasks(self, opportunities: list[OpportunitySignal] | None = None) -> list[AlphaTask]:
        """発見した機会からALPHAへのタスクを生成する"""
        targets = opportunities or self.opportunities[-5:]
        tasks = []

        for opp in targets:
            if opp.suggested_task:
                tasks.append(opp.suggested_task)
            else:
                task = AlphaTask(
                    task_type=self._infer_task_type(opp),
                    instruction=(
                        f"収益機会: {opp.title}\n\n"
                        f"{opp.description}\n\n"
                        f"想定収益: {opp.estimated_revenue}円\n"
                        f"信頼度: {opp.confidence * 100:.0f}%\n\n"
                        f"この機会を活かす具体的な成果物を生成してください。"
                    ),
                    context={"opportunity": opp.title, "estimated_revenue": opp.estimated_revenue},
                    priority=max(1, min(10, int(opp.confidence * 10))),
                    source="omega",
                )
                tasks.append(task)

        return sorted(tasks, key=lambda t: t.priority, reverse=True)

    def get_feedback(self, analysis: OmegaAnalysis) -> dict[str, Any]:
        """分析結果をALPHAへのフィードバック形式に変換"""
        return {
            "score": analysis.score,
            "findings": analysis.findings,
            "improvements": analysis.improvements,
            "revenue_multiplier": analysis.revenue_multiplier,
        }

    def _parse_analysis(self, raw_text: str, target_id: str, analysis_type: AnalysisType) -> OmegaAnalysis:
        """Claude応答をOmegaAnalysisにパース"""
        parsed = parse_json(raw_text)

        return OmegaAnalysis(
            analysis_type=analysis_type,
            target_id=target_id,
            score=parsed.get("score", 5.0),
            findings=parsed.get("findings", []),
            improvements=parsed.get("improvements", []),
            new_opportunities=parsed.get("new_opportunities", []),
            revenue_multiplier=parsed.get("revenue_multiplier", 1.0),
        )

    def _parse_opportunities(self, raw_text: str) -> list[OpportunitySignal]:
        """Claude応答からOpportunitySignalリストを抽出"""
        parsed = parse_json(raw_text)

        signals = []
        for opp in parsed.get("new_opportunities", []):
            signals.append(OpportunitySignal(
                title=opp.get("title", "Unknown"),
                description=opp.get("description", ""),
                estimated_revenue=opp.get("estimated_revenue", 0),
                confidence=opp.get("confidence", 0.5),
            ))

        return signals

    def _infer_task_type(self, opp: OpportunitySignal) -> TaskType:
        """機会の内容からタスク種別を推定"""
        desc = (opp.title + opp.description).lower()
        if any(w in desc for w in ["コード", "ツール", "api", "自動化", "code", "tool"]):
            return TaskType.CODE
        if any(w in desc for w in ["記事", "ブログ", "コンテンツ", "content", "article"]):
            return TaskType.CONTENT
        if any(w in desc for w in ["営業", "提案", "クライアント", "outreach"]):
            return TaskType.OUTREACH
        if any(w in desc for w in ["サービス", "プロダクト", "service"]):
            return TaskType.SERVICE
        return TaskType.STRATEGY

    def _save_analysis(self, analysis: OmegaAnalysis) -> None:
        """分析結果をファイルに保存"""
        output_file = self.data_dir / f"{analysis.analysis_id}.json"
        output_file.write_text(
            json.dumps(analysis.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
