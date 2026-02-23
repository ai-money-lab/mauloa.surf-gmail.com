"""
BRIDGE — ALPHA-OMEGA連続協議プロトコル

2つのAIエンジンが止まらずに協議し続ける仕組み。
ALPHAが生成 → OMEGAが分析 → OMEGAが新タスク生成 → ALPHAが実行 → 無限ループ

このループ自体が収益を生み出し続ける。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from nexus.alpha.engine import AlphaEngine, AlphaTask, AlphaOutput, TaskType
from nexus.omega.engine import OmegaEngine, OmegaAnalysis, AnalysisType, OpportunitySignal

logger = logging.getLogger("nexus.bridge")


class CyclePhase(str, Enum):
    """サイクルのフェーズ"""
    ALPHA_CREATE = "alpha_create"        # ALPHAが生成
    OMEGA_ANALYZE = "omega_analyze"      # OMEGAが分析
    OMEGA_FEEDBACK = "omega_feedback"    # OMEGAがフィードバック
    ALPHA_IMPROVE = "alpha_improve"      # ALPHAが改善
    OMEGA_SCAN = "omega_scan"            # OMEGAが機会探索
    ALPHA_EXECUTE = "alpha_execute"      # ALPHAが新タスク実行


@dataclass
class CycleResult:
    """1サイクルの結果"""
    cycle_number: int
    outputs: list[AlphaOutput] = field(default_factory=list)
    analyses: list[OmegaAnalysis] = field(default_factory=list)
    opportunities: list[OpportunitySignal] = field(default_factory=list)
    new_tasks_generated: int = 0
    total_revenue_potential: float = 0.0
    phases_completed: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "cycle_number": self.cycle_number,
            "outputs_count": len(self.outputs),
            "analyses_count": len(self.analyses),
            "opportunities_count": len(self.opportunities),
            "new_tasks_generated": self.new_tasks_generated,
            "total_revenue_potential": self.total_revenue_potential,
            "phases_completed": self.phases_completed,
            "timestamp": self.timestamp,
        }


class Bridge:
    """
    BRIDGE — ALPHA-OMEGA連続協議エンジン

    2つのAIが止まらずに以下のループを回す:
    1. ALPHA: 成果物を生成
    2. OMEGA: 分析・評価
    3. OMEGA: フィードバック → ALPHAが改善
    4. OMEGA: 新しい機会をスキャン
    5. OMEGA: ALPHAへの新タスクを生成
    6. ALPHA: 新タスクを実行
    7. → 1に戻る
    """

    def __init__(
        self,
        alpha: AlphaEngine | None = None,
        omega: OmegaEngine | None = None,
        data_dir: Path | None = None,
    ):
        self.alpha = alpha or AlphaEngine()
        self.omega = omega or OmegaEngine()
        self.data_dir = data_dir or Path("nexus/data/bridge")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cycle_count = 0
        self.results: list[CycleResult] = []

    def run_cycle(self, initial_tasks: list[AlphaTask] | None = None, market_context: str = "") -> CycleResult:
        """1サイクルを実行する"""
        self.cycle_count += 1
        result = CycleResult(cycle_number=self.cycle_count)
        logger.info(f"=== NEXUS Cycle {self.cycle_count} START ===")

        # Phase 1: ALPHA生成
        tasks = initial_tasks or self._generate_seed_tasks()
        logger.info(f"Phase 1: ALPHA generating {len(tasks)} outputs")
        outputs = self.alpha.execute_batch(tasks)
        result.outputs.extend(outputs)
        result.phases_completed.append(CyclePhase.ALPHA_CREATE.value)

        # Phase 2: OMEGA分析
        logger.info(f"Phase 2: OMEGA analyzing {len(outputs)} outputs")
        for output in outputs:
            analysis = self.omega.analyze(output, AnalysisType.QUALITY_REVIEW)
            result.analyses.append(analysis)

            # Phase 3: スコアが低い場合はフィードバック→改善
            if analysis.score < 7:
                logger.info(f"Phase 3: Feedback loop for {output.output_id} (score: {analysis.score})")
                feedback = self.omega.get_feedback(analysis)
                improved = self.alpha.receive_feedback(output.output_id, feedback)
                if improved:
                    result.outputs.append(improved)
                result.phases_completed.append(CyclePhase.OMEGA_FEEDBACK.value)
                result.phases_completed.append(CyclePhase.ALPHA_IMPROVE.value)

        result.phases_completed.append(CyclePhase.OMEGA_ANALYZE.value)

        # Phase 4: OMEGA機会探索
        logger.info("Phase 4: OMEGA scanning for opportunities")
        opportunities = self.omega.scan_opportunities(market_context)
        result.opportunities.extend(opportunities)
        result.phases_completed.append(CyclePhase.OMEGA_SCAN.value)

        # Phase 5: 新タスク生成 → ALPHA実行
        if opportunities:
            new_tasks = self.omega.generate_alpha_tasks(opportunities)
            result.new_tasks_generated = len(new_tasks)

            if new_tasks:
                logger.info(f"Phase 5: ALPHA executing {len(new_tasks)} new tasks from OMEGA")
                top_tasks = new_tasks[:3]  # 上位3つに絞る
                new_outputs = self.alpha.execute_batch(top_tasks)
                result.outputs.extend(new_outputs)
                result.phases_completed.append(CyclePhase.ALPHA_EXECUTE.value)

        # 収益ポテンシャル集計
        result.total_revenue_potential = sum(o.revenue_potential for o in result.outputs)

        # 保存
        self._save_cycle_result(result)
        self.results.append(result)

        logger.info(
            f"=== NEXUS Cycle {self.cycle_count} END === "
            f"Outputs: {len(result.outputs)}, "
            f"Revenue Potential: {result.total_revenue_potential:.0f}"
        )
        return result

    def run_continuous(self, num_cycles: int = 3, market_context: str = "") -> list[CycleResult]:
        """複数サイクルを連続実行する"""
        all_results = []

        for i in range(num_cycles):
            # 前サイクルの結果から次のタスクを導出
            if all_results and all_results[-1].opportunities:
                next_tasks = self.omega.generate_alpha_tasks(all_results[-1].opportunities)
            else:
                next_tasks = None

            result = self.run_cycle(initial_tasks=next_tasks, market_context=market_context)
            all_results.append(result)

        return all_results

    def get_performance_summary(self) -> dict[str, Any]:
        """全サイクルのパフォーマンスサマリー"""
        if not self.results:
            return {"cycles": 0, "message": "No cycles executed yet"}

        total_outputs = sum(len(r.outputs) for r in self.results)
        total_analyses = sum(len(r.analyses) for r in self.results)
        total_opportunities = sum(len(r.opportunities) for r in self.results)
        total_revenue = sum(r.total_revenue_potential for r in self.results)
        total_new_tasks = sum(r.new_tasks_generated for r in self.results)

        return {
            "cycles_completed": len(self.results),
            "total_outputs": total_outputs,
            "total_analyses": total_analyses,
            "total_opportunities_found": total_opportunities,
            "total_new_tasks_generated": total_new_tasks,
            "total_revenue_potential": total_revenue,
            "avg_revenue_per_cycle": total_revenue / len(self.results),
            "latest_cycle": self.results[-1].to_dict(),
        }

    def _generate_seed_tasks(self) -> list[AlphaTask]:
        """初回サイクル用のシードタスクを生成"""
        return [
            AlphaTask(
                task_type=TaskType.STRATEGY,
                instruction=(
                    "AIを活用した収益化の戦略を立案してください。\n"
                    "以下の領域をカバーすること:\n"
                    "1. AIフリーランスとしての案件獲得\n"
                    "2. 自動化ツール/APIの開発と販売\n"
                    "3. コンテンツ生成と収益化\n"
                    "4. AI活用コンサルティング\n"
                    "具体的なアクションプランを含めてください。"
                ),
                priority=10,
                source="bridge",
            ),
            AlphaTask(
                task_type=TaskType.ANALYSIS,
                instruction=(
                    "2025-2026年のAI市場で最も収益性の高い機会を分析してください。\n"
                    "個人/小規模チームがすぐに取り組めるものに絞ること。\n"
                    "各機会について、想定月収、難易度、開始までの期間を示してください。"
                ),
                priority=9,
                source="bridge",
            ),
        ]

    def _save_cycle_result(self, result: CycleResult) -> None:
        """サイクル結果を保存"""
        output_file = self.data_dir / f"cycle_{result.cycle_number:04d}.json"
        output_file.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
