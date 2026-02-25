"""Orchestrator — System E の司令塔.

すべてのAIエージェントとサブシステムを統括し、
自律的な意思決定・実行・改善のサイクルを回す。

外部モジュール（core/）に依存せず、単体で動作する。

使い方:
    python -m system_e.orchestrator --mode debate --topic "投稿戦略の改善"
    python -m system_e.orchestrator --mode evolve
    python -m system_e.orchestrator --mode diagnose
    python -m system_e.orchestrator --mode full-cycle
    python -m system_e.orchestrator --mode codegen --topic "新機能の実装"
"""

import argparse
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Callable, Optional

from system_e.client import ClaudeClient
from system_e.code_deployer import CodeDeployer
from system_e.code_generator import CodeGenerator
from system_e.code_validator import CodeValidator
from system_e.debate import DebateProtocol, QuickConsensus
from system_e.meta_optimizer import MetaOptimizer
from system_e.self_improve import EvolutionEngine

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
        codegen:    Debate → Code generation → Validation → Deploy
        full-cycle: Run everything in sequence (including codegen)

    Args:
        claude_client: Optional pre-configured ClaudeClient.
        on_notify: Optional callback for notifications (replaces core.notifier).
            Signature: (message: str) -> None
        auto_push: Whether CodeDeployer should auto-push after commit.
    """

    def __init__(
        self,
        claude_client: Optional[ClaudeClient] = None,
        on_notify: Optional[Callable[[str], None]] = None,
        auto_push: bool = False,
    ):
        self.claude = claude_client or ClaudeClient()
        self.debate = DebateProtocol(claude_client=self.claude)
        self.quick = QuickConsensus(claude_client=self.claude)
        self.evolution = EvolutionEngine(claude_client=self.claude)
        self.meta = MetaOptimizer(claude_client=self.claude)
        self.codegen = CodeGenerator(claude_client=self.claude)
        self.validator = CodeValidator()
        self.deployer = CodeDeployer(auto_push=auto_push)
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

    def run_codegen(self, topic: str = "", context: str = "") -> dict:
        """議論 → コード生成 → 検証 → デプロイの閉ループを実行.

        1. トピックについて4エージェントで議論
        2. 議論結果からPythonコードを生成
        3. 生成コードをlint・セキュリティ検証
        4. 検証通過ならファイル書き出し + git commit

        Args:
            topic: 議論・コード生成のトピック。
            context: 追加コンテキスト。

        Returns:
            dict with keys: debate, generation, validation, deployment
        """
        topic = topic or "システムの新しい機能モジュールを設計・実装する"
        logger.info("=== CODE GENERATION CYCLE START: %s ===", topic[:60])

        result: dict = {}

        # Step 1: Debate
        try:
            logger.info("[CodeGen 1/4] Multi-Agent Debate")
            result["debate"] = self.run_debate(topic, context)
        except Exception as e:
            logger.error("[CodeGen 1/4] Debate failed: %s", e)
            result["debate"] = {"error": str(e)}
            return result

        # Step 2: Generate code from debate
        try:
            logger.info("[CodeGen 2/4] Code Generation")
            gen_result = self.codegen.generate_from_debate(result["debate"])
            result["generation"] = gen_result.to_dict()
        except Exception as e:
            logger.error("[CodeGen 2/4] Code generation failed: %s", e)
            result["generation"] = {"error": str(e)}
            return result

        # Step 3: Validate
        try:
            logger.info("[CodeGen 3/4] Code Validation")
            val_result = self.validator.validate(gen_result)
            result["validation"] = val_result.to_dict()
        except Exception as e:
            logger.error("[CodeGen 3/4] Validation failed: %s", e)
            result["validation"] = {"error": str(e)}
            return result

        # Step 4: Deploy
        try:
            logger.info("[CodeGen 4/4] Deployment")
            deploy_result = self.deployer.deploy(gen_result, val_result)
            result["deployment"] = deploy_result.to_dict()
        except Exception as e:
            logger.error("[CodeGen 4/4] Deployment failed: %s", e)
            result["deployment"] = {"error": str(e)}

        self._log_action("codegen", {
            "topic": topic,
            "module": result.get("generation", {}).get("module_name"),
            "validation_passed": result.get("validation", {}).get("passed"),
            "deploy_success": result.get("deployment", {}).get("success"),
        })

        self._notify(
            f"System E コード生成完了\n"
            f"モジュール: {result.get('generation', {}).get('module_name', '?')}\n"
            f"検証: {'PASS' if result.get('validation', {}).get('passed') else 'FAIL'}\n"
            f"デプロイ: {'OK' if result.get('deployment', {}).get('success') else 'NG'}"
        )

        logger.info("=== CODE GENERATION CYCLE COMPLETE ===")
        return result

    def run_codegen_from_evolution(self, metrics: Optional[dict] = None) -> dict:
        """進化 → コード生成 → 検証 → デプロイの閉ループを実行.

        Args:
            metrics: 進化に使うメトリクス。

        Returns:
            dict with keys: evolution, generation, validation, deployment
        """
        logger.info("=== EVOLUTION + CODEGEN CYCLE START ===")
        result: dict = {}

        # Step 1: Evolution
        try:
            logger.info("[EvoCodeGen 1/4] Strategy Evolution")
            result["evolution"] = self.run_evolution(metrics)
        except Exception as e:
            logger.error("[EvoCodeGen 1/4] Evolution failed: %s", e)
            result["evolution"] = {"error": str(e)}
            return result

        # Step 2: Generate code from evolution
        try:
            logger.info("[EvoCodeGen 2/4] Code Generation")
            gen_result = self.codegen.generate_from_evolution(result["evolution"])
            result["generation"] = gen_result.to_dict()
        except Exception as e:
            logger.error("[EvoCodeGen 2/4] Code generation failed: %s", e)
            result["generation"] = {"error": str(e)}
            return result

        # Step 3: Validate
        try:
            logger.info("[EvoCodeGen 3/4] Code Validation")
            val_result = self.validator.validate(gen_result)
            result["validation"] = val_result.to_dict()
        except Exception as e:
            logger.error("[EvoCodeGen 3/4] Validation failed: %s", e)
            result["validation"] = {"error": str(e)}
            return result

        # Step 4: Deploy
        try:
            logger.info("[EvoCodeGen 4/4] Deployment")
            deploy_result = self.deployer.deploy(gen_result, val_result)
            result["deployment"] = deploy_result.to_dict()
        except Exception as e:
            logger.error("[EvoCodeGen 4/4] Deployment failed: %s", e)
            result["deployment"] = {"error": str(e)}

        self._log_action("evo_codegen", {
            "version": result.get("evolution", {}).get("version"),
            "module": result.get("generation", {}).get("module_name"),
            "validation_passed": result.get("validation", {}).get("passed"),
            "deploy_success": result.get("deployment", {}).get("success"),
        })

        logger.info("=== EVOLUTION + CODEGEN CYCLE COMPLETE ===")
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
        4. Generate code from debate results
        5. Generate report

        Args:
            system_health: External system health data for diagnosis.
            metrics: Performance metrics for evolution.
        """
        logger.info("=== FULL META-INTELLIGENCE CYCLE START ===")
        cycle_result = {}

        # Step 1: Diagnosis
        try:
            logger.info("[1/5] System Diagnosis")
            cycle_result["diagnosis"] = self.run_diagnosis(system_health)
        except Exception as e:
            logger.error("[1/5] Diagnosis failed: %s", e)
            cycle_result["diagnosis"] = {"error": str(e)}

        # Step 2: Debate on improvements
        try:
            logger.info("[2/5] Multi-Agent Debate")
            diagnosis_summary = json.dumps(
                cycle_result.get("diagnosis", {}).get("strategy_analysis", {}),
                ensure_ascii=False,
            )
            cycle_result["debate"] = self.run_debate(
                topic="システム全体のパフォーマンス改善戦略",
                context=f"直近のシステム診断結果:\n{diagnosis_summary}",
            )
        except Exception as e:
            logger.error("[2/5] Debate failed: %s", e)
            cycle_result["debate"] = {"error": str(e)}

        # Step 3: Evolution
        try:
            logger.info("[3/5] Strategy Evolution")
            evo_metrics = metrics or self._extract_metrics_from_diagnosis(
                cycle_result.get("diagnosis", {})
            )
            cycle_result["evolution"] = self.run_evolution(evo_metrics)
        except Exception as e:
            logger.error("[3/5] Evolution failed: %s", e)
            cycle_result["evolution"] = {"error": str(e)}

        # Step 4: Code Generation from debate
        try:
            logger.info("[4/5] Code Generation")
            debate = cycle_result.get("debate", {})
            if "error" not in debate:
                gen_result = self.codegen.generate_from_debate(debate)
                val_result = self.validator.validate(gen_result)
                deploy_result = self.deployer.deploy(gen_result, val_result)
                cycle_result["codegen"] = {
                    "generation": gen_result.to_dict(),
                    "validation": val_result.to_dict(),
                    "deployment": deploy_result.to_dict(),
                }
            else:
                cycle_result["codegen"] = {"skipped": "debate failed"}
        except Exception as e:
            logger.error("[4/5] Code generation failed: %s", e)
            cycle_result["codegen"] = {"error": str(e)}

        # Step 5: Report
        try:
            logger.info("[5/5] Report Generation")
            cycle_result["report"] = self.meta.generate_report(
                cycle_result.get("diagnosis", {}).get("health")
            )
        except Exception as e:
            logger.error("[5/5] Report generation failed: %s", e)
            cycle_result["report"] = {"error": str(e)}

        codegen_status = cycle_result.get("codegen", {})
        codegen_msg = ""
        if codegen_status.get("deployment", {}).get("success"):
            codegen_msg = f"\nコード生成: {codegen_status['generation']['module_name']}"
        elif "skipped" in codegen_status:
            codegen_msg = "\nコード生成: スキップ"
        else:
            codegen_msg = "\nコード生成: 失敗"

        self._notify(
            "System E フルサイクル完了\n"
            f"戦略バージョン: v{cycle_result['evolution'].get('version', '?')}\n"
            f"議論ラウンド: {len(cycle_result['debate'].get('rounds', []))}回"
            f"{codegen_msg}"
        )

        self._log_action("full_cycle", {
            "steps_completed": 5,
            "strategy_version": cycle_result["evolution"].get("version"),
            "codegen_success": codegen_status.get("deployment", {}).get("success"),
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
        choices=[
            "debate", "quick", "evolve", "diagnose",
            "optimize", "codegen", "evo-codegen", "full-cycle",
        ],
        default="diagnose",
        help="実行モード",
    )
    parser.add_argument("--topic", type=str, default="", help="議論のトピック")
    parser.add_argument("--auto-push", action="store_true", help="コード生成後にgit pushする")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    orchestrator = Orchestrator(auto_push=args.auto_push)

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

        elif args.mode == "codegen":
            topic = args.topic or "システムの新しい機能モジュールを設計・実装する"
            result = orchestrator.run_codegen(topic)
            print(json.dumps(result, ensure_ascii=False, indent=2))

        elif args.mode == "evo-codegen":
            result = orchestrator.run_codegen_from_evolution()
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
