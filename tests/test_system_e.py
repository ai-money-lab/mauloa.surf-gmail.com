"""Tests for System E: Meta-Intelligence Engine."""

import json
from unittest.mock import MagicMock, patch


from system_e.agents import (
    STRATEGIST,
    CRITIC,
    OPTIMIZER,
    INNOVATOR,
    ALL_AGENTS,
    AGENT_MAP,
    AgentRunner,
)
from system_e.debate import DebateProtocol, QuickConsensus
from system_e.self_improve import EvolutionEngine
from system_e.meta_optimizer import MetaOptimizer
from system_e.orchestrator import Orchestrator


# ─── Agent Tests ─────────────────────────────────────────

class TestAgentPersonas:
    def test_all_agents_defined(self):
        assert len(ALL_AGENTS) == 4

    def test_agent_map_keys(self):
        assert set(AGENT_MAP.keys()) == {"Strategist", "Critic", "Optimizer", "Innovator"}

    def test_strategist_persona(self):
        assert STRATEGIST.name == "Strategist"
        assert STRATEGIST.role == "戦略家AI"
        assert STRATEGIST.temperature == 0.6

    def test_critic_persona(self):
        assert CRITIC.name == "Critic"
        assert CRITIC.role == "批評家AI"
        assert CRITIC.temperature == 0.4

    def test_optimizer_persona(self):
        assert OPTIMIZER.name == "Optimizer"
        assert OPTIMIZER.temperature == 0.5

    def test_innovator_persona(self):
        assert INNOVATOR.name == "Innovator"
        assert INNOVATOR.temperature == 0.9

    def test_all_agents_have_system_prompt(self):
        for agent in ALL_AGENTS:
            assert agent.system_prompt
            assert len(agent.system_prompt) > 50


class TestAgentRunner:
    @patch("system_e.agents.ClaudeClient")
    def test_think_returns_parsed_json(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({
            "analysis": "test analysis",
            "strategy": "test strategy",
            "confidence": 0.8,
        })
        mock_client_cls.return_value = mock_client

        runner = AgentRunner(STRATEGIST, mock_client)
        result = runner.think("テストタスク")

        assert result["analysis"] == "test analysis"
        assert result["confidence"] == 0.8
        assert len(runner.history) == 1

    @patch("system_e.agents.ClaudeClient")
    def test_think_handles_code_block_response(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = '```json\n{"analysis": "wrapped"}\n```'
        mock_client_cls.return_value = mock_client

        runner = AgentRunner(STRATEGIST, mock_client)
        result = runner.think("テスト")

        assert result["analysis"] == "wrapped"

    @patch("system_e.agents.ClaudeClient")
    def test_think_handles_non_json_response(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = "This is not JSON"
        mock_client_cls.return_value = mock_client

        runner = AgentRunner(STRATEGIST, mock_client)
        result = runner.think("テスト")

        assert result.get("parse_error") is True
        assert "raw_response" in result

    @patch("system_e.agents.ClaudeClient")
    def test_respond_to_passes_context(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({"response": "agreed"})
        mock_client_cls.return_value = mock_client

        runner = AgentRunner(CRITIC, mock_client)
        other_outputs = [{"agent": "Strategist", "result": {"strategy": "A"}}]
        result = runner.respond_to("テストトピック", other_outputs)

        assert result["response"] == "agreed"
        call_args = mock_client.generate.call_args
        assert "Strategist" in call_args.kwargs.get("prompt", call_args[1].get("prompt", ""))


# ─── Debate Tests ────────────────────────────────────────

class TestDebateProtocol:
    @patch("system_e.debate.ClaudeClient")
    def test_debate_structure(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({
            "analysis": "test",
            "confidence": 0.7,
        })
        mock_client_cls.return_value = mock_client

        debate = DebateProtocol(claude_client=mock_client, max_rounds=2)
        result = debate.run_debate("テスト議題")

        assert "debate_id" in result
        assert "rounds" in result
        assert len(result["rounds"]) >= 2
        assert result["rounds"][0]["type"] == "independent"
        assert result["rounds"][1]["type"] == "cross_critique"
        assert "synthesis" in result

    @patch("system_e.debate.ClaudeClient")
    def test_debate_3_rounds(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({"result": "ok", "confidence": 0.8})
        mock_client_cls.return_value = mock_client

        debate = DebateProtocol(claude_client=mock_client, max_rounds=3)
        result = debate.run_debate("テスト")

        assert len(result["rounds"]) == 3
        assert result["rounds"][2]["type"] == "convergence"


class TestQuickConsensus:
    @patch("system_e.debate.ClaudeClient")
    def test_quick_consensus_structure(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({
            "decision": "proceed",
            "confidence": 0.85,
        })
        mock_client_cls.return_value = mock_client

        qc = QuickConsensus(claude_client=mock_client)
        result = qc.propose_and_critique("テストタスク")

        assert "proposal" in result
        assert "critique" in result
        assert "synthesis" in result


# ─── Self-Improve Tests ──────────────────────────────────

class TestEvolutionEngine:
    @patch("system_e.self_improve.ClaudeClient")
    def test_default_strategy(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        engine = EvolutionEngine(claude_client=mock_client)
        strategy = engine._default_strategy()

        assert strategy["version"] == 1
        assert "posting_strategy" in strategy
        assert "content_strategy" in strategy
        ratios = strategy["posting_strategy"]["pillar_ratios"]
        assert abs(sum(ratios.values()) - 1.0) < 0.01

    @patch("system_e.self_improve.ClaudeClient")
    def test_evolve_strategy(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({
            "changes": ["テスト変更"],
            "posting_strategy": {},
            "content_strategy": {},
            "rationale": "テスト根拠",
            "expected_improvement": "テスト効果",
        })
        mock_client_cls.return_value = mock_client

        engine = EvolutionEngine(claude_client=mock_client)
        result = engine.evolve_strategy({"engagement_rate": 0.03})

        assert result["version"] >= 1
        assert "posting_strategy" in result


# ─── Meta-Optimizer Tests ────────────────────────────────

class TestMetaOptimizer:
    @patch("system_e.meta_optimizer.ClaudeClient")
    def test_diagnose_structure(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({
            "analysis": "healthy",
            "bottleneck": "none",
            "confidence": 0.9,
        })
        mock_client_cls.return_value = mock_client

        optimizer = MetaOptimizer(claude_client=mock_client)
        result = optimizer.diagnose()

        assert "health" in result
        assert "strategy_analysis" in result
        assert "optimization_plan" in result


# ─── Orchestrator Tests ──────────────────────────────────

class TestOrchestrator:
    @patch("system_e.orchestrator.ClaudeClient")
    def test_orchestrator_init(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        orch = Orchestrator(claude_client=mock_client)
        assert orch.debate is not None
        assert orch.quick is not None
        assert orch.evolution is not None
        assert orch.meta is not None
