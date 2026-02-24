"""Orchestrator — System E の司令塔.

すべてのAIエージェントとサブシステムを統括し、
自律的な意思決定・実行・改善のサイクルを回す。

外部モジュール（core/）に依存せず、単体で動作する。

使い方:
    python -m system_e.orchestrator --mode debate --topic "投稿戦略の改善"
    python -m system_e.orchestrator --mode evolve
    python -m system_e.orchestrator --mode diagnose
    python -m system_e.orchestrator --mode full-cycle
"""

import argparse
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Callable, Optional

from system_e.client import ClaudeClient
from system_e.debate import DebateProtocol, QuickConsensus
from system_e.self_improve import EvolutionEngine
from system_e.meta_optimizer import MetaOptimizer

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
ORCHESTRATOR_LOG = Path(__file__).parent / "data" / "orchestrator_log.jsonl"


class Orchestrator:
    """The brain of System E — coordinates all meta-intelligence activities.

    Modes:
        debate:     Multi-agent debate on a specific topic
        quick:      Quick 2-agent consensus (Strategist + Critic)
        evolve:     Self-improvement cycle based on performance data
        diagnose:   Full system health diagnosis
        optimize:   Optimize system interactions
        full-cycle: Run everything in sequence

    Args:
        claude_client: Optional pre-configured ClaudeClient.
        on_notify: Optional callback for notifications (replaces core.notifier).
            Signature: (message: str) -> None
    """

    def __init__(
        self,
        claude_client: Optional[ClaudeClient] = None,
        on_notify: Optional[Callable[[str], None]] = None,
    ):
        self.claude = claude_client or ClaudeClient()
        self.debate = DebateProtocol(claude_client=self.claude)
        self.quick = QuickConsensus(claude_client=self.claude)
        self.evolution = EvolutionEngine(claude_client=self.claude)
        self.meta = MetaOptimizer(claude_client=self.claude)
        self._notify = on_notify or (lambda msg: logger.info("[Notify] %s", msg))
        ORCHESTRATOR_LOG.parent.mkdir(parents=True, exist_ok=True)

    def run_debate(self, topic: str, context: str = "") -> dict:
        """Run a full 3-round multi-agent debate."""
        logger.info("[Orchestrator] Starting debate: %s", topic[:80])
        result = self.debate.run_debate(topic, context)
        self._log_action("debate", {"topic": topic, "synthesis": result.get("synthesis")})
        return result

    def run_quick_consensus(self, task: str, context: str = "") -> dict:
        """Run a quick 2-agent consensus."""
        logger.info("[Orchestrator] Quick consensus: %s", task[:80])
        result = self.quick.propose_and_critique(task, context)
        self._log_action("quick_consensus", {"task": task, "synthesis": result.get("synthesis")})
        return result

    def run_evolution(self, metrics: Optional[dict] = None) -> dict:
        """Run the self-improvement cycle.

        Args:
            metrics: Performance metrics to base evolution on.
                If None, uses an empty placeholder.
        """
        logger.info("[Orchestrator] Starting evolution cycle")

        if metrics is None:
            metrics = {
                "collection_time": datetime.now(JST).isoformat(),
                "note": "No external metrics provided. Using self-contained evolution.",
            }

        result = self.evolution.evolve_strategy(metrics)
        self._log_action("evolution", {
            "version": result.get("version"),
            "changes": result.get("optimization_history", [{}])[-1].get("changes", []),
        })

        self._notify(
            f"System E 戦略進化 v{result.get('version', '?')}\n"
            f"変更点: {len(result.get('optimization_history', [{}])[-1].get('changes', []))}件"
        )

        return result

    def run_diagnosis(self, system_health: Optional[dict] = None) -> dict:
        """Run a full system diagnosis.

        Args:
            system_health: Health data from external systems.
                If None, performs self-diagnosis only.
        """
        logger.info("[Orchestrator] Running system diagnosis")
        result = self.meta.diagnose(system_health)
        self._log_action("diagnosis", {
            "systems_checked": list(result.get("health", {}).get("systems", {}).keys()),
        })
        return result

    def run_interaction_optimization(self, architecture: str = "") -> dict:
        """Optimize inter-system interactions.

        Args:
            architecture: Description of the system architecture to optimize.
        """
        logger.info("[Orchestrator] Optimizing system interactions")
        result = self.meta.optimize_interactions(architecture)
        self._log_action("interaction_optimization", result)
        return result

    def run_full_cycle(
        self,
        system_health: Optional[dict] = None,
        metrics: Optional[dict] = None,
    ) -> dict:
        """Execute the complete meta-intelligence cycle.

        1. Diagnose systems
        2. Debate improvement strategies
        3. Evolve based on findings
        4. Generate report

        Args:
            system_health: External system health data for diagnosis.
            metrics: Performance metrics for evolution.
        """
        logger.info("=== FULL META-INTELLIGENCE CYCLE START ===")
        cycle_result = {}

        # Step 1: Diagnosis
        try:
            logger.info("[1/4] System Diagnosis")
            cycle_result["diagnosis"] = self.run_diagnosis(system_health)
        except Exception as e:
            logger.error("[1/4] Diagnosis failed: %s", e)
            cycle_result["diagnosis"] = {"error": str(e)}

        # Step 2: Debate on improvements
        try:
            logger.info("[2/4] Multi-Agent Debate")
            diagnosis_summary = json.dumps(
                cycle_result.get("diagnosis", {}).get("strategy_analysis", {}),
                ensure_ascii=False,
            )
            cycle_result["debate"] = self.run_debate(
                topic="システム全体のパフォーマンス改善戦略",
                context=f"直近のシステム診断結果:\n{diagnosis_summary}",
            )
        except Exception as e:
            logger.error("[2/4] Debate failed: %s", e)
            cycle_result["debate"] = {"error": str(e)}

        # Step 3: Evolution
        try:
            logger.info("[3/4] Strategy Evolution")
            evo_metrics = metrics or self._extract_metrics_from_diagnosis(
                cycle_result.get("diagnosis", {})
            )
            cycle_result["evolution"] = self.run_evolution(evo_metrics)
        except Exception as e:
            logger.error("[3/4] Evolution failed: %s", e)
            cycle_result["evolution"] = {"error": str(e)}

        # Step 4: Report
        try:
            logger.info("[4/4] Report Generation")
            cycle_result["report"] = self.meta.generate_report(
                cycle_result.get("diagnosis", {}).get("health")
            )
        except Exception as e:
            logger.error("[4/4] Report generation failed: %s", e)
            cycle_result["report"] = {"error": str(e)}

        self._notify(
            "System E フルサイクル完了\n"
            f"戦略バージョン: v{cycle_result['evolution'].get('version', '?')}\n"
            f"議論ラウンド: {len(cycle_result['debate'].get('rounds', []))}回"
        )

        self._log_action("full_cycle", {
            "steps_completed": 4,
            "strategy_version": cycle_result["evolution"].get("version"),
        })

        logger.info("=== FULL META-INTELLIGENCE CYCLE COMPLETE ===")
        return cycle_result

    def _extract_metrics_from_diagnosis(self, diagnosis: dict) -> dict:
        """Extract usable metrics from a diagnosis result."""
        health = diagnosis.get("health", {})
        systems = health.get("systems", {})

        return {
            "from_diagnosis": True,
            "system_statuses": {
                name: sys.get("status", "unknown")
                for name, sys in systems.items()
            },
        }

    def _log_action(self, action: str, details: dict) -> None:
        """Append action to orchestrator log."""
        entry = {
            "timestamp": datetime.now(JST).isoformat(),
            "action": action,
            "details": details,
        }
        with open(ORCHESTRATOR_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="System E: Meta-Intelligence Orchestrator")
    parser.add_argument(
        "--mode",
        choices=["debate", "quick", "evolve", "diagnose", "optimize", "full-cycle"],
        default="diagnose",
        help="実行モード",
    )
    parser.add_argument("--topic", type=str, default="", help="議論のトピック（debateモード用）")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    orchestrator = Orchestrator()

    try:
        if args.mode == "debate":
            topic = args.topic or "次の成長戦略を議論する"
            result = orchestrator.run_debate(topic)
            print(json.dumps(result.get("synthesis", {}), ensure_ascii=False, indent=2))

        elif args.mode == "quick":
            topic = args.topic or "今週最も優先すべきタスク"
            result = orchestrator.run_quick_consensus(topic)
            print(json.dumps(result.get("synthesis", {}), ensure_ascii=False, indent=2))

        elif args.mode == "evolve":
            result = orchestrator.run_evolution()
            print(f"Strategy evolved to v{result.get('version', '?')}")

        elif args.mode == "diagnose":
            result = orchestrator.run_diagnosis()
            print(json.dumps(result.get("optimization_plan", {}), ensure_ascii=False, indent=2))

        elif args.mode == "optimize":
            result = orchestrator.run_interaction_optimization()
            print(json.dumps(result, ensure_ascii=False, indent=2))

        elif args.mode == "full-cycle":
            result = orchestrator.run_full_cycle()
            report = result.get("report", {})
            print(json.dumps(report, ensure_ascii=False, indent=2))

    except Exception as e:
        logger.error("Orchestrator mode '%s' failed: %s", args.mode, e)
        print(f"Error running mode '{args.mode}': {e}")


if __name__ == "__main__":
    main()
