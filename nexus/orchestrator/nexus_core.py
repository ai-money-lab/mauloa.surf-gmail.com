"""
NEXUS ORCHESTRATOR — 全体統括メタAI

全エンジンを統括し、自律的に収益を生み出し続ける最上位レイヤー。

完全自律ループ:
  CRAWL → TRY → DEBATE → EVOLVE → CRAWL → ...

AIが稼ぎ方を見つけ、実際にTRYし、失敗ならAI同士で議論し、
成功パターンを増殖させ、改善を繰り返す。

実行モード:
- single: 1サイクルだけ実行
- continuous: 連続サイクル実行
- swarm: 全エージェント一斉稼働
- full: 全モード統合実行（最強モード）
- autonomous: 完全自律ループ（CRAWL→TRY→DEBATE→EVOLVE）
"""

from __future__ import annotations

import json
import logging
import argparse
import signal
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus.alpha.engine import AlphaEngine, AlphaTask, TaskType
from nexus.omega.engine import OmegaEngine
from nexus.bridge.protocol import Bridge, CycleResult
from nexus.agents.swarm import AgentSwarm
from nexus.monetize.pipeline import MonetizePipeline
from nexus.crawler.opportunity_crawler import OpportunityCrawler
from nexus.factory.product_generator import ProductGenerator
from nexus.trial.trial_runner import TrialRunner, TrialMode, TrialResult
from nexus.debate.debate_engine import DebateEngine
from nexus.evolution.evolver import Evolver

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
    autonomous_loops: int = 0
    trials_run: int = 0
    trials_succeeded: int = 0
    debates_held: int = 0
    patterns_discovered: int = 0
    generation: int = 0
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
            "autonomous_loops": self.autonomous_loops,
            "trials_run": self.trials_run,
            "trials_succeeded": self.trials_succeeded,
            "debates_held": self.debates_held,
            "patterns_discovered": self.patterns_discovered,
            "generation": self.generation,
            "started_at": self.started_at,
            "last_updated": self.last_updated,
        }


class NexusOrchestrator:
    """
    NEXUS — 最上位オーケストレーター

    2つのAIが互いに稼ぎ続けるシステムの司令塔。

    完全自律ループ:
    1. CRAWL: AIが稼ぎ方を探索
    2. TRY: 実際に商品を生成して評価
    3. DEBATE: 失敗ならAI同士で議論
    4. EVOLVE: 成功パターンを増殖・改善
    5. → 1に戻る（永続ループ）
    """

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path("nexus/data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 既存エンジン
        self.alpha = AlphaEngine(data_dir=self.data_dir / "alpha")
        self.omega = OmegaEngine(data_dir=self.data_dir / "omega")
        self.bridge = Bridge(alpha=self.alpha, omega=self.omega, data_dir=self.data_dir / "bridge")
        self.swarm = AgentSwarm(data_dir=self.data_dir / "agents")
        self.monetize = MonetizePipeline(data_dir=self.data_dir / "monetize")

        # 新エンジン: 自律収益ループ
        self.crawler = OpportunityCrawler(data_dir=self.data_dir / "crawler")
        self.factory = ProductGenerator(data_dir=self.data_dir / "factory")
        self.trial = TrialRunner(factory=self.factory, data_dir=self.data_dir / "trial")
        self.debate = DebateEngine(data_dir=self.data_dir / "debate")
        self.evolver = Evolver(data_dir=self.data_dir / "evolution")

        self.state = NexusState()
        self._load_state()

        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """シグナルを受けて安全にシャットダウン"""
        logger.warning("Shutdown signal received (%s). Saving state...", signum)
        self._save_state()
        logger.info("State saved. Exiting.")
        raise SystemExit(0)

    def run(self, mode: str = "full", market_context: str = "", num_cycles: int = 3) -> dict[str, Any]:
        """メイン実行エントリーポイント"""
        logger.info("=" * 60)
        logger.info("NEXUS ORCHESTRATOR — Mode: %s", mode)
        logger.info("=" * 60)

        if mode == "single":
            return self._run_single_cycle(market_context)
        elif mode == "continuous":
            return self._run_continuous(market_context, num_cycles)
        elif mode == "swarm":
            return self._run_swarm(market_context)
        elif mode == "full":
            return self._run_full(market_context, num_cycles)
        elif mode == "autonomous":
            return self._run_autonomous(market_context, num_cycles)
        elif mode == "crawl":
            return self._run_crawl(market_context)
        elif mode == "trial":
            return self._run_trial(market_context)
        elif mode == "evolve":
            return self._run_evolve()
        else:
            return {"error": f"Unknown mode: {mode}"}

    # ─── 自律ループ（新コア） ───

    def _run_autonomous(self, market_context: str, num_loops: int) -> dict[str, Any]:
        """
        完全自律ループ: CRAWL → TRY → DEBATE → EVOLVE

        AIが自分で稼ぎ方を見つけ、試し、議論し、成功を増殖させる。
        """
        logger.info("=== AUTONOMOUS MODE: CRAWL → TRY → DEBATE → EVOLVE ===")
        all_results: dict[str, Any] = {"mode": "autonomous", "loops": []}

        for loop_num in range(1, num_loops + 1):
            logger.info("--- Loop %d/%d ---", loop_num, num_loops)
            loop_result: dict[str, Any] = {"loop": loop_num}

            # Step 1: CRAWL — 稼ぎ方を探索
            logger.info("Step 1: CRAWL — 稼ぎ方を探索")
            opportunities = self.crawler.crawl(market_context=market_context)
            self.crawler.evaluate(opportunities)
            top_opps = self.crawler.get_top_opportunities(limit=3)

            loop_result["crawl"] = {
                "opportunities_found": len(opportunities),
                "top_opportunities": [o.to_dict() for o in top_opps],
            }
            self.state.total_opportunities += len(opportunities)

            # Step 2: TRY — 実際に試す
            logger.info("Step 2: TRY — %d件をTRY", len(top_opps))
            trials = self.trial.run_batch(top_opps, mode=TrialMode.DRY_RUN)
            self.state.trials_run += len(trials)

            successes = [t for t in trials if t.result == TrialResult.SUCCESS]
            failures = [t for t in trials if t.debate_requested]
            self.state.trials_succeeded += len(successes)

            loop_result["trial"] = {
                "trials_run": len(trials),
                "successes": len(successes),
                "failures": len(failures),
                "stats": self.trial.get_stats(),
            }

            # Step 3: DEBATE — 失敗をAI同士で議論
            debate_results = []
            retry_results = []
            if failures:
                logger.info("Step 3: DEBATE — %d件をAI同士で議論", len(failures))
                for failed_trial in failures[:2]:  # 最大2件を議論
                    debate_result = self.debate.debate(failed_trial)
                    debate_results.append(debate_result)
                    self.state.debates_held += 1

                    # 議論の結果、再挑戦すべきなら再TRY
                    if debate_result.should_retry:
                        improvements = debate_result.improvements
                        retry = self.trial.retry_trial(
                            failed_trial.trial_id,
                            improvements=improvements,
                        )
                        if retry:
                            retry_results.append(retry)
                            if retry.result == TrialResult.SUCCESS:
                                successes.append(retry)
                                self.state.trials_succeeded += 1

            loop_result["debate"] = {
                "debates_held": len(debate_results),
                "retries": len(retry_results),
                "retry_successes": len([r for r in retry_results if r.result == TrialResult.SUCCESS]),
            }

            # Step 4: EVOLVE — 成功パターンを増殖
            new_patterns = []
            replicated_opps = []
            if successes:
                logger.info("Step 4: EVOLVE — %d件の成功パターンを増殖", len(successes))
                for success in successes:
                    pattern = self.evolver.extract_pattern(success)
                    if pattern:
                        new_patterns.append(pattern)
                        self.state.patterns_discovered += 1

                        # 横展開
                        new_opps = self.evolver.replicate(pattern)
                        replicated_opps.extend(new_opps)

                # 世代を進化させる
                gen = self.evolver.evolve()
                self.state.generation = gen.gen_number

            loop_result["evolve"] = {
                "new_patterns": len(new_patterns),
                "replicated_opportunities": len(replicated_opps),
                "generation": self.state.generation,
                "evolution_stats": self.evolver.get_evolution_stats(),
            }

            # 横展開された機会を次のループのCrawlerに追加
            self.crawler.opportunities.extend(replicated_opps)

            # Step 5: 成果物を収益化パイプラインに投入
            successful_products = [
                s.product for s in successes
                if s.product is not None
            ]
            if successful_products:
                from nexus.alpha.engine import AlphaOutput, OutputQuality
                mock_outputs = [
                    AlphaOutput(
                        task_type=TaskType.SERVICE,
                        content=p.description,
                        quality=OutputQuality.FINAL,
                        revenue_potential=float(p.price),
                    )
                    for p in successful_products
                ]
                deals = self.monetize.convert_to_deals(mock_outputs)
                self.state.total_deals += len(deals)
                loop_result["monetize"] = {"deals_created": len(deals)}

            self.state.autonomous_loops += 1
            self.state.update()
            all_results["loops"].append(loop_result)

            # Memory management: keep only last 20 loop results in memory
            if len(all_results["loops"]) > 20:
                all_results["loops"] = all_results["loops"][-20:]

        all_results["state"] = self.state.to_dict()
        all_results["trial_stats"] = self.trial.get_stats()
        all_results["evolution_stats"] = self.evolver.get_evolution_stats()

        self._save_state()
        self._save_full_report(all_results)

        logger.info("=== AUTONOMOUS MODE COMPLETE ===")
        logger.info("Loops: %d | Trials: %d | Successes: %d | Patterns: %d",
                    num_loops, self.state.trials_run, self.state.trials_succeeded, self.state.patterns_discovered)

        return all_results

    def _run_crawl(self, market_context: str) -> dict[str, Any]:
        """クロールのみ実行"""
        logger.info("--- Crawl Only ---")
        opportunities = self.crawler.crawl(market_context=market_context)
        evaluated = self.crawler.evaluate(opportunities)
        top = self.crawler.get_top_opportunities(limit=5)

        self.state.total_opportunities += len(opportunities)
        self.state.update()
        self._save_state()

        return {
            "mode": "crawl",
            "opportunities_found": len(opportunities),
            "top_opportunities": [o.to_dict() for o in top],
            "evaluation": evaluated,
            "state": self.state.to_dict(),
        }

    def _run_trial(self, market_context: str) -> dict[str, Any]:
        """既存の機会でTrialを実行"""
        logger.info("--- Trial Mode ---")
        top_opps = self.crawler.get_top_opportunities(limit=3)
        if not top_opps:
            # 機会がなければまずクロール
            top_opps = self.crawler.crawl(market_context=market_context)[:3]

        trials = self.trial.run_batch(top_opps)
        self.state.trials_run += len(trials)
        self.state.trials_succeeded += len([t for t in trials if t.result == TrialResult.SUCCESS])
        self.state.update()
        self._save_state()

        return {
            "mode": "trial",
            "trials": [t.to_dict() for t in trials],
            "stats": self.trial.get_stats(),
            "state": self.state.to_dict(),
        }

    def _run_evolve(self) -> dict[str, Any]:
        """進化のみ実行"""
        logger.info("--- Evolve Mode ---")
        gen = self.evolver.evolve()
        self.state.generation = gen.gen_number
        self.state.update()
        self._save_state()

        return {
            "mode": "evolve",
            "generation": gen.to_dict(),
            "top_patterns": [p.to_dict() for p in self.evolver.get_top_patterns()],
            "stats": self.evolver.get_evolution_stats(),
            "state": self.state.to_dict(),
        }

    # ─── 既存モード（維持） ───

    def _run_single_cycle(self, market_context: str) -> dict[str, Any]:
        """1サイクル実行: ALPHA生成 → OMEGA分析 → フィードバック → 改善"""
        logger.info("--- Single Cycle ---")
        result = self.bridge.run_cycle(market_context=market_context)
        self._process_cycle_result(result)
        return {"mode": "single", "cycle": result.to_dict(), "state": self.state.to_dict()}

    def _run_continuous(self, market_context: str, num_cycles: int) -> dict[str, Any]:
        """連続サイクル: ALPHA-OMEGAが止まらずにループ"""
        logger.info("--- Continuous: %d cycles ---", num_cycles)
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
        logger.info("Step 3: ALPHA-OMEGA Loop — %d cycles", num_cycles)
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
        logger.info("Total Revenue Potential: %.0f", self.state.total_revenue_potential)
        logger.info("Total Deals: %d", self.state.total_deals)
        logger.info("Total Outputs: %d", self.state.total_outputs)

        return all_results

    # ─── 内部ヘルパー ───

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
            self.state.autonomous_loops = data.get("autonomous_loops", 0)
            self.state.trials_run = data.get("trials_run", 0)
            self.state.trials_succeeded = data.get("trials_succeeded", 0)
            self.state.debates_held = data.get("debates_held", 0)
            self.state.patterns_discovered = data.get("patterns_discovered", 0)
            self.state.generation = data.get("generation", 0)
            self.state.started_at = data.get("started_at", self.state.started_at)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error("Failed to load state from %s: %s. Starting fresh.", state_file, e)

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
    parser = argparse.ArgumentParser(description="NEXUS — Dual-AI Autonomous Revenue Engine")
    parser.add_argument(
        "--mode",
        choices=["single", "continuous", "swarm", "full", "autonomous", "crawl", "trial", "evolve"],
        default="autonomous",
        help="Execution mode",
    )
    parser.add_argument("--cycles", type=int, default=3, help="Number of cycles/loops")
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
