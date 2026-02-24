"""
AGENT SWARM — 並列分担型エージェント群

複数のAIエージェントが同時に稼働し、タスクを分担する。
各エージェントは専門領域を持ち、互いに成果を共有する。

エージェント種別:
- HUNTER: 案件を探し出すエージェント
- BUILDER: コード・ツールを作るエージェント
- WRITER: コンテンツを生成するエージェント
- SELLER: 営業・提案するエージェント
- ANALYST: 分析・最適化するエージェント
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any

from nexus.common import call_api, parse_json

logger = logging.getLogger("nexus.agents")


class AgentRole(str, Enum):
    """エージェントの役割"""
    HUNTER = "hunter"      # 案件探索
    BUILDER = "builder"    # コード・ツール構築
    WRITER = "writer"      # コンテンツ生成
    SELLER = "seller"      # 営業・提案
    ANALYST = "analyst"    # 分析・最適化


AGENT_PROMPTS: dict[AgentRole, str] = {
    AgentRole.HUNTER: """あなたはHUNTER — 収益機会を狩るエージェントです。

使命:
- フリーランス案件、ビジネス機会、未開拓市場を発見する
- 具体的な案件情報（プラットフォーム、単価、要件）を提供する
- 競合が少なくAI活用で優位に立てる案件を優先する

出力（JSON）:
- "opportunities": [{"title", "platform", "estimated_revenue", "requirements", "ai_advantage", "urgency": 1-10}]
- "market_trends": 発見したトレンド
- "action_items": すぐにやるべきこと""",

    AgentRole.BUILDER: """あなたはBUILDER — ツールとコードを構築するエージェントです。

使命:
- 売れるツール、API、自動化スクリプトを設計・実装する
- 再利用可能で拡張しやすいコードを書く
- 最小限の工数で最大の価値を生む

出力（JSON）:
- "product": {"name", "description", "tech_stack", "features", "pricing_model"}
- "implementation": コードまたは設計書
- "monetization": 収益化戦略""",

    AgentRole.WRITER: """あなたはWRITER — 収益を生むコンテンツを作るエージェントです。

使命:
- 技術記事、チュートリアル、マーケティングコピーを生成する
- SEO・エンゲージメントを最大化する
- 読者を顧客に変換するコンテンツ設計

出力（JSON）:
- "content": {"title", "body", "format", "target_audience", "seo_keywords"}
- "distribution": 配信戦略
- "conversion_strategy": 収益化への導線""",

    AgentRole.SELLER: """あなたはSELLER — 営業と提案の専門エージェントです。

使命:
- 説得力のある提案書・営業メッセージを作成する
- クライアントのペインポイントを特定し、解決策を提示する
- 単価を最大化する交渉戦略を設計する

出力（JSON）:
- "proposals": [{"client_type", "pitch", "value_proposition", "pricing", "follow_up_plan"}]
- "objection_handling": 想定される反論と対策
- "closing_strategy": クロージング戦略""",

    AgentRole.ANALYST: """あなたはANALYST — データ分析と最適化の専門エージェントです。

使命:
- パフォーマンスデータを分析し、改善点を特定する
- 収益最大化のための具体的な提案を行う
- 他エージェントの成果を横断的に評価する

出力（JSON）:
- "analysis": {"findings", "metrics", "benchmarks"}
- "recommendations": 改善提案のリスト
- "priority_actions": 優先度順のアクションリスト""",
}


@dataclass
class AgentTask:
    """エージェントへのタスク"""
    role: AgentRole
    instruction: str
    context: dict[str, Any] = field(default_factory=dict)
    priority: int = 5


@dataclass
class AgentResult:
    """エージェントの実行結果"""
    role: AgentRole
    output: dict[str, Any]
    raw_text: str
    success: bool
    execution_time: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "role": self.role.value,
            "output": self.output,
            "success": self.success,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp,
        }


class AgentSwarm:
    """
    AGENT SWARM — 並列エージェント群

    複数のエージェントを同時に起動し、タスクを分担して実行する。
    各エージェントの成果を統合し、次のアクションを決定する。
    """

    def __init__(self, max_workers: int = 5, data_dir: Path | None = None):
        self.max_workers = max_workers
        self.data_dir = data_dir or Path("nexus/data/agents")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.results_history: list[list[AgentResult]] = []
        self._lock = Lock()

    def dispatch(self, tasks: list[AgentTask]) -> list[AgentResult]:
        """複数エージェントを並列実行"""
        logger.info(f"Dispatching {len(tasks)} agents in parallel")
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._execute_agent, task): task
                for task in tasks
            }

            for future in as_completed(futures):
                task = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(f"Agent {task.role.value} completed (success: {result.success})")
                except Exception as e:
                    logger.error(f"Agent {task.role.value} failed: {e}")
                    results.append(AgentResult(
                        role=task.role,
                        output={"error": str(e)},
                        raw_text="",
                        success=False,
                    ))

        with self._lock:
            self.results_history.append(results)
        self._save_results(results)
        return results

    def full_sweep(self, market_context: str = "", shared_context: dict[str, Any] | None = None) -> list[AgentResult]:
        """全エージェントで一斉スキャン"""
        context = shared_context or {}
        context["market_context"] = market_context

        tasks = [
            AgentTask(
                role=AgentRole.HUNTER,
                instruction="現在のAI市場で即座に取り組める収益機会を5つ発見してください。",
                context=context,
                priority=10,
            ),
            AgentTask(
                role=AgentRole.BUILDER,
                instruction="24時間以内に作れて売れるAIツールを3つ設計してください。",
                context=context,
                priority=9,
            ),
            AgentTask(
                role=AgentRole.WRITER,
                instruction="バズる技術記事のアイデアを3つ、本文付きで生成してください。",
                context=context,
                priority=8,
            ),
            AgentTask(
                role=AgentRole.SELLER,
                instruction="AIサービスの営業提案書テンプレートを3パターン作成してください。",
                context=context,
                priority=8,
            ),
            AgentTask(
                role=AgentRole.ANALYST,
                instruction="AI収益化の成功パターンを分析し、最も効率的な戦略を提案してください。",
                context=context,
                priority=7,
            ),
        ]

        return self.dispatch(tasks)

    def targeted_sweep(self, focus: str, roles: list[AgentRole] | None = None) -> list[AgentResult]:
        """特定テーマにフォーカスしたスキャン"""
        target_roles = roles or list(AgentRole)
        tasks = []

        for role in target_roles:
            tasks.append(AgentTask(
                role=role,
                instruction=f"以下のテーマに対して、あなたの専門知識を最大限に活用してください:\n\n{focus}",
                context={"focus": focus},
                priority=8,
            ))

        return self.dispatch(tasks)

    def synthesize(self, results: list[AgentResult]) -> dict[str, Any]:
        """全エージェントの結果を統合・合成する"""
        successful = [r for r in results if r.success]
        if not successful:
            return {"error": "No successful agent results to synthesize"}

        synthesis_input = "\n\n---\n\n".join(
            f"[{r.role.value.upper()}]\n{json.dumps(r.output, ensure_ascii=False, indent=2)}"
            for r in successful
        )

        raw = call_api(
            system=(
                "あなたは複数のAIエージェントの結果を統合する統合エンジンです。\n"
                "各エージェントの発見を組み合わせ、最も効果的なアクションプランを作成してください。\n\n"
                "出力（JSON）:\n"
                "- \"priority_actions\": 優先度順アクションリスト（各アクションに担当エージェント明記）\n"
                "- \"synergies\": エージェント間のシナジー（組み合わせで価値が出るもの）\n"
                "- \"total_revenue_estimate\": 全体の想定収益\n"
                "- \"execution_plan\": 実行計画（タイムライン付き）"
            ),
            messages=[{
                "role": "user",
                "content": f"以下の全エージェント結果を統合してください:\n\n{synthesis_input}",
            }],
            max_tokens=4096,
        )

        return parse_json(raw, default={"raw_synthesis": raw})

    def _execute_agent(self, task: AgentTask) -> AgentResult:
        """単一エージェントを実行"""
        import time
        start_time = time.time()

        system_prompt = AGENT_PROMPTS.get(task.role, "")
        user_content = task.instruction
        if task.context:
            user_content += f"\n\nコンテキスト:\n{json.dumps(task.context, ensure_ascii=False, indent=2)}"

        raw_text = call_api(
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
            max_tokens=4096,
        )
        elapsed = time.time() - start_time

        # JSONパース
        output = parse_json(raw_text, default={"raw": raw_text})

        return AgentResult(
            role=task.role,
            output=output,
            raw_text=raw_text,
            success=True,
            execution_time=elapsed,
        )

    def _save_results(self, results: list[AgentResult]) -> None:
        """結果を保存"""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_file = self.data_dir / f"swarm_{ts}.json"
        data = [r.to_dict() for r in results]
        output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
