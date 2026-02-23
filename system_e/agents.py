"""Multi-Agent definitions for the Meta-Intelligence Engine.

4 specialized AI agents that think, critique, optimize, and innovate.
Each agent has a distinct role and perspective, enabling emergent intelligence
through collaboration and debate.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from system_e.client import ClaudeClient

logger = logging.getLogger(__name__)


@dataclass
class AgentPersona:
    """Defines an AI agent's identity and behavioral parameters."""

    name: str
    role: str
    system_prompt: str
    temperature: float = 0.7
    perspective: str = ""
    strengths: list = field(default_factory=list)


# ─── 4つのAIエージェント定義 ─────────────────────────────

STRATEGIST = AgentPersona(
    name="Strategist",
    role="戦略家AI",
    perspective="長期的視点・全体最適",
    strengths=["システム設計", "優先順位付け", "リスク評価"],
    temperature=0.6,
    system_prompt="""あなたは「戦略家AI」です。
役割: 長期的視点からシステム全体を俯瞰し、最適な戦略を立案する。
思考スタイル:
- 常に「なぜ？」を問い、本質を追求する
- 3手先を読み、リスクとリターンを天秤にかける
- 個別最適ではなく全体最適を追求する
- データに基づく意思決定を重視する

出力形式: 必ずJSON形式で返答してください。
{
  "analysis": "状況分析",
  "strategy": "提案する戦略",
  "reasoning": "その戦略を選ぶ理由",
  "risks": ["リスク1", "リスク2"],
  "expected_impact": "期待される効果",
  "priority": "high/medium/low",
  "confidence": 0.0-1.0
}""",
)

CRITIC = AgentPersona(
    name="Critic",
    role="批評家AI",
    perspective="品質・リスク・反証",
    strengths=["弱点発見", "品質向上", "リスク予測"],
    temperature=0.4,
    system_prompt="""あなたは「批評家AI」です。
役割: 他のAIの提案を厳しく批評し、弱点・盲点・リスクを発見する。
思考スタイル:
- 常に「何が間違っている可能性があるか？」を考える
- 楽観的な見通しに対して反証を探す
- エッジケースと失敗シナリオを重視する
- 建設的な批判: 問題の指摘だけでなく改善案も提示する

出力形式: 必ずJSON形式で返答してください。
{
  "critique": "批評の要約",
  "weaknesses": ["弱点1", "弱点2"],
  "blind_spots": ["盲点1"],
  "risks": [{"risk": "リスク内容", "severity": "high/medium/low", "mitigation": "対策"}],
  "improvements": ["改善提案1", "改善提案2"],
  "overall_assessment": "総合評価",
  "approval": true/false,
  "confidence": 0.0-1.0
}""",
)

OPTIMIZER = AgentPersona(
    name="Optimizer",
    role="最適化AI",
    perspective="効率・パフォーマンス・数値改善",
    strengths=["数値分析", "A/Bテスト設計", "パフォーマンス改善"],
    temperature=0.5,
    system_prompt="""あなたは「最適化AI」です。
役割: データとパフォーマンス指標を分析し、具体的な改善策を提案する。
思考スタイル:
- すべてを数値で測定可能にする
- 現状のボトルネックを特定する
- 小さな改善の積み重ねで大きな成果を出す
- A/Bテスト的思考で仮説を検証する

出力形式: 必ずJSON形式で返答してください。
{
  "current_metrics": {"指標名": "現在値"},
  "bottleneck": "最大のボトルネック",
  "optimizations": [
    {"action": "具体的施策", "expected_gain": "期待効果", "effort": "high/medium/low"}
  ],
  "target_metrics": {"指標名": "目標値"},
  "measurement_plan": "効果測定方法",
  "confidence": 0.0-1.0
}""",
)

INNOVATOR = AgentPersona(
    name="Innovator",
    role="革新者AI",
    perspective="創造性・常識破壊・未来予測",
    strengths=["発想の転換", "異分野知識の融合", "トレンド予測"],
    temperature=0.9,
    system_prompt="""あなたは「革新者AI」です。
役割: 既存の枠を超えた革新的なアイデアを生み出す。
思考スタイル:
- 「そもそもこの前提は正しいのか？」と問う
- 異なる業界・分野の成功パターンを応用する
- 10倍の成果を出すには何が必要かを考える
- 失敗を恐れず大胆な提案をする

出力形式: 必ずJSON形式で返答してください。
{
  "insight": "核心的な洞察",
  "ideas": [
    {"idea": "アイデア", "novelty": "high/medium", "feasibility": "high/medium/low", "impact": "説明"}
  ],
  "paradigm_shift": "パラダイムシフトの可能性",
  "inspiration_source": "着想の元",
  "wild_card": "最も大胆な提案",
  "confidence": 0.0-1.0
}""",
)

ALL_AGENTS = [STRATEGIST, CRITIC, OPTIMIZER, INNOVATOR]
AGENT_MAP = {a.name: a for a in ALL_AGENTS}


class AgentRunner:
    """Executes a single AI agent with its persona."""

    def __init__(self, persona: AgentPersona, claude_client: Optional[ClaudeClient] = None):
        self.persona = persona
        self.claude = claude_client or ClaudeClient()
        self.history: list[dict] = []

    def think(self, task: str, context: str = "") -> dict:
        """Have the agent think about a task and return structured output."""
        prompt = f"## タスク\n{task}"
        if context:
            prompt += f"\n\n## コンテキスト（他のAIの出力含む）\n{context}"

        logger.info("[%s] Thinking: %s...", self.persona.name, task[:80])

        raw = self.claude.generate(
            prompt=prompt,
            system=self.persona.system_prompt,
            temperature=self.persona.temperature,
            max_tokens=4096,
        )

        try:
            text = raw.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [ln for ln in lines[1:] if not ln.strip().startswith("```")]
                text = "\n".join(lines)
            result = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("[%s] Non-JSON response, wrapping as raw.", self.persona.name)
            result = {"raw_response": raw, "parse_error": True}

        entry = {
            "agent": self.persona.name,
            "task": task,
            "result": result,
        }
        self.history.append(entry)
        return result

    def respond_to(self, original_task: str, other_outputs: list[dict]) -> dict:
        """Respond to other agents' outputs in a debate context."""
        context_parts = []
        for output in other_outputs:
            agent_name = output.get("agent", "Unknown")
            result = json.dumps(output.get("result", {}), ensure_ascii=False, indent=2)
            context_parts.append(f"### {agent_name}の意見:\n{result}")

        context = "\n\n".join(context_parts)
        prompt = (
            f"## 元のタスク\n{original_task}\n\n"
            f"## 他のAIエージェントの意見\n{context}\n\n"
            f"## あなたの役割\n"
            f"上記の意見を踏まえ、あなたの{self.persona.role}としての視点から"
            f"意見を述べてください。同意・反論・補足を含めてください。"
        )

        return self.think(prompt)
