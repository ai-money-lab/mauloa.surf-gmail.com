"""Self-Improvement Loop — AIが自分自身を進化させる.

実績データを分析 → 改善仮説を生成 → 戦略を進化 → 効果を測定
このサイクルを回し続けることで、システム全体が自律的に賢くなる。
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from system_e.client import ClaudeClient
from system_e.agents import AgentRunner, OPTIMIZER, INNOVATOR, CRITIC

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
EVOLUTION_DIR = Path(__file__).parent / "data" / "evolution"
STRATEGY_FILE = Path(__file__).parent / "data" / "current_strategy.json"


class EvolutionEngine:
    """Self-improving system that evolves strategies based on performance data."""

    def __init__(self, claude_client: Optional[ClaudeClient] = None):
        self.claude = claude_client or ClaudeClient()
        self.optimizer = AgentRunner(OPTIMIZER, self.claude)
        self.innovator = AgentRunner(INNOVATOR, self.claude)
        self.critic = AgentRunner(CRITIC, self.claude)
        EVOLUTION_DIR.mkdir(parents=True, exist_ok=True)

    def load_current_strategy(self) -> dict:
        """Load the current system strategy."""
        if STRATEGY_FILE.exists():
            return json.loads(STRATEGY_FILE.read_text(encoding="utf-8"))
        return self._default_strategy()

    def _default_strategy(self) -> dict:
        return {
            "version": 1,
            "created_at": datetime.now(JST).isoformat(),
            "posting_strategy": {
                "pillar_ratios": {
                    "不動産の裏側": 0.30,
                    "住環境・暮らしの知恵": 0.25,
                    "お金・資産・不動産投資": 0.20,
                    "経営者の日常": 0.15,
                    "テクノロジー×不動産": 0.10,
                },
                "posting_times": ["07:00", "12:00", "19:00"],
                "tone": "professional_yet_approachable",
            },
            "content_strategy": {
                "hook_patterns": ["数字で始める", "問いかけで始める", "意外性で始める"],
                "engagement_tactics": ["リプライ誘導", "引用RT誘導", "保存させる有益情報"],
            },
            "optimization_history": [],
        }

    def analyze_performance(self, metrics: dict) -> dict:
        """Have the Optimizer analyze current performance metrics.

        Args:
            metrics: Dict with keys like engagement_rate, impressions,
                     follower_growth, top_posts, worst_posts, etc.
        """
        task = (
            "以下のパフォーマンスデータを分析し、改善点を特定してください。\n\n"
            f"## パフォーマンスデータ\n{json.dumps(metrics, ensure_ascii=False, indent=2)}"
        )

        strategy = self.load_current_strategy()
        context = f"## 現在の戦略\n{json.dumps(strategy, ensure_ascii=False, indent=2)}"

        return self.optimizer.think(task, context)

    def generate_hypotheses(self, analysis: dict) -> dict:
        """Have the Innovator generate improvement hypotheses."""
        task = (
            "以下の分析結果に基づき、パフォーマンスを飛躍的に改善する\n"
            "仮説とアイデアを生成してください。既存の枠にとらわれず自由に発想してください。\n\n"
            f"## 分析結果\n{json.dumps(analysis, ensure_ascii=False, indent=2)}"
        )
        return self.innovator.think(task)

    def validate_hypotheses(self, hypotheses: dict, analysis: dict) -> dict:
        """Have the Critic validate the proposed hypotheses."""
        task = (
            "以下の改善仮説を批評してください。実現可能性、リスク、\n"
            "見落としている点を指摘し、採用すべき仮説を選別してください。"
        )
        context = (
            f"## 分析結果\n{json.dumps(analysis, ensure_ascii=False, indent=2)}\n\n"
            f"## 改善仮説\n{json.dumps(hypotheses, ensure_ascii=False, indent=2)}"
        )
        return self.critic.think(task, context)

    def evolve_strategy(self, metrics: dict) -> dict:
        """Run the full evolution cycle: analyze → hypothesize → validate → evolve.

        Returns:
            New evolved strategy with change log.
        """
        timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
        logger.info("=== Evolution Cycle Start [%s] ===", timestamp)

        # Step 1: Analyze
        logger.info("Step 1: Performance analysis")
        analysis = self.analyze_performance(metrics)

        # Step 2: Hypothesize
        logger.info("Step 2: Hypothesis generation")
        hypotheses = self.generate_hypotheses(analysis)

        # Step 3: Validate
        logger.info("Step 3: Hypothesis validation")
        validation = self.validate_hypotheses(hypotheses, analysis)

        # Step 4: Synthesize new strategy
        logger.info("Step 4: Strategy evolution")
        new_strategy = self._synthesize_evolution(analysis, hypotheses, validation)

        # Save evolution record
        evolution_record = {
            "timestamp": timestamp,
            "metrics_input": metrics,
            "analysis": analysis,
            "hypotheses": hypotheses,
            "validation": validation,
            "new_strategy": new_strategy,
        }

        record_path = EVOLUTION_DIR / f"evolution_{timestamp}.json"
        record_path.write_text(
            json.dumps(evolution_record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Update current strategy
        current = self.load_current_strategy()
        current["version"] = current.get("version", 0) + 1
        current["last_evolved"] = datetime.now(JST).isoformat()
        current["optimization_history"].append({
            "timestamp": timestamp,
            "changes": new_strategy.get("changes", []),
        })

        # Apply changes from synthesis
        if "posting_strategy" in new_strategy:
            current["posting_strategy"].update(new_strategy["posting_strategy"])
        if "content_strategy" in new_strategy:
            current["content_strategy"].update(new_strategy["content_strategy"])

        STRATEGY_FILE.parent.mkdir(parents=True, exist_ok=True)
        STRATEGY_FILE.write_text(
            json.dumps(current, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info("=== Evolution Cycle Complete: v%d ===", current["version"])
        return current

    def _synthesize_evolution(self, analysis: dict, hypotheses: dict, validation: dict) -> dict:
        """Synthesize analysis, hypotheses, and validation into strategy changes."""
        prompt = f"""3つのAIエージェントの出力を統合し、具体的な戦略変更を決定してください。

## Optimizer の分析
{json.dumps(analysis, ensure_ascii=False, indent=2)}

## Innovator の仮説
{json.dumps(hypotheses, ensure_ascii=False, indent=2)}

## Critic の検証結果
{json.dumps(validation, ensure_ascii=False, indent=2)}

## 指示
採用する変更のみをJSON形式で出力してください:
{{
  "changes": ["変更点の説明1", "変更点の説明2"],
  "posting_strategy": {{"変更するキーのみ": "新しい値"}},
  "content_strategy": {{"変更するキーのみ": "新しい値"}},
  "rationale": "変更の根拠",
  "expected_improvement": "期待される改善効果"
}}"""

        raw = self.claude.generate(
            prompt=prompt,
            system="あなたは3つのAIの出力を統合する最終決定者です。保守的すぎず、無謀すぎない最適な変更を決定してください。",
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
            logger.warning("Evolution synthesis parse error.")
            return {"changes": [], "raw_response": raw}
