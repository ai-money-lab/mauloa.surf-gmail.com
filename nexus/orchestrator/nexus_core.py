"""
NEXUS ORCHESTRATOR — 全体統括メタAI

全エンジンを統括し、自律的に収益を生み出し続ける最上位レイヤー。

ALPHA（創造） + OMEGA（増幅） + BRIDGE（協議） + AGENTS（並列分担） + MONETIZE（収益化）
 ↑ 全てをこのOrchestatorが制御する ↑

実行モード:
- single: 1サイクルだけ実行
- continuous: 連続サイクル実行
- swarm: 全エージェント一斉稼働
- full: 全モード統合実行（最強モード）
"""

from __future__ import annotations

import json
import logging
import argparse
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus.alpha.engine import AlphaEngine, AlphaTask, TaskType
from nexus.omega.engine import OmegaEngine
from nexus.bridge.protocol import Bridge, CycleResult
from nexus.agents.swarm import AgentSwarm
from nexus.monetize.pipeline import MonetizePipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("nexus.orchestrator")


@dataclass
class NexusState:
    """NEXUSの全体状態"""
    cycles_completed: int = 0
    total_revenue_potential: float = 0.0
    total_outputs: int = 0
    total_deals: int = 0
    total_opportunities: int = 0
    agent_sweeps: int = 0
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated: str = ""

    def update(self):
        self.last_updated = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "cycles_completed": self.cycles_completed,
            "total_revenue_potential": self.total_revenue_potential,
            "total_outputs": self.total_outputs,
            "total_deals": self.total_deals,
            "total_opportunities": self.total_opportunities,
            "agent_sweeps": self.agent_sweeps,
            "started_at": self.started_at,
            "last_updated": self.last_updated,
        }


class NexusOrchestrator:
    """
    NEXUS — 最上位オーケストレーター

    2つのClaudeCodeが互いに稼ぎ続けるシステムの司令塔。
    ALPHA-OMEGAのループ + AGENTの並列稼働 + 収益パイプライン
    全てを統合して自律的に回し続ける。
    """

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path("nexus/data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 各エンジン初期化
        self.alpha = AlphaEngine(data_dir=self.data_dir / "alpha")
        self.omega = OmegaEngine(data_dir=self.data_dir / "omega")
        self.bridge = Bridge(alpha=self.alpha, omega=self.omega, data_dir=self.data_dir / "bridge")
        self.swarm = AgentSwarm(data_dir=self.data_dir / "agents")
        self.monetize = MonetizePipeline(data_dir=self.data_dir / "monetize")

        self.state = NexusState()
        self._load_state()

    def run(self, mode: str = "full", market_context: str = "", num_cycles: int = 3) -> dict[str, Any]:
        """メイン実行エントリーポイント"""
        logger.info(f"{'='*60}")
        logger.info(f"NEXUS ORCHESTRATOR — Mode: {mode}")
        logger.info(f"{'='*60}")

        if mode == "single":
            return self._run_single_cycle(market_context)
        elif mode == "continuous":
            return self._run_continuous(market_context, num_cycles)
        elif mode == "swarm":
            return self._run_swarm(market_context)
        elif mode == "full":
            return self._run_full(market_context, num_cycles)
        else:
            return {"error": f"Unknown mode: {mode}"}

    def _run_single_cycle(self, market_context: str) -> dict[str, Any]:
        """1サイクル実行: ALPHA生成 → OMEGA分析 → フィードバック → 改善"""
        logger.info("--- Single Cycle ---")
        result = self.bridge.run_cycle(market_context=market_context)
        self._process_cycle_result(result)
        return {"mode": "single", "cycle": result.to_dict(), "state": self.state.to_dict()}

    def _run_continuous(self, market_context: str, num_cycles: int) -> dict[str, Any]:
        """連続サイクル: ALPHA-OMEGAが止まらずにループ"""
        logger.info(f"--- Continuous: {num_cycles} cycles ---")
        results = self.bridge.run_continuous(num_cycles=num_cycles, market_context=market_context)

        for result in results:
            self._process_cycle_result(result)

        return {
            "mode": "continuous",
            "cycles": [r.to_dict() for r in results],
            "performance": self.bridge.get_performance_summary(),
            "state": self.state.to_dict(),
        }

    def _run_swarm(self, market_context: str) -> dict[str, Any]:
        """全エージェント一斉稼働"""
        logger.info("--- Agent Swarm ---")
        results = self.swarm.full_sweep(market_context=market_context)
        synthesis = self.swarm.synthesize(results)

        self.state.agent_sweeps += 1
        self.state.update()
        self._save_state()

        return {
            "mode": "swarm",
            "agent_results": [r.to_dict() for r in results],
            "synthesis": synthesis,
            "state": self.state.to_dict(),
        }

    def _run_full(self, market_context: str, num_cycles: int) -> dict[str, Any]:
        """フルモード: 全システム統合実行（最強）"""
        logger.info("=== FULL MODE: EVERYTHING ===")
        all_results = {}

        # Step 1: エージェント群で市場スキャン
        logger.info("Step 1: Agent Swarm — Market Scan")
        swarm_results = self.swarm.full_sweep(market_context=market_context)
        swarm_synthesis = self.swarm.synthesize(swarm_results)
        all_results["swarm"] = {
            "results": [r.to_dict() for r in swarm_results],
            "synthesis": swarm_synthesis,
        }

        # Step 2: スキャン結果からALPHAタスクを生成
        logger.info("Step 2: Generate tasks from swarm findings")
        alpha_tasks = self._swarm_to_alpha_tasks(swarm_synthesis)

        # Step 3: ALPHA-OMEGAの連続ループ
        logger.info(f"Step 3: ALPHA-OMEGA Loop — {num_cycles} cycles")
        cycle_results = []
        for i in range(num_cycles):
            tasks = alpha_tasks if i == 0 else None
            cycle = self.bridge.run_cycle(initial_tasks=tasks, market_context=market_context)
            self._process_cycle_result(cycle)
            cycle_results.append(cycle)

        all_results["cycles"] = [r.to_dict() for r in cycle_results]

        # Step 4: 成果物を収益化パイプラインに投入
        logger.info("Step 4: Monetize — Convert to deals")
        all_outputs = []
        for cycle in cycle_results:
            all_outputs.extend(cycle.outputs)
        if all_outputs:
            deals = self.monetize.convert_to_deals(all_outputs)
            all_results["deals"] = [d.to_dict() for d in deals]
            self.state.total_deals += len(deals)

        # Step 5: 収益レポート
        logger.info("Step 5: Revenue Report")
        report = self.monetize.get_revenue_report()
        all_results["revenue_report"] = {
            "total_estimated": report.total_estimated,
            "total_actual": report.total_actual,
            "by_channel": report.deals_by_channel,
            "by_status": report.deals_by_status,
            "pipeline_health": report.pipeline_health,
        }

        all_results["state"] = self.state.to_dict()
        all_results["mode"] = "full"

        self._save_state()
        self._save_full_report(all_results)

        logger.info("=== FULL MODE COMPLETE ===")
        logger.info(f"Total Revenue Potential: {self.state.total_revenue_potential:.0f}")
        logger.info(f"Total Deals: {self.state.total_deals}")
        logger.info(f"Total Outputs: {self.state.total_outputs}")

        return all_results

    def _process_cycle_result(self, result: CycleResult) -> None:
        """サイクル結果を状態に反映"""
        self.state.cycles_completed += 1
        self.state.total_revenue_potential += result.total_revenue_potential
        self.state.total_outputs += len(result.outputs)
        self.state.total_opportunities += len(result.opportunities)
        self.state.update()

    def _swarm_to_alpha_tasks(self, synthesis: dict[str, Any]) -> list[AlphaTask]:
        """Swarm統合結果からALPHAタスクを生成"""
        tasks = []

        # priority_actionsから
        for action in synthesis.get("priority_actions", [])[:3]:
            if isinstance(action, dict):
                instruction = action.get("action", action.get("description", str(action)))
            else:
                instruction = str(action)

            tasks.append(AlphaTask(
                task_type=TaskType.STRATEGY,
                instruction=instruction,
                context={"source": "swarm_synthesis"},
                priority=9,
                source="orchestrator",
            ))

        # タスクが空なら汎用タスクを追加
        if not tasks:
            tasks.append(AlphaTask(
                task_type=TaskType.STRATEGY,
                instruction=(
                    "エージェント群の分析に基づき、最も収益性の高い"
                    "アクションプランを作成してください。"
                ),
                priority=8,
                source="orchestrator",
            ))

        return tasks

    def _save_state(self) -> None:
        """状態を保存"""
        state_file = self.data_dir / "nexus_state.json"
        state_file.write_text(
            json.dumps(self.state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_state(self) -> None:
        """状態を読み込み"""
        state_file = self.data_dir / "nexus_state.json"
        if not state_file.exists():
            return
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            self.state.cycles_completed = data.get("cycles_completed", 0)
            self.state.total_revenue_potential = data.get("total_revenue_potential", 0)
            self.state.total_outputs = data.get("total_outputs", 0)
            self.state.total_deals = data.get("total_deals", 0)
            self.state.total_opportunities = data.get("total_opportunities", 0)
            self.state.agent_sweeps = data.get("agent_sweeps", 0)
            self.state.started_at = data.get("started_at", self.state.started_at)
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to load state, starting fresh")

    def _save_full_report(self, report: dict[str, Any]) -> None:
        """フルレポートを保存"""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_file = self.data_dir / f"full_report_{ts}.json"
        report_file.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )


def main():
    """CLIエントリーポイント"""
    parser = argparse.ArgumentParser(description="NEXUS — Dual-AI Revenue Engine")
    parser.add_argument(
        "--mode",
        choices=["single", "continuous", "swarm", "full"],
        default="full",
        help="Execution mode",
    )
    parser.add_argument("--cycles", type=int, default=3, help="Number of cycles (for continuous/full)")
    parser.add_argument("--market", type=str, default="", help="Market context")
    args = parser.parse_args()

    orchestrator = NexusOrchestrator()
    result = orchestrator.run(mode=args.mode, market_context=args.market, num_cycles=args.cycles)

    print("\n" + "=" * 60)
    print("NEXUS RESULT")
    print("=" * 60)
    print(json.dumps(result.get("state", {}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
