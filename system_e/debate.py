"""Multi-Agent Debate Protocol — AI同士が協議して最適解を導く.

3ラウンド制の構造化された議論プロトコル:
  Round 1: 各エージェントが独立に意見を出す（並列思考）
  Round 2: 他のエージェントの意見を踏まえて反論・補足（交差批評）
  Round 3: 合意形成 — 統合AIが全意見をまとめ最終結論を出す
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from system_e.client import ClaudeClient
from system_e.agents import (
    AgentPersona,
    AgentRunner,
    ALL_AGENTS,
    STRATEGIST,
    CRITIC,
)

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
DEBATE_LOG_DIR = Path(__file__).parent / "data" / "debates"


class DebateProtocol:
    """Structured multi-agent debate for reaching AI consensus."""

    def __init__(
        self,
        agents: Optional[list[AgentPersona]] = None,
        claude_client: Optional[ClaudeClient] = None,
        max_rounds: int = 3,
    ):
        self.claude = claude_client or ClaudeClient()
        self.agent_personas = agents or ALL_AGENTS
        self.runners = {
            persona.name: AgentRunner(persona, self.claude)
            for persona in self.agent_personas
        }
        self.max_rounds = max_rounds
        DEBATE_LOG_DIR.mkdir(parents=True, exist_ok=True)

    def run_debate(self, topic: str, context: str = "") -> dict:
        """Execute a full multi-agent debate on a topic.

        Returns:
            Complete debate record with all rounds and final synthesis.
        """
        debate_id = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
        logger.info("=== Debate Start [%s]: %s ===", debate_id, topic[:80])

        record = {
            "debate_id": debate_id,
            "topic": topic,
            "context": context,
            "agents": [p.name for p in self.agent_personas],
            "rounds": [],
            "synthesis": None,
            "started_at": datetime.now(JST).isoformat(),
        }

        # ── Round 1: 独立思考（各エージェントが個別に考える）──
        round1 = self._run_independent_round(topic, context)
        record["rounds"].append({"round": 1, "type": "independent", "outputs": round1})
        logger.info("Round 1 complete: %d opinions collected", len(round1))

        # ── Round 2: 交差批評（他の意見を踏まえて再考）──
        round2 = self._run_cross_critique_round(topic, round1)
        record["rounds"].append({"round": 2, "type": "cross_critique", "outputs": round2})
        logger.info("Round 2 complete: cross-critique done")

        # ── Round 3: 合意形成 ──
        if self.max_rounds >= 3:
            round3 = self._run_convergence_round(topic, round1, round2)
            record["rounds"].append({"round": 3, "type": "convergence", "outputs": round3})
            logger.info("Round 3 complete: convergence reached")

        # ── 最終統合 ──
        synthesis = self._synthesize(topic, record["rounds"])
        record["synthesis"] = synthesis
        record["completed_at"] = datetime.now(JST).isoformat()

        # Save debate log
        self._save_debate(debate_id, record)
        logger.info("=== Debate Complete [%s] ===", debate_id)

        return record

    def _run_independent_round(self, topic: str, context: str) -> list[dict]:
        """Round 1: Each agent thinks independently."""
        outputs = []
        for name, runner in self.runners.items():
            task = f"以下のトピックについて、あなたの{runner.persona.role}としての視点から分析してください。\n\nトピック: {topic}"
            result = runner.think(task, context)
            outputs.append({"agent": name, "result": result})
        return outputs

    def _run_cross_critique_round(self, topic: str, round1_outputs: list[dict]) -> list[dict]:
        """Round 2: Each agent reviews and responds to others' opinions."""
        outputs = []
        for name, runner in self.runners.items():
            # Give each agent the other agents' outputs (not their own)
            other_outputs = [o for o in round1_outputs if o["agent"] != name]
            result = runner.respond_to(topic, other_outputs)
            outputs.append({"agent": name, "result": result})
        return outputs

    def _run_convergence_round(
        self, topic: str, round1: list[dict], round2: list[dict]
    ) -> list[dict]:
        """Round 3: Agents try to find common ground and resolve disagreements."""
        all_context = (
            "## Round 1 (独立意見)\n"
            + json.dumps(round1, ensure_ascii=False, indent=2)
            + "\n\n## Round 2 (交差批評)\n"
            + json.dumps(round2, ensure_ascii=False, indent=2)
        )

        outputs = []
        for name, runner in self.runners.items():
            task = (
                f"## 合意形成フェーズ\n"
                f"トピック: {topic}\n\n"
                f"これまでの2ラウンドの議論を踏まえ、以下を出力してください:\n"
                f"1. 全員が同意している点\n"
                f"2. まだ議論が分かれている点\n"
                f"3. あなたの最終的な立場と根拠\n"
                f"4. 次に取るべきアクション提案"
            )
            result = runner.think(task, all_context)
            outputs.append({"agent": name, "result": result})
        return outputs

    def _synthesize(self, topic: str, rounds: list[dict]) -> dict:
        """Final synthesis: A meta-AI integrates all debate outputs."""
        synthesis_prompt = f"""あなたは4つのAIエージェントによる議論の統合者です。

## トピック
{topic}

## 議論の全記録
{json.dumps(rounds, ensure_ascii=False, indent=2)}

## 指示
上記の議論を統合し、以下のJSON形式で最終結論を出してください:

{{
  "consensus": "全エージェントの合意事項",
  "key_insights": ["重要な洞察1", "重要な洞察2", "重要な洞察3"],
  "disagreements": ["未解決の論点"],
  "final_decision": "最終的な結論・方針",
  "action_plan": [
    {{"action": "具体的アクション", "owner": "担当システム", "priority": "high/medium/low"}}
  ],
  "confidence": 0.0-1.0,
  "meta_learning": "この議論から得られたメタ的な学び"
}}"""

        raw = self.claude.generate(
            prompt=synthesis_prompt,
            system="あなたは複数AIの議論を統合する最上位のメタAIです。客観的かつ包括的に統合してください。",
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
            logger.warning("Synthesis parse error, returning raw.")
            return {"raw_response": raw, "parse_error": True}

    def _save_debate(self, debate_id: str, record: dict) -> None:
        path = DEBATE_LOG_DIR / f"debate_{debate_id}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Debate log saved: %s", path)


class QuickConsensus:
    """Lightweight 2-agent debate for fast decisions."""

    def __init__(self, claude_client: Optional[ClaudeClient] = None):
        self.claude = claude_client or ClaudeClient()

    def propose_and_critique(self, task: str, context: str = "") -> dict:
        """Strategist proposes, Critic reviews, then synthesis."""
        proposer = AgentRunner(STRATEGIST, self.claude)
        critic = AgentRunner(CRITIC, self.claude)

        # Propose
        proposal = proposer.think(task, context)

        # Critique
        critique = critic.respond_to(task, [{"agent": "Strategist", "result": proposal}])

        # Quick synthesis
        synthesis_prompt = f"""提案と批評を統合してください。

## 提案 (Strategist):
{json.dumps(proposal, ensure_ascii=False, indent=2)}

## 批評 (Critic):
{json.dumps(critique, ensure_ascii=False, indent=2)}

JSON形式で最終判断を出力:
{{"decision": "最終判断", "rationale": "根拠", "action": "次のアクション", "confidence": 0.0-1.0}}"""

        raw = self.claude.generate(prompt=synthesis_prompt, temperature=0.3, max_tokens=2048)
        try:
            text = raw.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [ln for ln in lines[1:] if not ln.strip().startswith("```")]
                text = "\n".join(lines)
            synthesis = json.loads(text)
        except json.JSONDecodeError:
            synthesis = {"raw_response": raw}

        return {
            "proposal": proposal,
            "critique": critique,
            "synthesis": synthesis,
        }
