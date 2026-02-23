"""Meta-Optimizer — AIがAIシステム自体を最適化する.

System A-D全体のパフォーマンスを俯瞰し、
システム間の連携・リソース配分・優先順位を最適化する上位レイヤー。
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from core.claude_client import ClaudeClient
from system_e.agents import AgentRunner, STRATEGIST, OPTIMIZER

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
META_LOG_DIR = Path(__file__).parent.parent / "data" / "system_e" / "meta_optimization"


class SystemHealthReport:
    """Collects and structures health data from all systems."""

    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / "data"

    def collect(self) -> dict:
        """Collect available performance data from all systems."""
        report = {
            "collected_at": datetime.now(JST).isoformat(),
            "systems": {},
        }

        # System A: X posting performance
        report["systems"]["A"] = self._collect_system_a()

        # System B: Order processing
        report["systems"]["B"] = self._collect_system_b()

        # System C: Information gathering
        report["systems"]["C"] = self._collect_system_c()

        # System D: Results publishing
        report["systems"]["D"] = self._collect_system_d()

        # System E: Meta-intelligence
        report["systems"]["E"] = self._collect_system_e()

        return report

    def _collect_system_a(self) -> dict:
        perf_dir = self.data_dir / "performance"
        if not perf_dir.exists():
            return {"status": "no_data", "description": "X投稿パイプライン"}

        files = sorted(perf_dir.glob("*.json"), reverse=True)
        if not files:
            return {"status": "no_data", "description": "X投稿パイプライン"}

        latest = json.loads(files[0].read_text(encoding="utf-8"))
        return {
            "status": "active",
            "description": "X投稿パイプライン",
            "latest_report": files[0].name,
            "data": latest,
        }

    def _collect_system_b(self) -> dict:
        orders_dir = self.data_dir / "orders"
        if not orders_dir.exists():
            return {"status": "no_data", "description": "案件自動処理エンジン"}

        files = list(orders_dir.glob("*.json"))
        return {
            "status": "active" if files else "idle",
            "description": "案件自動処理エンジン",
            "total_orders": len(files),
        }

    def _collect_system_c(self) -> dict:
        sc_dir = self.data_dir / "system_c"
        if not sc_dir.exists():
            return {"status": "no_data", "description": "情報収集エージェント軍団"}

        daily_count = len(list((sc_dir / "daily").glob("*.json"))) if (sc_dir / "daily").exists() else 0
        weekly_count = len(list((sc_dir / "weekly").glob("*.json"))) if (sc_dir / "weekly").exists() else 0

        return {
            "status": "active" if (daily_count + weekly_count) > 0 else "idle",
            "description": "情報収集エージェント軍団",
            "daily_reports": daily_count,
            "weekly_reports": weekly_count,
        }

    def _collect_system_d(self) -> dict:
        sd_dir = self.data_dir / "results_content"
        if not sd_dir.exists():
            return {"status": "no_data", "description": "実績発信エンジン"}

        files = list(sd_dir.glob("*.json"))
        return {
            "status": "active" if files else "idle",
            "description": "実績発信エンジン",
            "contents_generated": len(files),
        }

    def _collect_system_e(self) -> dict:
        se_dir = self.data_dir / "system_e"
        if not se_dir.exists():
            return {"status": "initialized", "description": "メタ知能エンジン"}

        debate_count = len(list((se_dir / "debates").glob("*.json"))) if (se_dir / "debates").exists() else 0
        evolution_count = len(list((se_dir / "evolution").glob("*.json"))) if (se_dir / "evolution").exists() else 0

        return {
            "status": "active",
            "description": "メタ知能エンジン",
            "debates_conducted": debate_count,
            "evolutions_completed": evolution_count,
        }


class MetaOptimizer:
    """Top-level optimizer that improves the entire system of systems."""

    def __init__(self, claude_client: Optional[ClaudeClient] = None):
        self.claude = claude_client or ClaudeClient()
        self.strategist = AgentRunner(STRATEGIST, self.claude)
        self.optimizer = AgentRunner(OPTIMIZER, self.claude)
        self.health_reporter = SystemHealthReport()
        META_LOG_DIR.mkdir(parents=True, exist_ok=True)

    def diagnose(self) -> dict:
        """Run a full system diagnosis across all systems.

        Returns:
            Diagnosis report with health status, bottlenecks, and recommendations.
        """
        logger.info("=== Meta-Optimization: System Diagnosis ===")

        # Collect health data
        health = self.health_reporter.collect()

        # Have Strategist analyze the overall system
        strategy_analysis = self.strategist.think(
            task=(
                "以下のシステム健全性データを分析し、全体戦略の観点から\n"
                "ボトルネック、機会、リスクを特定してください。\n"
                "System A-Eの連携度合い、リソース配分の最適性も評価してください。"
            ),
            context=json.dumps(health, ensure_ascii=False, indent=2),
        )

        # Have Optimizer suggest specific improvements
        optimization_plan = self.optimizer.think(
            task=(
                "以下のシステム健全性データと戦略分析を踏まえ、\n"
                "具体的な最適化施策を優先順位付きで提案してください。\n"
                "各施策の期待効果と実装コストも見積もってください。"
            ),
            context=(
                f"## 健全性データ\n{json.dumps(health, ensure_ascii=False, indent=2)}\n\n"
                f"## 戦略分析\n{json.dumps(strategy_analysis, ensure_ascii=False, indent=2)}"
            ),
        )

        diagnosis = {
            "diagnosed_at": datetime.now(JST).isoformat(),
            "health": health,
            "strategy_analysis": strategy_analysis,
            "optimization_plan": optimization_plan,
        }

        # Save diagnosis
        timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
        path = META_LOG_DIR / f"diagnosis_{timestamp}.json"
        path.write_text(json.dumps(diagnosis, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Diagnosis saved: %s", path)

        return diagnosis

    def optimize_system_interactions(self) -> dict:
        """Analyze and optimize how systems A-D interact with each other.

        Returns:
            Interaction optimization recommendations.
        """
        task = """HIROKI AI Empireの4つのサブシステムの連携を最適化してください。

現在のアーキテクチャ:
- System A (X投稿パイプライン): 3つのパイプラインでコンテンツ生成→品質チェック→投稿
- System B (案件処理エンジン): ランサーズ/ココナラの案件を自動処理
- System C (情報収集エージェント): CrewAIベースの情報収集軍団
- System D (実績発信エンジン): System B/Cの成果をXで発信

現在の連携フロー:
  C → A (データ供給)
  C → B (データ供給)
  B → D (実績データ)
  D → A (投稿コンテンツ)

以下を分析してください:
1. 現在の連携で不足している接続はあるか？
2. データフローのボトルネックはどこか？
3. 新たに追加すべき連携パスは何か？
4. System Eとして他システムをどう強化できるか？"""

        return self.strategist.think(task)

    def generate_weekly_report(self) -> dict:
        """Generate a weekly meta-optimization report."""
        health = self.health_reporter.collect()

        report_prompt = f"""以下のシステムデータに基づき、週次メタレポートを生成してください。

{json.dumps(health, ensure_ascii=False, indent=2)}

出力形式 (JSON):
{{
  "week_summary": "今週の総括",
  "system_scores": {{"A": 0-100, "B": 0-100, "C": 0-100, "D": 0-100, "E": 0-100}},
  "highlights": ["良かった点"],
  "concerns": ["懸念事項"],
  "next_week_priorities": ["来週の優先事項"],
  "evolution_recommendations": ["進化の方向性"]
}}"""

        raw = self.claude.generate(
            prompt=report_prompt,
            system="あなたはAIシステム群の週次レビューを行うメタAIです。",
            temperature=0.3,
            max_tokens=4096,
        )

        try:
            text = raw.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [ln for ln in lines[1:] if not ln.strip().startswith("```")]
                text = "\n".join(lines)
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw_response": raw}
