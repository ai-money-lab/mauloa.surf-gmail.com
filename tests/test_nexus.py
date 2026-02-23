"""
NEXUS System — テスト

ALPHA, OMEGA, BRIDGE, AGENTS, MONETIZE, ORCHESTRATOR 全コンポーネントのテスト。
Claude API呼び出しはモックで差し替え。
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nexus.alpha.engine import (
    AlphaEngine, AlphaTask, AlphaOutput, TaskType, OutputQuality,
)
from nexus.omega.engine import (
    OmegaEngine, OmegaAnalysis, AnalysisType, OpportunitySignal,
)
from nexus.bridge.protocol import Bridge, CycleResult, CyclePhase
from nexus.agents.swarm import AgentSwarm, AgentTask, AgentRole, AgentResult
from nexus.monetize.pipeline import (
    MonetizePipeline, Deal, Channel, DealStatus, RevenueReport,
)
from nexus.orchestrator.nexus_core import NexusOrchestrator, NexusState


# ─── Fixtures ───

MOCK_ALPHA_RESPONSE = json.dumps({
    "content": "AIフリーランス案件獲得の完全ガイド",
    "revenue_strategy": "技術記事をLead Magnetとして活用",
    "next_actions": ["記事を公開", "SNSで拡散", "フォローアップ"],
    "quality_score": 8,
    "improvement_notes": "SEO最適化が可能",
})

MOCK_OMEGA_RESPONSE = json.dumps({
    "score": 7.5,
    "findings": ["コンテンツ品質は高い", "SEOが弱い"],
    "improvements": ["キーワード追加", "メタデータ最適化"],
    "new_opportunities": [
        {
            "title": "AI自動化ツール販売",
            "description": "小規模事業者向けAIツール",
            "estimated_revenue": 50000,
            "confidence": 0.8,
        }
    ],
    "revenue_multiplier": 1.5,
    "alpha_tasks": [],
})

MOCK_MONETIZE_RESPONSE = json.dumps({
    "deals": [
        {
            "title": "AI記事執筆代行",
            "channel": "freelance",
            "estimated_revenue": 30000,
            "description": "技術記事の執筆代行サービス",
            "deliverables": ["記事本文", "SEOレポート"],
            "action_plan": ["提案書作成", "サンプル提出"],
        }
    ],
    "immediate_actions": ["ランサーズに登録"],
    "revenue_timeline": "1週間以内に初回収益",
})

MOCK_AGENT_RESPONSE = json.dumps({
    "opportunities": [
        {
            "title": "ChatGPTラッパーツール",
            "platform": "自社サイト",
            "estimated_revenue": 100000,
            "requirements": "Python, API",
            "ai_advantage": "高い",
            "urgency": 8,
        }
    ],
    "market_trends": "AI活用ツールの需要急増",
    "action_items": ["プロトタイプ作成"],
})

MOCK_SYNTHESIS_RESPONSE = json.dumps({
    "priority_actions": [
        {"action": "AIツール販売開始", "agent": "builder"},
        {"action": "技術ブログ開設", "agent": "writer"},
    ],
    "synergies": ["BUILDER×WRITER: ツール紹介記事"],
    "total_revenue_estimate": 200000,
    "execution_plan": "1週間でプロトタイプ→2週目で販売開始",
})


def _mock_anthropic_response(text: str) -> MagicMock:
    """Anthropicレスポンスのモック生成"""
    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.text = text
    mock_response.content = [mock_content]
    return mock_response


@pytest.fixture
def tmp_data_dir(tmp_path):
    return tmp_path / "nexus_test"


# ─── AlphaOutput Tests ───

class TestAlphaOutput:
    def test_output_creation(self):
        output = AlphaOutput(
            task_type=TaskType.CONTENT,
            content="テスト記事",
            quality=OutputQuality.DRAFT,
        )
        assert output.output_id != ""
        assert output.task_type == TaskType.CONTENT
        assert output.timestamp != ""

    def test_output_to_dict(self):
        output = AlphaOutput(
            task_type=TaskType.CODE,
            content="def hello(): pass",
            quality=OutputQuality.FINAL,
            revenue_potential=5000.0,
        )
        d = output.to_dict()
        assert d["task_type"] == "code"
        assert d["quality"] == "final"
        assert d["revenue_potential"] == 5000.0


# ─── AlphaEngine Tests ───

class TestAlphaEngine:
    @patch("nexus.alpha.engine.Anthropic")
    def test_execute(self, mock_anthropic_cls, tmp_data_dir):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_anthropic_response(MOCK_ALPHA_RESPONSE)
        mock_anthropic_cls.return_value = mock_client

        engine = AlphaEngine(data_dir=tmp_data_dir / "alpha")
        task = AlphaTask(
            task_type=TaskType.CONTENT,
            instruction="テスト記事を生成",
        )

        output = engine.execute(task)
        assert output is not None
        assert output.quality == OutputQuality.PREMIUM  # score=8
        assert output.revenue_potential > 0
        assert len(engine.history) == 1

    @patch("nexus.alpha.engine.Anthropic")
    def test_execute_batch(self, mock_anthropic_cls, tmp_data_dir):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_anthropic_response(MOCK_ALPHA_RESPONSE)
        mock_anthropic_cls.return_value = mock_client

        engine = AlphaEngine(data_dir=tmp_data_dir / "alpha")
        tasks = [
            AlphaTask(task_type=TaskType.CONTENT, instruction="Task 1", priority=5),
            AlphaTask(task_type=TaskType.CODE, instruction="Task 2", priority=10),
        ]

        outputs = engine.execute_batch(tasks)
        assert len(outputs) == 2

    @patch("nexus.alpha.engine.Anthropic")
    def test_receive_feedback(self, mock_anthropic_cls, tmp_data_dir):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_anthropic_response(MOCK_ALPHA_RESPONSE)
        mock_anthropic_cls.return_value = mock_client

        engine = AlphaEngine(data_dir=tmp_data_dir / "alpha")
        task = AlphaTask(task_type=TaskType.CONTENT, instruction="Test")
        output = engine.execute(task)

        improved = engine.receive_feedback(
            output.output_id,
            {"score": 6, "improvements": ["改善A"]},
        )
        assert improved is not None


# ─── OmegaEngine Tests ───

class TestOmegaEngine:
    @patch("nexus.omega.engine.Anthropic")
    def test_analyze(self, mock_anthropic_cls, tmp_data_dir):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_anthropic_response(MOCK_OMEGA_RESPONSE)
        mock_anthropic_cls.return_value = mock_client

        engine = OmegaEngine(data_dir=tmp_data_dir / "omega")
        alpha_output = AlphaOutput(
            task_type=TaskType.CONTENT,
            content="テスト記事",
            quality=OutputQuality.DRAFT,
        )

        analysis = engine.analyze(alpha_output)
        assert analysis.score == 7.5
        assert len(analysis.findings) == 2
        assert len(analysis.improvements) == 2

    @patch("nexus.omega.engine.Anthropic")
    def test_scan_opportunities(self, mock_anthropic_cls, tmp_data_dir):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_anthropic_response(MOCK_OMEGA_RESPONSE)
        mock_anthropic_cls.return_value = mock_client

        engine = OmegaEngine(data_dir=tmp_data_dir / "omega")
        signals = engine.scan_opportunities("AI市場")
        assert len(signals) == 1
        assert signals[0].title == "AI自動化ツール販売"

    @patch("nexus.omega.engine.Anthropic")
    def test_generate_alpha_tasks(self, mock_anthropic_cls, tmp_data_dir):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        engine = OmegaEngine(data_dir=tmp_data_dir / "omega")
        opp = OpportunitySignal(
            title="AIツール販売",
            description="自動化ツールを販売する",
            estimated_revenue=50000,
            confidence=0.8,
        )

        tasks = engine.generate_alpha_tasks([opp])
        assert len(tasks) == 1
        assert tasks[0].source == "omega"


# ─── Bridge Tests ───

class TestBridge:
    @patch("nexus.omega.engine.Anthropic")
    @patch("nexus.alpha.engine.Anthropic")
    def test_run_cycle(self, mock_alpha_cls, mock_omega_cls, tmp_data_dir):
        # ALPHAモック
        mock_alpha_client = MagicMock()
        mock_alpha_client.messages.create.return_value = _mock_anthropic_response(MOCK_ALPHA_RESPONSE)
        mock_alpha_cls.return_value = mock_alpha_client

        # OMEGAモック
        mock_omega_client = MagicMock()
        mock_omega_client.messages.create.return_value = _mock_anthropic_response(MOCK_OMEGA_RESPONSE)
        mock_omega_cls.return_value = mock_omega_client

        bridge = Bridge(data_dir=tmp_data_dir / "bridge")
        result = bridge.run_cycle()

        assert isinstance(result, CycleResult)
        assert result.cycle_number == 1
        assert len(result.outputs) > 0
        assert CyclePhase.ALPHA_CREATE.value in result.phases_completed


# ─── AgentSwarm Tests ───

class TestAgentSwarm:
    @patch("nexus.agents.swarm.Anthropic")
    def test_dispatch(self, mock_anthropic_cls, tmp_data_dir):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_anthropic_response(MOCK_AGENT_RESPONSE)
        mock_anthropic_cls.return_value = mock_client

        swarm = AgentSwarm(max_workers=2, data_dir=tmp_data_dir / "agents")
        tasks = [
            AgentTask(role=AgentRole.HUNTER, instruction="テスト"),
            AgentTask(role=AgentRole.BUILDER, instruction="テスト"),
        ]

        results = swarm.dispatch(tasks)
        assert len(results) == 2
        assert all(r.success for r in results)

    @patch("nexus.agents.swarm.Anthropic")
    def test_full_sweep(self, mock_anthropic_cls, tmp_data_dir):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_anthropic_response(MOCK_AGENT_RESPONSE)
        mock_anthropic_cls.return_value = mock_client

        swarm = AgentSwarm(max_workers=3, data_dir=tmp_data_dir / "agents")
        results = swarm.full_sweep()
        assert len(results) == 5  # 全5種類のエージェント

    @patch("nexus.agents.swarm.Anthropic")
    def test_synthesize(self, mock_anthropic_cls, tmp_data_dir):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_anthropic_response(MOCK_SYNTHESIS_RESPONSE)
        mock_anthropic_cls.return_value = mock_client

        swarm = AgentSwarm(data_dir=tmp_data_dir / "agents")
        results = [
            AgentResult(role=AgentRole.HUNTER, output={"test": True}, raw_text="", success=True),
            AgentResult(role=AgentRole.BUILDER, output={"test": True}, raw_text="", success=True),
        ]

        synthesis = swarm.synthesize(results)
        assert "priority_actions" in synthesis


# ─── MonetizePipeline Tests ───

class TestMonetizePipeline:
    def test_deal_creation(self):
        deal = Deal(
            title="テスト案件",
            channel=Channel.FREELANCE,
            status=DealStatus.IDENTIFIED,
            estimated_revenue=50000,
        )
        assert deal.deal_id != ""
        assert deal.channel == Channel.FREELANCE

    def test_deal_to_dict(self):
        deal = Deal(
            title="API開発",
            channel=Channel.DIGITAL_PRODUCT,
            status=DealStatus.PROPOSED,
            estimated_revenue=100000,
        )
        d = deal.to_dict()
        assert d["channel"] == "digital_product"
        assert d["status"] == "proposed"

    @patch("nexus.monetize.pipeline.Anthropic")
    def test_convert_to_deals(self, mock_anthropic_cls, tmp_data_dir):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_anthropic_response(MOCK_MONETIZE_RESPONSE)
        mock_anthropic_cls.return_value = mock_client

        pipeline = MonetizePipeline(data_dir=tmp_data_dir / "monetize")
        outputs = [
            AlphaOutput(
                task_type=TaskType.CONTENT,
                content="テスト記事",
                quality=OutputQuality.FINAL,
            ),
        ]

        deals = pipeline.convert_to_deals(outputs)
        assert len(deals) == 1
        assert deals[0].title == "AI記事執筆代行"

    def test_revenue_report(self, tmp_data_dir):
        pipeline = MonetizePipeline(data_dir=tmp_data_dir / "monetize")
        pipeline.deals = [
            Deal(title="A", channel=Channel.FREELANCE, status=DealStatus.PAID,
                 estimated_revenue=50000, actual_revenue=50000),
            Deal(title="B", channel=Channel.CONTENT, status=DealStatus.IN_PROGRESS,
                 estimated_revenue=30000),
        ]

        report = pipeline.get_revenue_report()
        assert report.total_estimated == 80000
        assert report.total_actual == 50000
        assert report.pipeline_health > 0

    def test_update_deal_status(self, tmp_data_dir):
        pipeline = MonetizePipeline(data_dir=tmp_data_dir / "monetize")
        deal = Deal(title="Test", channel=Channel.FREELANCE,
                    status=DealStatus.IDENTIFIED, estimated_revenue=10000)
        pipeline.deals.append(deal)

        updated = pipeline.update_deal_status(deal.deal_id, DealStatus.PAID, actual_revenue=10000)
        assert updated is not None
        assert updated.status == DealStatus.PAID
        assert updated.actual_revenue == 10000


# ─── NexusState Tests ───

class TestNexusState:
    def test_state_creation(self):
        state = NexusState()
        assert state.cycles_completed == 0
        assert state.total_revenue_potential == 0.0

    def test_state_update(self):
        state = NexusState()
        state.cycles_completed = 5
        state.total_revenue_potential = 100000
        state.update()
        assert state.last_updated != ""

    def test_state_to_dict(self):
        state = NexusState()
        d = state.to_dict()
        assert "cycles_completed" in d
        assert "total_revenue_potential" in d


# ─── Integration (all mocked) ───

class TestNexusIntegration:
    @patch("nexus.agents.swarm.Anthropic")
    @patch("nexus.monetize.pipeline.Anthropic")
    @patch("nexus.omega.engine.Anthropic")
    @patch("nexus.alpha.engine.Anthropic")
    def test_orchestrator_single(self, mock_a, mock_o, mock_m, mock_s, tmp_data_dir):
        for mock_cls in [mock_a, mock_o, mock_m, mock_s]:
            client = MagicMock()
            client.messages.create.return_value = _mock_anthropic_response(MOCK_ALPHA_RESPONSE)
            mock_cls.return_value = client

        orchestrator = NexusOrchestrator(data_dir=tmp_data_dir)
        result = orchestrator.run(mode="single")
        assert result["mode"] == "single"
        assert "state" in result
