"""
NEXUS System — テスト

全コンポーネントのテスト: ALPHA, OMEGA, BRIDGE, AGENTS, MONETIZE,
CRAWLER, FACTORY, TRIAL, DEBATE, EVOLUTION, ORCHESTRATOR
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
from nexus.crawler.opportunity_crawler import (
    OpportunityCrawler, Opportunity, OpportunityType, Feasibility,
)
from nexus.factory.product_generator import (
    ProductGenerator, Product, ProductCategory, ProductStatus,
)
from nexus.trial.trial_runner import (
    TrialRunner, Trial, TrialMode, TrialResult,
)
from nexus.debate.debate_engine import DebateEngine, DebateResult
from nexus.evolution.evolver import Evolver, SuccessPattern, Generation
from nexus.orchestrator.nexus_core import NexusOrchestrator, NexusState


# ─── Mock Responses ───

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

MOCK_CRAWL_RESPONSE = json.dumps({
    "opportunities": [
        {
            "title": "プロンプトテンプレート販売",
            "opportunity_type": "digital_product",
            "feasibility": "immediate",
            "estimated_revenue": 30000,
            "confidence": 0.8,
            "description": "業務効率化プロンプト集",
            "platform": "coconala",
            "competition_level": "中",
            "required_skills": ["プロンプト設計"],
            "action_steps": ["テーマ選定", "プロンプト作成", "出品"],
            "risks": ["競合増加"],
        },
        {
            "title": "AI自動化スクリプト受託",
            "opportunity_type": "freelance_gig",
            "feasibility": "short_term",
            "estimated_revenue": 100000,
            "confidence": 0.7,
            "description": "業務自動化スクリプトの受託開発",
            "platform": "lancers",
            "competition_level": "低",
            "required_skills": ["Python", "API"],
            "action_steps": ["提案書作成", "サンプル提出"],
            "risks": ["要件変更"],
        },
    ],
    "market_insights": "AI市場は拡大中",
    "top_3_recommendation": ["プロンプト販売", "自動化受託"],
})

MOCK_EVALUATE_RESPONSE = json.dumps({
    "evaluated": [
        {
            "opp_id": "test123",
            "alpha_verdict": {"score": 8, "reasoning": "実行可能"},
            "omega_verdict": {"score": 7, "reasoning": "競合注意"},
            "consensus_score": 7.5,
            "should_try": True,
            "try_order": 1,
        }
    ],
    "debate_summary": "ALPHA-OMEGAは概ね合意",
    "final_recommendation": "プロンプト販売から着手",
})

MOCK_PRODUCT_RESPONSE = json.dumps({
    "product_name": "業務効率化AIプロンプト集50選",
    "description": "すぐに使えるプロンプト集",
    "prompts": [
        {"title": "メール自動返信", "prompt": "...", "use_case": "営業", "expected_output": "返信文"},
    ],
    "price_suggestion": 3000,
    "target_audience": "ビジネスパーソン",
})

MOCK_LISTING_RESPONSE = json.dumps({
    "title": "AIプロンプト50選",
    "subtitle": "業務効率化に",
    "description": "すぐ使える",
    "bullet_points": ["即使用可能", "50種類", "業種別"],
    "tags": ["AI", "プロンプト"],
    "category_suggestion": "ビジネス",
})

MOCK_TRIAL_EVAL_RESPONSE = json.dumps({
    "scores": {"market_fit": 8, "quality": 7, "differentiation": 6, "pricing": 8, "scalability": 7},
    "total_score": 36,
    "verdict": "success",
    "strengths": ["価格妥当", "市場ニーズあり"],
    "weaknesses": ["差別化弱い"],
    "improvements": ["競合分析追加"],
    "would_you_buy": True,
})

MOCK_DEBATE_ALPHA = json.dumps({
    "argument": "プロンプト内容を充実させれば売れる",
    "proposed_improvements": ["事例追加", "業種別カスタマイズ"],
    "counter_to_omega": "差別化は事例で補える",
    "concessions": ["競合分析は必要"],
})

MOCK_DEBATE_OMEGA = json.dumps({
    "argument": "差別化なしでは埋もれる",
    "critical_issues": ["競合との差別化"],
    "counter_to_alpha": "事例だけでは不十分",
    "constructive_suggestions": ["ニッチ特化", "動画付き"],
})

MOCK_DEBATE_SYNTHESIS = json.dumps({
    "consensus": "ニッチ特化+事例充実で差別化",
    "improvements": ["業種特化", "成功事例追加", "動画説明付き"],
    "new_strategy": "不動産業界特化プロンプト集として再出品",
    "should_retry": True,
    "pivot_suggestion": "",
    "confidence": 0.75,
    "key_insight": "汎用よりニッチ特化が有効",
})

MOCK_EVOLVE_RESPONSE = json.dumps({
    "success_factors": ["ニッチ特化", "即使用可能"],
    "replication_ideas": [
        {"title": "飲食店向けプロンプト集", "description": "飲食店特化", "estimated_revenue": 30000, "platform": "coconala", "confidence": 0.7},
        {"title": "EC向け自動化テンプレート", "description": "EC特化", "estimated_revenue": 50000, "platform": "note", "confidence": 0.6},
    ],
    "improvements": ["価格引き上げ"],
    "kill_list": ["汎用テンプレート"],
    "next_gen_strategy": "業種特化を横展開",
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
        mock_alpha_client = MagicMock()
        mock_alpha_client.messages.create.return_value = _mock_anthropic_response(MOCK_ALPHA_RESPONSE)
        mock_alpha_cls.return_value = mock_alpha_client

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
        assert len(results) == 5

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


# ─── Crawler Tests ───

class TestOpportunityCrawler:
    def test_opportunity_creation(self):
        opp = Opportunity(
            title="テスト機会",
            opportunity_type=OpportunityType.DIGITAL_PRODUCT,
            feasibility=Feasibility.IMMEDIATE,
            estimated_revenue=50000,
            confidence=0.8,
        )
        assert opp.opp_id != ""
        assert opp.priority_score > 0

    def test_opportunity_to_dict(self):
        opp = Opportunity(
            title="API開発",
            opportunity_type=OpportunityType.API_SERVICE,
            feasibility=Feasibility.SHORT_TERM,
            estimated_revenue=100000,
            confidence=0.7,
        )
        d = opp.to_dict()
        assert d["opportunity_type"] == "api_service"
        assert d["feasibility"] == "short_term"

    @patch("nexus.crawler.opportunity_crawler.Anthropic")
    def test_crawl(self, mock_anthropic_cls, tmp_data_dir):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_anthropic_response(MOCK_CRAWL_RESPONSE)
        mock_anthropic_cls.return_value = mock_client

        crawler = OpportunityCrawler(data_dir=tmp_data_dir / "crawler")
        opps = crawler.crawl()
        assert len(opps) == 2
        assert opps[0].title == "プロンプトテンプレート販売"

    @patch("nexus.crawler.opportunity_crawler.Anthropic")
    def test_evaluate(self, mock_anthropic_cls, tmp_data_dir):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_anthropic_response(MOCK_EVALUATE_RESPONSE)
        mock_anthropic_cls.return_value = mock_client

        crawler = OpportunityCrawler(data_dir=tmp_data_dir / "crawler")
        opp = Opportunity(
            title="テスト", opportunity_type=OpportunityType.DIGITAL_PRODUCT,
            feasibility=Feasibility.IMMEDIATE, estimated_revenue=30000, confidence=0.8,
        )
        crawler.opportunities.append(opp)
        result = crawler.evaluate()
        assert len(result) > 0

    def test_record_trial_result(self, tmp_data_dir):
        crawler = OpportunityCrawler(data_dir=tmp_data_dir / "crawler")
        crawler.record_trial_result("test_id", success=True, actual_revenue=50000, notes="成功")
        assert len(crawler.crawl_history) == 1


# ─── Factory Tests ───

class TestProductGenerator:
    def test_product_creation(self):
        product = Product(
            name="テスト商品",
            category=ProductCategory.PROMPT_PACK,
            status=ProductStatus.DRAFT,
            price=3000,
        )
        assert product.product_id != ""

    def test_product_to_dict(self):
        product = Product(
            name="プロンプト集",
            category=ProductCategory.PROMPT_PACK,
            status=ProductStatus.READY,
            price=5000,
            description="テスト",
        )
        d = product.to_dict()
        assert d["category"] == "prompt_pack"
        assert d["price"] == 5000

    @patch("nexus.factory.product_generator.Anthropic")
    def test_generate(self, mock_anthropic_cls, tmp_data_dir):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _mock_anthropic_response(MOCK_PRODUCT_RESPONSE),
            _mock_anthropic_response(MOCK_LISTING_RESPONSE),
        ]
        mock_anthropic_cls.return_value = mock_client

        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        product = factory.generate("業務効率化", ProductCategory.PROMPT_PACK)
        assert product is not None
        assert product.status == ProductStatus.READY
        assert len(factory.products) == 1


# ─── Trial Tests ───

class TestTrialRunner:
    def test_trial_creation(self):
        opp = Opportunity(
            title="テスト", opportunity_type=OpportunityType.DIGITAL_PRODUCT,
            feasibility=Feasibility.IMMEDIATE, estimated_revenue=30000, confidence=0.8,
        )
        trial = Trial(opportunity=opp, mode=TrialMode.DRY_RUN, result=TrialResult.PENDING)
        assert trial.trial_id != ""

    @patch("nexus.factory.product_generator.Anthropic")
    @patch("nexus.trial.trial_runner.Anthropic")
    def test_run_trial_success(self, mock_trial_cls, mock_factory_cls, tmp_data_dir):
        # Factory mock
        mock_factory_client = MagicMock()
        mock_factory_client.messages.create.side_effect = [
            _mock_anthropic_response(MOCK_PRODUCT_RESPONSE),
            _mock_anthropic_response(MOCK_LISTING_RESPONSE),
        ]
        mock_factory_cls.return_value = mock_factory_client

        # Trial evaluation mock
        mock_trial_client = MagicMock()
        mock_trial_client.messages.create.return_value = _mock_anthropic_response(MOCK_TRIAL_EVAL_RESPONSE)
        mock_trial_cls.return_value = mock_trial_client

        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        runner = TrialRunner(factory=factory, data_dir=tmp_data_dir / "trial")

        opp = Opportunity(
            title="プロンプト販売", opportunity_type=OpportunityType.DIGITAL_PRODUCT,
            feasibility=Feasibility.IMMEDIATE, estimated_revenue=30000, confidence=0.8,
        )

        trial = runner.run_trial(opp)
        assert trial.result == TrialResult.SUCCESS
        assert trial.product is not None

    def test_get_stats(self, tmp_data_dir):
        runner = TrialRunner(data_dir=tmp_data_dir / "trial")
        stats = runner.get_stats()
        assert stats["total_trials"] == 0
        assert stats["success_rate"] == 0.0


# ─── Debate Tests ───

class TestDebateEngine:
    @patch("nexus.debate.debate_engine.Anthropic")
    def test_debate(self, mock_anthropic_cls, tmp_data_dir):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            # Round 1
            _mock_anthropic_response(MOCK_DEBATE_ALPHA),
            _mock_anthropic_response(MOCK_DEBATE_OMEGA),
            # Round 2
            _mock_anthropic_response(MOCK_DEBATE_ALPHA),
            _mock_anthropic_response(MOCK_DEBATE_OMEGA),
            # Round 3
            _mock_anthropic_response(MOCK_DEBATE_ALPHA),
            _mock_anthropic_response(MOCK_DEBATE_OMEGA),
            # Synthesis
            _mock_anthropic_response(MOCK_DEBATE_SYNTHESIS),
        ]
        mock_anthropic_cls.return_value = mock_client

        engine = DebateEngine(data_dir=tmp_data_dir / "debate")

        opp = Opportunity(
            title="テスト", opportunity_type=OpportunityType.DIGITAL_PRODUCT,
            feasibility=Feasibility.IMMEDIATE, estimated_revenue=30000, confidence=0.8,
        )
        trial = Trial(
            opportunity=opp, mode=TrialMode.DRY_RUN, result=TrialResult.FAILURE,
            evaluation={"total_score": 25, "strengths": [], "weaknesses": ["差別化"]},
            lessons=["差別化が必要"],
        )

        result = engine.debate(trial)
        assert isinstance(result, DebateResult)
        assert len(result.rounds) == 3
        assert result.should_retry is True
        assert result.confidence == 0.75


# ─── Evolution Tests ───

class TestEvolver:
    def test_success_pattern(self):
        pattern = SuccessPattern(
            pattern_id="test123",
            title="プロンプト販売",
            category="digital_product",
            description="テスト",
            revenue=30000,
            success_factors=["ニッチ特化"],
        )
        d = pattern.to_dict()
        assert d["revenue"] == 30000

    def test_extract_pattern(self, tmp_data_dir):
        evolver = Evolver(data_dir=tmp_data_dir / "evolution")
        opp = Opportunity(
            title="テスト成功", opportunity_type=OpportunityType.DIGITAL_PRODUCT,
            feasibility=Feasibility.IMMEDIATE, estimated_revenue=30000, confidence=0.8,
        )
        trial = Trial(
            opportunity=opp, mode=TrialMode.DRY_RUN, result=TrialResult.SUCCESS,
            evaluation={"total_score": 40}, lessons=["ニッチ特化が有効"],
        )

        pattern = evolver.extract_pattern(trial)
        assert pattern is not None
        assert pattern.title == "テスト成功"
        assert len(evolver.patterns) == 1

    def test_extract_pattern_failure_returns_none(self, tmp_data_dir):
        evolver = Evolver(data_dir=tmp_data_dir / "evolution")
        opp = Opportunity(
            title="失敗", opportunity_type=OpportunityType.DIGITAL_PRODUCT,
            feasibility=Feasibility.IMMEDIATE, estimated_revenue=30000, confidence=0.8,
        )
        trial = Trial(
            opportunity=opp, mode=TrialMode.DRY_RUN, result=TrialResult.FAILURE,
        )

        pattern = evolver.extract_pattern(trial)
        assert pattern is None

    @patch("nexus.evolution.evolver.Anthropic")
    def test_evolve(self, mock_anthropic_cls, tmp_data_dir):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_anthropic_response(MOCK_EVOLVE_RESPONSE)
        mock_anthropic_cls.return_value = mock_client

        evolver = Evolver(data_dir=tmp_data_dir / "evolution")
        evolver.patterns.append(SuccessPattern(
            pattern_id="p1", title="プロンプト販売", category="digital_product",
            description="テスト", revenue=30000, success_factors=["ニッチ特化"],
        ))

        gen = evolver.evolve()
        assert isinstance(gen, Generation)
        assert gen.gen_number == 1
        assert len(gen.patterns) == 1

    @patch("nexus.evolution.evolver.Anthropic")
    def test_replicate(self, mock_anthropic_cls, tmp_data_dir):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_anthropic_response(MOCK_EVOLVE_RESPONSE)
        mock_anthropic_cls.return_value = mock_client

        evolver = Evolver(data_dir=tmp_data_dir / "evolution")
        pattern = SuccessPattern(
            pattern_id="p1", title="プロンプト販売", category="digital_product",
            description="テスト", revenue=30000, success_factors=["ニッチ特化"],
        )
        evolver.patterns.append(pattern)

        new_opps = evolver.replicate(pattern)
        assert len(new_opps) == 2
        assert pattern.replication_count == 2  # 0 (initial) + 2 (replicated)

    def test_get_evolution_stats(self, tmp_data_dir):
        evolver = Evolver(data_dir=tmp_data_dir / "evolution")
        stats = evolver.get_evolution_stats()
        assert stats["current_generation"] == 0
        assert stats["total_patterns"] == 0


# ─── NexusState Tests ───

class TestNexusState:
    def test_state_creation(self):
        state = NexusState()
        assert state.cycles_completed == 0
        assert state.total_revenue_potential == 0.0
        assert state.autonomous_loops == 0

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
        assert "autonomous_loops" in d
        assert "trials_run" in d
        assert "patterns_discovered" in d


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
