"""Meta-Optimizer — AIがAIシステム自体を最適化する.

外部システムのパフォーマンスデータを受け取り、
戦略的分析・最適化提案を行う。外部データディレクトリへの直接アクセスは行わない。
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from system_e.client import ClaudeClient
from system_e.agents import AgentRunner, STRATEGIST, OPTIMIZER

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
META_LOG_DIR = Path(__file__).parent / "data" / "meta_optimization"


class MetaOptimizer:
    """Top-level optimizer that improves the entire system of systems.

    外部システムのデータは引数として渡す設計。
    ファイルシステムへの直接読み込みは system_e/data/ 内のみ。
    """

    def __init__(self, claude_client: Optional[ClaudeClient] = None):
        self.claude = claude_client or ClaudeClient()
        self.strategist = AgentRunner(STRATEGIST, self.claude)
        self.optimizer = AgentRunner(OPTIMIZER, self.claude)
        META_LOG_DIR.mkdir(parents=True, exist_ok=True)

    def diagnose(self, system_health: Optional[dict] = None) -> dict:
        """Run a full system diagnosis.

        Args:
            system_health: Health data from external systems.
                If None, uses a minimal self-diagnosis of System E only.

        Returns:
            Diagnosis report with health status, bottlenecks, and recommendations.
        """
        logger.info("=== Meta-Optimization: System Diagnosis ===")

        health = system_health or self._self_diagnosis()

        # Have Strategist analyze the overall system
        logger.info("Running strategic analysis via Strategist agent")
        strategy_analysis = self.strategist.think(
            task=(
                "以下のシステム健全性データを分析し、全体戦略の観点から\n"
                "ボトルネック、機会、リスクを特定してください。\n"
                "各システムの連携度合い、リソース配分の最適性も評価してください。"
            ),
            context=json.dumps(health, ensure_ascii=False, indent=2),
        )

        # Have Optimizer suggest specific improvements
        logger.info("Generating optimization plan via Optimizer agent")
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

    def optimize_interactions(self, architecture_description: str = "") -> dict:
        """Analyze and optimize how systems interact with each other.

        Args:
            architecture_description: Free-text description of the current system
                architecture. If empty, uses a generic prompt.

        Returns:
            Interaction optimization recommendations.
        """
        logger.info("=== Meta-Optimization: Interaction Optimization ===")
        default_description = (
            "複数のサブシステムで構成されたAI自動化プラットフォーム。\n"
            "各システムの詳細が不明な場合、一般的なマルチエージェントシステムの\n"
            "最適化原則に基づいて提案してください。"
        )

        task = f"""以下のシステムアーキテクチャの連携を最適化してください。

## アーキテクチャ
{architecture_description or default_description}

以下を分析してください:
1. 現在の連携で不足している接続はあるか？
2. データフローのボトルネックはどこか？
3. 新たに追加すべき連携パスは何か？
4. メタ知能レイヤーとして他システムをどう強化できるか？"""

        result = self.strategist.think(task)
        logger.info("Interaction optimization complete")
        return result

    def generate_report(self, health_data: Optional[dict] = None) -> dict:
        """Generate a meta-optimization report.

        Args:
            health_data: System health data. If None, uses self-diagnosis.
        """
        health = health_data or self._self_diagnosis()

        report_prompt = f"""以下のシステムデータに基づき、メタレポートを生成してください。

{json.dumps(health, ensure_ascii=False, indent=2)}

出力形式 (JSON):
{{
  "summary": "総括",
  "system_scores": {{"システム名": "0-100のスコア"}},
  "highlights": ["良かった点"],
  "concerns": ["懸念事項"],
  "priorities": ["優先事項"],
  "evolution_recommendations": ["進化の方向性"]
}}"""

        raw = self.claude.generate(
            prompt=report_prompt,
            system="あなたはAIシステム群のレビューを行うメタAIです。",
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

    def _self_diagnosis(self) -> dict:
        """Minimal self-diagnosis using only System E's own data."""
        se_dir = Path(__file__).parent / "data"

        debate_count = 0
        evolution_count = 0
        meta_count = 0

        debates_dir = se_dir / "debates"
        if debates_dir.exists():
            debate_count = len(list(debates_dir.glob("*.json")))

        evolution_dir = se_dir / "evolution"
        if evolution_dir.exists():
            evolution_count = len(list(evolution_dir.glob("*.json")))

        meta_dir = se_dir / "meta_optimization"
        if meta_dir.exists():
            meta_count = len(list(meta_dir.glob("*.json")))

        return {
            "collected_at": datetime.now(JST).isoformat(),
            "systems": {
                "E": {
                    "status": "active",
                    "description": "メタ知能エンジン（独立稼働）",
                    "debates_conducted": debate_count,
                    "evolutions_completed": evolution_count,
                    "meta_optimizations": meta_count,
                },
            },
        }
