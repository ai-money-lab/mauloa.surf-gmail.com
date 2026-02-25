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
    python -m system_e.orchestrator --mode analytics
    python -m system_e.orchestrator --mode bridge
    python -m system_e.orchestrator --mode smart-evolve
    python -m system_e.orchestrator --mode bot-insight
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
from system_e.bot_insights_bridge import BotInsightsBridge
from system_e.code_test_harness import CodeTestHarness
from system_e.nexus_bridge import NexusBridge
from system_e.performance_tracker import PerformanceTracker
from system_e.self_improve import EvolutionEngine

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
ORCHESTRATOR_LOG = Path(__file__).parent / "data" / "orchestrator_log.jsonl"


class Orchestrator:
    """The brain of System E — coordinates all meta-intelligence activities.

    Modes:
        debate:       Multi-agent debate on a specific topic
        quick:        Quick 2-agent consensus (Strategist + Critic)
        evolve:       Self-improvement cycle based on performance data
        diagnose:     Full system health diagnosis
        optimize:     Optimize system interactions
        codegen:      Debate → Code generation → Validation → Deploy
        analytics:    Performance analysis and reporting
        bridge:       NEXUS V2 ↔ System E bidirectional optimization
        smart-evolve: Data-driven evolution (analytics → bridge → evolve)
        bot-insight:  Inquiry Bot → System E insights feedback
        full-cycle:   Run everything in sequence (including codegen)

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
        self.test_harness = CodeTestHarness()
        self.tracker = PerformanceTracker()
        self.bridge = NexusBridge(claude_client=self.claude)
        self.bot_insights = BotInsightsBridge(claude_client=self.claude)
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
            logger.info("[CodeGen 3/5] Code Validation")
            val_result = self.validator.validate(gen_result)
            result["validation"] = val_result.to_dict()
        except Exception as e:
            logger.error("[CodeGen 3/5] Validation failed: %s", e)
            result["validation"] = {"error": str(e)}
            return result

        # Step 4: Test Harness
        try:
            logger.info("[CodeGen 4/5] Test Harness")
            test_result = self.test_harness.run_tests(
                gen_result.source_code, gen_result.module_name,
            )
            result["test_harness"] = test_result.to_dict()
        except Exception as e:
            logger.error("[CodeGen 4/5] Test harness failed: %s", e)
            result["test_harness"] = {"error": str(e)}

        # Step 5: Deploy
        try:
            logger.info("[CodeGen 5/5] Deployment")
            deploy_result = self.deployer.deploy(gen_result, val_result)
            result["deployment"] = deploy_result.to_dict()
        except Exception as e:
            logger.error("[CodeGen 5/5] Deployment failed: %s", e)
            result["deployment"] = {"error": str(e)}

        self._log_action("codegen", {
            "topic": topic,
            "module": result.get("generation", {}).get("module_name"),
            "validation_passed": result.get("validation", {}).get("passed"),
            "test_harness_passed": result.get("test_harness", {}).get("passed"),
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

    def run_analytics(self) -> dict:
        """パフォーマンス分析レポートを生成.

        PerformanceTracker がオーケストレーターログと NEXUS V2 履歴を解析し、
        成功率・トレンド・ヘルススコア・改善推奨を算出する。

        Returns:
            Full performance report dict.
        """
        logger.info("[Orchestrator] Running performance analytics")
        report = self.tracker.generate_full_report()
        self._log_action("analytics", {
            "health_score": report.get("health_score"),
            "total_actions": report.get("system_e", {}).get("action_stats", {}).get("total_actions"),
            "recommendations_count": len(report.get("recommendations", [])),
        })

        self._notify(
            f"System E パフォーマンスレポート\n"
            f"ヘルススコア: {report.get('health_score', '?')}/100\n"
            f"推奨事項: {len(report.get('recommendations', []))}件"
        )

        return report

    def run_bridge(self) -> dict:
        """NEXUS V2 ↔ System E のブリッジサイクルを実行.

        1. NEXUS V2 状態収集
        2. 収益パフォーマンス分析
        3. 最適化計画生成
        4. 進化用フィードバック生成

        Returns:
            Bridge cycle result dict.
        """
        logger.info("[Orchestrator] Running NEXUS V2 bridge cycle")
        result = self.bridge.run_bridge_cycle()
        self._log_action("bridge", {
            "nexus_cycles": result.get("nexus_state", {}).get("cycles"),
            "nexus_assets": result.get("nexus_state", {}).get("assets"),
        })

        self._notify(
            "System E ↔ NEXUS V2 ブリッジ完了\n"
            f"NEXUS V2 サイクル: {result.get('nexus_state', {}).get('cycles', '?')}\n"
            f"アセット: {result.get('nexus_state', {}).get('assets', '?')}"
        )

        return result

    def run_smart_evolve(self) -> dict:
        """データ駆動型の進化サイクルを実行.

        従来の evolve は外部メトリクスを手動で渡す必要があったが、
        smart-evolve は performance_tracker と nexus_bridge から
        自動的にメトリクスを収集して進化エンジンに渡す。

        1. パフォーマンスメトリクス自動収集
        2. NEXUS V2 フィードバック収集
        3. 統合メトリクスで進化を実行

        Returns:
            Evolution result dict with data-driven metrics.
        """
        logger.info("=== SMART EVOLUTION CYCLE START ===")
        result: dict = {}

        # Step 1: Collect performance metrics
        try:
            logger.info("[SmartEvolve 1/3] Collecting performance metrics")
            perf_metrics = self.tracker.generate_evolution_metrics()
            result["performance_metrics"] = perf_metrics
        except Exception as e:
            logger.error("[SmartEvolve 1/3] Metrics collection failed: %s", e)
            perf_metrics = {}
            result["performance_metrics"] = {"error": str(e)}

        # Step 2: Collect NEXUS V2 feedback
        try:
            logger.info("[SmartEvolve 2/4] Collecting NEXUS V2 feedback")
            nexus_feedback = self.bridge.generate_nexus_feedback()
            result["nexus_feedback"] = nexus_feedback
        except Exception as e:
            logger.error("[SmartEvolve 2/4] NEXUS feedback failed: %s", e)
            nexus_feedback = {}
            result["nexus_feedback"] = {"error": str(e)}

        # Step 3: Collect Bot insights feedback
        bot_feedback: dict = {}
        try:
            logger.info("[SmartEvolve 3/4] Collecting Bot insights feedback")
            bot_feedback = self.bot_insights.generate_evolution_feedback()
            result["bot_feedback"] = bot_feedback
        except Exception as e:
            logger.error("[SmartEvolve 3/4] Bot feedback failed: %s", e)
            result["bot_feedback"] = {"error": str(e)}

        # Step 4: Run evolution with combined metrics
        try:
            logger.info("[SmartEvolve 4/4] Running data-driven evolution")
            combined_metrics = {**perf_metrics, **nexus_feedback, **bot_feedback}
            combined_metrics["source"] = "smart_evolve"
            result["evolution"] = self.run_evolution(combined_metrics)
        except Exception as e:
            logger.error("[SmartEvolve 4/4] Evolution failed: %s", e)
            result["evolution"] = {"error": str(e)}

        self._log_action("smart_evolve", {
            "perf_health_score": perf_metrics.get("codegen_pass_rate"),
            "nexus_assets": nexus_feedback.get("nexus_total_assets"),
            "evolution_version": result.get("evolution", {}).get("version"),
        })

        self._notify(
            "System E スマート進化完了\n"
            f"戦略バージョン: v{result.get('evolution', {}).get('version', '?')}\n"
            f"データソース: パフォーマンス + NEXUS V2"
        )

        logger.info("=== SMART EVOLUTION CYCLE COMPLETE ===")
        return result

    def run_bot_insight(self) -> dict:
        """Inquiry Bot の運用データを分析し、進化エンジンにフィードバック.

        1. Bot メトリクス収集
        2. 改善パターン検出
        3. 戦略分析
        4. 進化用フィードバック生成

        Returns:
            Bot insight cycle result dict.
        """
        logger.info("[Orchestrator] Running Bot insight cycle")
        result = self.bot_insights.run_insight_cycle()

        metrics = result.get("metrics", {})
        patterns = result.get("patterns", {})
        self._log_action("bot_insight", {
            "total_inquiries": metrics.get("total_inquiries", 0),
            "auto_resolve_rate": metrics.get("auto_resolve_rate", 0),
            "faq_gaps": len(patterns.get("faq_gaps", [])),
        })

        self._notify(
            "System E Bot Insight 完了\n"
            f"問い合わせ数: {metrics.get('total_inquiries', 0)}件\n"
            f"自動応答率: {metrics.get('auto_resolve_rate', 0):.0%}\n"
            f"FAQ ギャップ: {len(patterns.get('faq_gaps', []))}件"
        )

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
            "optimize", "codegen", "evo-codegen",
            "analytics", "bridge", "bot-insight",
            "smart-evolve", "full-cycle",
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

        elif args.mode == "analytics":
            result = orchestrator.run_analytics()
            print(json.dumps(result, ensure_ascii=False, indent=2))

        elif args.mode == "bridge":
            result = orchestrator.run_bridge()
            print(json.dumps(result, ensure_ascii=False, indent=2))

        elif args.mode == "bot-insight":
            result = orchestrator.run_bot_insight()
            print(json.dumps(result, ensure_ascii=False, indent=2))

        elif args.mode == "smart-evolve":
            result = orchestrator.run_smart_evolve()
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
