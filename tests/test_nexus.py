"""
NEXUS System — テスト

全コンポーネントのテスト: ALPHA, OMEGA, BRIDGE, AGENTS, MONETIZE,
CRAWLER, FACTORY, TRIAL, DEBATE, EVOLUTION, ORCHESTRATOR, COMMON
Claude API呼び出しはモックで差し替え。
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from nexus.common import parse_json, parse_json_list, call_api, get_client, reset_client
from nexus.alpha.engine import (
    AlphaEngine, AlphaTask, AlphaOutput, TaskType, OutputQuality,
)
from nexus.omega.engine import (
    OmegaEngine, OmegaAnalysis, AnalysisType, OpportunitySignal,
)
from nexus.bridge.protocol import Bridge, CycleResult, CyclePhase
from nexus.agents.swarm import AgentSwarm, AgentTask, AgentRole, AgentResult
from nexus.monetize.pipeline import (
    MonetizePipeline, Deal, Channel, DealStatus,
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


@pytest.fixture
def tmp_data_dir(tmp_path):
    return tmp_path / "nexus_test"


# ─── Common (parse_json) Tests ───

class TestParseJson:
    def test_parse_full_json(self):
        text = '{"key": "value", "num": 42}'
        assert parse_json(text) == {"key": "value", "num": 42}

    def test_parse_json_with_surrounding_text(self):
        text = 'Here is the result: {"key": "value"} done.'
        assert parse_json(text) == {"key": "value"}

    def test_parse_json_code_block(self):
        text = '```json\n{"key": "value"}\n```'
        assert parse_json(text) == {"key": "value"}

    def test_parse_json_nested(self):
        text = 'prefix {"outer": {"inner": 1}} suffix'
        result = parse_json(text)
        assert result["outer"]["inner"] == 1

    def test_parse_json_default(self):
        assert parse_json("not json at all") == {}
        assert parse_json("", {"fallback": True}) == {"fallback": True}

    def test_parse_json_with_escaped_braces_in_string(self):
        text = '{"code": "function() { return {}; }", "ok": true}'
        result = parse_json(text)
        assert result["ok"] is True

    def test_parse_json_list_basic(self):
        text = '{"items": [1, 2, 3]}'
        assert parse_json_list(text, "items") == [1, 2, 3]

    def test_parse_json_list_missing_key(self):
        text = '{"other": [1]}'
        assert parse_json_list(text, "items") == []

    def test_parse_json_list_default(self):
        assert parse_json_list("bad", "items", ["x"]) == ["x"]


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

    def test_output_id_deterministic(self):
        """Same inputs at same time produce same ID"""
        ts = "2025-01-01T00:00:00"
        a = AlphaOutput(task_type=TaskType.CODE, content="test", quality=OutputQuality.DRAFT, timestamp=ts, output_id="")
        b = AlphaOutput(task_type=TaskType.CODE, content="test", quality=OutputQuality.DRAFT, timestamp=ts, output_id="")
        assert a.output_id == b.output_id


# ─── AlphaEngine Tests ───

class TestAlphaEngine:
    @patch("nexus.alpha.engine.call_api", return_value=MOCK_ALPHA_RESPONSE)
    def test_execute(self, mock_call, tmp_data_dir):
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
        mock_call.assert_called()

    @patch("nexus.alpha.engine.call_api", return_value=MOCK_ALPHA_RESPONSE)
    def test_execute_batch(self, mock_call, tmp_data_dir):
        engine = AlphaEngine(data_dir=tmp_data_dir / "alpha")
        tasks = [
            AlphaTask(task_type=TaskType.CONTENT, instruction="Task 1", priority=5),
            AlphaTask(task_type=TaskType.CODE, instruction="Task 2", priority=10),
        ]

        outputs = engine.execute_batch(tasks)
        assert len(outputs) == 2

    @patch("nexus.alpha.engine.call_api", return_value=MOCK_ALPHA_RESPONSE)
    def test_receive_feedback(self, mock_call, tmp_data_dir):
        engine = AlphaEngine(data_dir=tmp_data_dir / "alpha")
        task = AlphaTask(task_type=TaskType.CONTENT, instruction="Test")
        output = engine.execute(task)

        improved = engine.receive_feedback(
            output.output_id,
            {"score": 6, "improvements": ["改善A"]},
        )
        assert improved is not None

    @patch("nexus.alpha.engine.call_api")
    def test_execute_iterates_until_quality(self, mock_call, tmp_data_dir):
        """Low quality score triggers iteration, high score stops"""
        low_response = json.dumps({"content": "draft", "quality_score": 4})
        high_response = json.dumps({"content": "final", "quality_score": 9})
        mock_call.side_effect = [low_response, high_response]

        engine = AlphaEngine(data_dir=tmp_data_dir / "alpha")
        task = AlphaTask(task_type=TaskType.CONTENT, instruction="Test", max_iterations=3)
        output = engine.execute(task)
        assert output.quality == OutputQuality.PREMIUM
        assert mock_call.call_count == 2

    def test_find_output_not_found(self, tmp_data_dir):
        engine = AlphaEngine(data_dir=tmp_data_dir / "alpha")
        assert engine._find_output("nonexistent") is None

    @patch("nexus.alpha.engine.call_api", return_value=MOCK_ALPHA_RESPONSE)
    def test_find_output_from_file(self, mock_call, tmp_data_dir):
        engine = AlphaEngine(data_dir=tmp_data_dir / "alpha")
        task = AlphaTask(task_type=TaskType.CONTENT, instruction="Test")
        output = engine.execute(task)
        output_id = output.output_id

        # Clear in-memory, find from file
        engine.history.clear()
        found = engine._find_output(output_id)
        assert found is not None
        assert found.output_id == output_id


# ─── OmegaEngine Tests ───

class TestOmegaEngine:
    @patch("nexus.omega.engine.call_api", return_value=MOCK_OMEGA_RESPONSE)
    def test_analyze(self, mock_call, tmp_data_dir):
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
        mock_call.assert_called_once()

    @patch("nexus.omega.engine.call_api", return_value=MOCK_OMEGA_RESPONSE)
    def test_scan_opportunities(self, mock_call, tmp_data_dir):
        engine = OmegaEngine(data_dir=tmp_data_dir / "omega")
        signals = engine.scan_opportunities("AI市場")
        assert len(signals) == 1
        assert signals[0].title == "AI自動化ツール販売"

    def test_generate_alpha_tasks(self, tmp_data_dir):
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

    def test_get_feedback(self, tmp_data_dir):
        engine = OmegaEngine(data_dir=tmp_data_dir / "omega")
        analysis = OmegaAnalysis(
            analysis_type=AnalysisType.QUALITY_REVIEW,
            target_id="test",
            score=7.0,
            findings=["finding1"],
            improvements=["improve1"],
            revenue_multiplier=1.5,
        )
        feedback = engine.get_feedback(analysis)
        assert feedback["score"] == 7.0
        assert feedback["revenue_multiplier"] == 1.5


# ─── Bridge Tests ───

class TestBridge:
    @patch("nexus.omega.engine.call_api", return_value=MOCK_OMEGA_RESPONSE)
    @patch("nexus.alpha.engine.call_api", return_value=MOCK_ALPHA_RESPONSE)
    def test_run_cycle(self, mock_alpha, mock_omega, tmp_data_dir):
        bridge = Bridge(data_dir=tmp_data_dir / "bridge")
        result = bridge.run_cycle()

        assert isinstance(result, CycleResult)
        assert result.cycle_number == 1
        assert len(result.outputs) > 0
        assert CyclePhase.ALPHA_CREATE.value in result.phases_completed

    @patch("nexus.omega.engine.call_api", return_value=MOCK_OMEGA_RESPONSE)
    @patch("nexus.alpha.engine.call_api", return_value=MOCK_ALPHA_RESPONSE)
    def test_run_continuous(self, mock_alpha, mock_omega, tmp_data_dir):
        bridge = Bridge(data_dir=tmp_data_dir / "bridge")
        results = bridge.run_continuous(num_cycles=2)
        assert len(results) == 2
        assert results[0].cycle_number == 1
        assert results[1].cycle_number == 2

    @patch("nexus.omega.engine.call_api", return_value=MOCK_OMEGA_RESPONSE)
    @patch("nexus.alpha.engine.call_api", return_value=MOCK_ALPHA_RESPONSE)
    def test_performance_summary(self, mock_alpha, mock_omega, tmp_data_dir):
        bridge = Bridge(data_dir=tmp_data_dir / "bridge")
        bridge.run_cycle()
        summary = bridge.get_performance_summary()
        assert summary["cycles_completed"] == 1
        assert summary["total_outputs"] > 0

    def test_performance_summary_empty(self, tmp_data_dir):
        bridge = Bridge(data_dir=tmp_data_dir / "bridge")
        summary = bridge.get_performance_summary()
        assert summary["cycles"] == 0


# ─── AgentSwarm Tests ───

class TestAgentSwarm:
    @patch("nexus.agents.swarm.call_api", return_value=MOCK_AGENT_RESPONSE)
    def test_dispatch(self, mock_call, tmp_data_dir):
        swarm = AgentSwarm(max_workers=2, data_dir=tmp_data_dir / "agents")
        tasks = [
            AgentTask(role=AgentRole.HUNTER, instruction="テスト"),
            AgentTask(role=AgentRole.BUILDER, instruction="テスト"),
        ]

        results = swarm.dispatch(tasks)
        assert len(results) == 2
        assert all(r.success for r in results)

    @patch("nexus.agents.swarm.call_api", return_value=MOCK_AGENT_RESPONSE)
    def test_full_sweep(self, mock_call, tmp_data_dir):
        swarm = AgentSwarm(max_workers=3, data_dir=tmp_data_dir / "agents")
        results = swarm.full_sweep()
        assert len(results) == 5

    @patch("nexus.agents.swarm.call_api", return_value=MOCK_SYNTHESIS_RESPONSE)
    def test_synthesize(self, mock_call, tmp_data_dir):
        swarm = AgentSwarm(data_dir=tmp_data_dir / "agents")
        results = [
            AgentResult(role=AgentRole.HUNTER, output={"test": True}, raw_text="", success=True),
            AgentResult(role=AgentRole.BUILDER, output={"test": True}, raw_text="", success=True),
        ]

        synthesis = swarm.synthesize(results)
        assert "priority_actions" in synthesis

    def test_synthesize_empty(self, tmp_data_dir):
        swarm = AgentSwarm(data_dir=tmp_data_dir / "agents")
        result = swarm.synthesize([])
        assert "error" in result

    @patch("nexus.agents.swarm.call_api", return_value=MOCK_AGENT_RESPONSE)
    def test_targeted_sweep(self, mock_call, tmp_data_dir):
        swarm = AgentSwarm(max_workers=2, data_dir=tmp_data_dir / "agents")
        results = swarm.targeted_sweep("AI自動化", roles=[AgentRole.BUILDER, AgentRole.ANALYST])
        assert len(results) == 2


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

    @patch("nexus.monetize.pipeline.call_api", return_value=MOCK_MONETIZE_RESPONSE)
    def test_convert_to_deals(self, mock_call, tmp_data_dir):
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

    def test_update_deal_not_found(self, tmp_data_dir):
        pipeline = MonetizePipeline(data_dir=tmp_data_dir / "monetize")
        assert pipeline.update_deal_status("nonexistent", DealStatus.PAID) is None

    def test_generate_alpha_tasks_for_deal(self, tmp_data_dir):
        pipeline = MonetizePipeline(data_dir=tmp_data_dir / "monetize")
        deal = Deal(
            title="Test Deal", channel=Channel.FREELANCE,
            status=DealStatus.ACCEPTED, estimated_revenue=50000,
            deliverables=["成果物A", "成果物B"],
        )
        tasks = pipeline.generate_alpha_tasks_for_deal(deal)
        assert len(tasks) == 2


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

    def test_priority_score_calculation(self):
        immediate = Opportunity(
            title="A", opportunity_type=OpportunityType.DIGITAL_PRODUCT,
            feasibility=Feasibility.IMMEDIATE, estimated_revenue=10000, confidence=1.0,
        )
        long_term = Opportunity(
            title="B", opportunity_type=OpportunityType.DIGITAL_PRODUCT,
            feasibility=Feasibility.LONG_TERM, estimated_revenue=10000, confidence=1.0,
        )
        assert immediate.priority_score > long_term.priority_score

    @patch("nexus.crawler.opportunity_crawler.call_api", return_value=MOCK_CRAWL_RESPONSE)
    def test_crawl(self, mock_call, tmp_data_dir):
        crawler = OpportunityCrawler(data_dir=tmp_data_dir / "crawler")
        opps = crawler.crawl()
        assert len(opps) == 2
        assert opps[0].title == "プロンプトテンプレート販売"

    @patch("nexus.crawler.opportunity_crawler.call_api", return_value=MOCK_EVALUATE_RESPONSE)
    def test_evaluate(self, mock_call, tmp_data_dir):
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

    def test_get_top_opportunities(self, tmp_data_dir):
        crawler = OpportunityCrawler(data_dir=tmp_data_dir / "crawler")
        for i in range(5):
            crawler.opportunities.append(Opportunity(
                title=f"Opp {i}", opportunity_type=OpportunityType.DIGITAL_PRODUCT,
                feasibility=Feasibility.IMMEDIATE, estimated_revenue=(i + 1) * 10000, confidence=0.8,
            ))
        top = crawler.get_top_opportunities(limit=3)
        assert len(top) == 3
        assert top[0].estimated_revenue >= top[1].estimated_revenue


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

    @patch("nexus.factory.product_generator.call_api")
    def test_generate(self, mock_call, tmp_data_dir):
        mock_call.side_effect = [MOCK_PRODUCT_RESPONSE, MOCK_LISTING_RESPONSE]

        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        product = factory.generate("業務効率化", ProductCategory.PROMPT_PACK)
        assert product is not None
        assert product.status == ProductStatus.READY
        assert len(factory.products) == 1

    def test_get_product_not_found(self, tmp_data_dir):
        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        assert factory.get_product("nonexistent") is None


# ─── Trial Tests ───

class TestTrialRunner:
    def test_trial_creation(self):
        opp = Opportunity(
            title="テスト", opportunity_type=OpportunityType.DIGITAL_PRODUCT,
            feasibility=Feasibility.IMMEDIATE, estimated_revenue=30000, confidence=0.8,
        )
        trial = Trial(opportunity=opp, mode=TrialMode.DRY_RUN, result=TrialResult.PENDING)
        assert trial.trial_id != ""

    @patch("nexus.trial.trial_runner.call_api", return_value=MOCK_TRIAL_EVAL_RESPONSE)
    @patch("nexus.factory.product_generator.call_api")
    def test_run_trial_success(self, mock_factory, mock_trial, tmp_data_dir):
        mock_factory.side_effect = [MOCK_PRODUCT_RESPONSE, MOCK_LISTING_RESPONSE]

        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        runner = TrialRunner(factory=factory, data_dir=tmp_data_dir / "trial")

        opp = Opportunity(
            title="プロンプト販売", opportunity_type=OpportunityType.DIGITAL_PRODUCT,
            feasibility=Feasibility.IMMEDIATE, estimated_revenue=30000, confidence=0.8,
        )

        trial = runner.run_trial(opp)
        assert trial.result == TrialResult.SUCCESS
        assert trial.product is not None

    @patch("nexus.trial.trial_runner.call_api", return_value=json.dumps({
        "total_score": 20, "verdict": "failure", "weaknesses": ["品質低い"], "improvements": ["改善必要"],
    }))
    @patch("nexus.factory.product_generator.call_api")
    def test_run_trial_failure(self, mock_factory, mock_trial, tmp_data_dir):
        mock_factory.side_effect = [MOCK_PRODUCT_RESPONSE, MOCK_LISTING_RESPONSE]

        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        runner = TrialRunner(factory=factory, data_dir=tmp_data_dir / "trial")

        opp = Opportunity(
            title="失敗テスト", opportunity_type=OpportunityType.DIGITAL_PRODUCT,
            feasibility=Feasibility.IMMEDIATE, estimated_revenue=30000, confidence=0.8,
        )

        trial = runner.run_trial(opp)
        assert trial.result == TrialResult.FAILURE
        assert trial.debate_requested is True

    def test_get_stats(self, tmp_data_dir):
        runner = TrialRunner(data_dir=tmp_data_dir / "trial")
        stats = runner.get_stats()
        assert stats["total_trials"] == 0
        assert stats["success_rate"] == 0.0


# ─── Debate Tests ───

class TestDebateEngine:
    @patch("nexus.debate.debate_engine.call_api")
    def test_debate(self, mock_call, tmp_data_dir):
        mock_call.side_effect = [
            # Round 1
            MOCK_DEBATE_ALPHA, MOCK_DEBATE_OMEGA,
            # Round 2
            MOCK_DEBATE_ALPHA, MOCK_DEBATE_OMEGA,
            # Round 3
            MOCK_DEBATE_ALPHA, MOCK_DEBATE_OMEGA,
            # Synthesis
            MOCK_DEBATE_SYNTHESIS,
        ]

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
        assert len(result.rounds) >= 2
        assert result.should_retry is True
        assert result.confidence == 0.75

    @patch("nexus.debate.debate_engine.call_api")
    def test_debate_adaptive_termination(self, mock_call, tmp_data_dir):
        """High agreement after round 2 should skip round 3"""
        alpha_high_agree = json.dumps({
            "argument": "同意する",
            "proposed_improvements": ["A"],
            "counter_to_omega": "",
            "concessions": ["ポイント1", "ポイント2", "ポイント3"],
        })
        omega_high_agree = json.dumps({
            "argument": "概ね合意",
            "critical_issues": [],
            "counter_to_alpha": "",
            "constructive_suggestions": ["提案1", "提案2", "提案3"],
        })
        mock_call.side_effect = [
            MOCK_DEBATE_ALPHA, MOCK_DEBATE_OMEGA,   # Round 1
            alpha_high_agree, omega_high_agree,       # Round 2 (high agreement)
            MOCK_DEBATE_SYNTHESIS,                     # Synthesis
        ]

        engine = DebateEngine(data_dir=tmp_data_dir / "debate")
        opp = Opportunity(
            title="テスト", opportunity_type=OpportunityType.DIGITAL_PRODUCT,
            feasibility=Feasibility.IMMEDIATE, estimated_revenue=30000, confidence=0.8,
        )
        trial = Trial(opportunity=opp, mode=TrialMode.DRY_RUN, result=TrialResult.FAILURE)

        result = engine.debate(trial)
        assert len(result.rounds) == 2


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

    def test_extract_pattern_duplicate_detection(self, tmp_data_dir):
        """Duplicate patterns with same title should return existing"""
        evolver = Evolver(data_dir=tmp_data_dir / "evolution")
        opp = Opportunity(
            title="同じタイトル", opportunity_type=OpportunityType.DIGITAL_PRODUCT,
            feasibility=Feasibility.IMMEDIATE, estimated_revenue=30000, confidence=0.8,
        )
        trial1 = Trial(opportunity=opp, mode=TrialMode.DRY_RUN, result=TrialResult.SUCCESS,
                        evaluation={"total_score": 40}, lessons=["A"])
        trial2 = Trial(opportunity=opp, mode=TrialMode.DRY_RUN, result=TrialResult.SUCCESS,
                        evaluation={"total_score": 45}, lessons=["B"])

        p1 = evolver.extract_pattern(trial1)
        p2 = evolver.extract_pattern(trial2)
        assert p1.pattern_id == p2.pattern_id
        assert len(evolver.patterns) == 1

    @patch("nexus.evolution.evolver.call_api", return_value=MOCK_EVOLVE_RESPONSE)
    def test_evolve(self, mock_call, tmp_data_dir):
        evolver = Evolver(data_dir=tmp_data_dir / "evolution")
        evolver.patterns.append(SuccessPattern(
            pattern_id="p1", title="プロンプト販売", category="digital_product",
            description="テスト", revenue=30000, success_factors=["ニッチ特化"],
        ))

        gen = evolver.evolve()
        assert isinstance(gen, Generation)
        assert gen.gen_number == 1
        assert len(gen.patterns) == 1

    def test_evolve_no_patterns(self, tmp_data_dir):
        evolver = Evolver(data_dir=tmp_data_dir / "evolution")
        gen = evolver.evolve()
        assert gen.gen_number == 1
        assert len(gen.patterns) == 0

    @patch("nexus.evolution.evolver.call_api", return_value=MOCK_EVOLVE_RESPONSE)
    def test_replicate(self, mock_call, tmp_data_dir):
        evolver = Evolver(data_dir=tmp_data_dir / "evolution")
        pattern = SuccessPattern(
            pattern_id="p1", title="プロンプト販売", category="digital_product",
            description="テスト", revenue=30000, success_factors=["ニッチ特化"],
        )
        evolver.patterns.append(pattern)

        new_opps = evolver.replicate(pattern)
        assert len(new_opps) == 2
        assert pattern.replication_count == 2

    def test_get_evolution_stats(self, tmp_data_dir):
        evolver = Evolver(data_dir=tmp_data_dir / "evolution")
        stats = evolver.get_evolution_stats()
        assert stats["current_generation"] == 0
        assert stats["total_patterns"] == 0

    def test_persistence(self, tmp_data_dir):
        """State persists across instances"""
        evolver1 = Evolver(data_dir=tmp_data_dir / "evolution")
        opp = Opportunity(
            title="永続テスト", opportunity_type=OpportunityType.DIGITAL_PRODUCT,
            feasibility=Feasibility.IMMEDIATE, estimated_revenue=30000, confidence=0.8,
        )
        trial = Trial(opportunity=opp, mode=TrialMode.DRY_RUN, result=TrialResult.SUCCESS,
                       evaluation={"total_score": 40}, lessons=["test"])
        evolver1.extract_pattern(trial)

        evolver2 = Evolver(data_dir=tmp_data_dir / "evolution")
        assert len(evolver2.patterns) == 1
        assert evolver2.patterns[0].title == "永続テスト"


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
    @patch("nexus.agents.swarm.call_api", return_value=MOCK_AGENT_RESPONSE)
    @patch("nexus.monetize.pipeline.call_api", return_value=MOCK_MONETIZE_RESPONSE)
    @patch("nexus.omega.engine.call_api", return_value=MOCK_OMEGA_RESPONSE)
    @patch("nexus.alpha.engine.call_api", return_value=MOCK_ALPHA_RESPONSE)
    def test_orchestrator_single(self, mock_a, mock_o, mock_m, mock_s, tmp_data_dir):
        orchestrator = NexusOrchestrator(data_dir=tmp_data_dir)
        result = orchestrator.run(mode="single")
        assert result["mode"] == "single"
        assert "state" in result

    def test_orchestrator_unknown_mode(self, tmp_data_dir):
        orchestrator = NexusOrchestrator(data_dir=tmp_data_dir)
        result = orchestrator.run(mode="nonexistent")
        assert "error" in result


# ─── call_api Retry Tests ───

class TestCallApi:
    @patch("nexus.common.get_client")
    def test_call_api_success(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="hello")]
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = call_api(system="test", messages=[{"role": "user", "content": "hi"}])
        assert result == "hello"
        mock_client.messages.create.assert_called_once()

    @patch("nexus.common.get_client")
    @patch("nexus.common.time.sleep")
    def test_call_api_retries_on_rate_limit(self, mock_sleep, mock_get_client):
        from anthropic import RateLimitError
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]

        # First call raises RateLimitError, second succeeds
        rate_err = RateLimitError.__new__(RateLimitError)
        rate_err.status_code = 429
        rate_err.message = "rate limited"
        mock_client.messages.create.side_effect = [rate_err, mock_response]
        mock_get_client.return_value = mock_client

        result = call_api(system="test", messages=[{"role": "user", "content": "hi"}], max_retries=2)
        assert result == "ok"
        assert mock_client.messages.create.call_count == 2
        mock_sleep.assert_called_once_with(1)  # 2**0 = 1

    @patch("nexus.common.get_client")
    @patch("nexus.common.time.sleep")
    def test_call_api_retries_on_timeout(self, mock_sleep, mock_get_client):
        from anthropic import APITimeoutError
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="recovered")]

        timeout_err = APITimeoutError.__new__(APITimeoutError)
        timeout_err.message = "timeout"
        mock_client.messages.create.side_effect = [timeout_err, mock_response]
        mock_get_client.return_value = mock_client

        result = call_api(system="test", messages=[{"role": "user", "content": "hi"}], max_retries=2)
        assert result == "recovered"

    @patch("nexus.common.get_client")
    @patch("nexus.common.time.sleep")
    def test_call_api_retries_on_server_error(self, mock_sleep, mock_get_client):
        from anthropic import APIError
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]

        server_err = APIError.__new__(APIError)
        server_err.status_code = 500
        server_err.message = "server error"
        mock_client.messages.create.side_effect = [server_err, mock_response]
        mock_get_client.return_value = mock_client

        result = call_api(system="test", messages=[{"role": "user", "content": "hi"}], max_retries=2)
        assert result == "ok"

    @patch("nexus.common.get_client")
    def test_call_api_raises_non_retryable_error(self, mock_get_client):
        from anthropic import APIError
        mock_client = MagicMock()
        api_err = APIError.__new__(APIError)
        api_err.status_code = 400
        api_err.message = "bad request"
        mock_client.messages.create.side_effect = api_err
        mock_get_client.return_value = mock_client

        with pytest.raises(APIError):
            call_api(system="test", messages=[{"role": "user", "content": "hi"}])

    @patch("nexus.common.get_client")
    def test_call_api_passes_temperature(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        call_api(system="test", messages=[{"role": "user", "content": "hi"}], temperature=0.5)
        kwargs = mock_client.messages.create.call_args.kwargs
        assert kwargs["temperature"] == 0.5

    def test_get_client_singleton(self):
        reset_client()
        c1 = get_client()
        c2 = get_client()
        assert c1 is c2
        reset_client()

    def test_reset_client(self):
        reset_client()
        c1 = get_client()
        reset_client()
        c2 = get_client()
        assert c1 is not c2
        reset_client()


# ─── Additional Factory Tests ───

class TestProductGeneratorExtended:
    @patch("nexus.factory.product_generator.call_api")
    def test_generate_batch(self, mock_call, tmp_data_dir):
        mock_call.side_effect = [MOCK_PRODUCT_RESPONSE, MOCK_LISTING_RESPONSE] * 2

        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        themes = [
            {"theme": "テーマ1", "category": "prompt_pack", "price": 3000},
            {"theme": "テーマ2", "category": "automation_script", "price": 5000},
        ]
        products = factory.generate_batch(themes)
        assert len(products) == 2
        assert len(factory.products) == 2

    def test_get_catalog(self, tmp_data_dir):
        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        factory.products.append(Product(
            name="テスト商品", category=ProductCategory.PROMPT_PACK,
            status=ProductStatus.READY, price=3000,
        ))
        catalog = factory.get_catalog()
        assert len(catalog) == 1
        assert catalog[0]["name"] == "テスト商品"

    def test_get_catalog_empty(self, tmp_data_dir):
        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        assert factory.get_catalog() == []

    @patch("nexus.factory.product_generator.call_api")
    def test_get_product_found(self, mock_call, tmp_data_dir):
        mock_call.side_effect = [MOCK_PRODUCT_RESPONSE, MOCK_LISTING_RESPONSE]
        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        product = factory.generate("テスト", ProductCategory.PROMPT_PACK)

        found = factory.get_product(product.product_id)
        assert found is not None
        assert found.product_id == product.product_id

    @patch("nexus.factory.product_generator.call_api")
    def test_update_status(self, mock_call, tmp_data_dir):
        mock_call.side_effect = [MOCK_PRODUCT_RESPONSE, MOCK_LISTING_RESPONSE]
        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        product = factory.generate("テスト", ProductCategory.PROMPT_PACK)

        updated = factory.update_status(product.product_id, ProductStatus.LISTED)
        assert updated is not None
        assert updated.status == ProductStatus.LISTED

    def test_update_status_not_found(self, tmp_data_dir):
        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        assert factory.update_status("nonexistent", ProductStatus.LISTED) is None


# ─── Additional Trial Tests ───

class TestTrialRunnerExtended:
    def _make_opp(self, title="テスト", revenue=30000):
        return Opportunity(
            title=title, opportunity_type=OpportunityType.DIGITAL_PRODUCT,
            feasibility=Feasibility.IMMEDIATE, estimated_revenue=revenue, confidence=0.8,
        )

    @patch("nexus.trial.trial_runner.call_api", return_value=MOCK_TRIAL_EVAL_RESPONSE)
    @patch("nexus.factory.product_generator.call_api")
    def test_run_batch(self, mock_factory, mock_trial, tmp_data_dir):
        mock_factory.side_effect = [MOCK_PRODUCT_RESPONSE, MOCK_LISTING_RESPONSE] * 2
        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        runner = TrialRunner(factory=factory, data_dir=tmp_data_dir / "trial")

        opps = [self._make_opp("A", 50000), self._make_opp("B", 30000)]
        trials = runner.run_batch(opps)
        assert len(trials) == 2
        # Higher priority should be first (sorted by priority_score)
        assert trials[0].opportunity.estimated_revenue >= trials[1].opportunity.estimated_revenue

    @patch("nexus.trial.trial_runner.call_api", return_value=MOCK_TRIAL_EVAL_RESPONSE)
    @patch("nexus.factory.product_generator.call_api")
    def test_retry_trial(self, mock_factory, mock_trial, tmp_data_dir):
        mock_factory.side_effect = [MOCK_PRODUCT_RESPONSE, MOCK_LISTING_RESPONSE] * 2
        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        runner = TrialRunner(factory=factory, data_dir=tmp_data_dir / "trial")

        opp = self._make_opp("リトライ")
        trial = runner.run_trial(opp)
        retry = runner.retry_trial(trial.trial_id, improvements=["改善A", "改善B"])
        assert retry is not None
        assert retry.result == TrialResult.SUCCESS

    def test_retry_trial_not_found(self, tmp_data_dir):
        runner = TrialRunner(data_dir=tmp_data_dir / "trial")
        assert runner.retry_trial("nonexistent") is None

    @patch("nexus.trial.trial_runner.call_api", return_value=MOCK_TRIAL_EVAL_RESPONSE)
    @patch("nexus.factory.product_generator.call_api")
    def test_get_successes(self, mock_factory, mock_trial, tmp_data_dir):
        mock_factory.side_effect = [MOCK_PRODUCT_RESPONSE, MOCK_LISTING_RESPONSE]
        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        runner = TrialRunner(factory=factory, data_dir=tmp_data_dir / "trial")

        runner.run_trial(self._make_opp())
        assert len(runner.get_successes()) == 1

    @patch("nexus.trial.trial_runner.call_api", return_value=json.dumps({
        "total_score": 20, "verdict": "failure", "weaknesses": ["W"], "improvements": ["I"],
    }))
    @patch("nexus.factory.product_generator.call_api")
    def test_get_failures_needing_debate(self, mock_factory, mock_trial, tmp_data_dir):
        mock_factory.side_effect = [MOCK_PRODUCT_RESPONSE, MOCK_LISTING_RESPONSE]
        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        runner = TrialRunner(factory=factory, data_dir=tmp_data_dir / "trial")

        runner.run_trial(self._make_opp())
        failures = runner.get_failures_needing_debate()
        assert len(failures) == 1

    @patch("nexus.trial.trial_runner.call_api", return_value=json.dumps({
        "total_score": 28, "verdict": "partial", "strengths": [], "weaknesses": [], "improvements": ["X"],
    }))
    @patch("nexus.factory.product_generator.call_api")
    def test_run_trial_partial(self, mock_factory, mock_trial, tmp_data_dir):
        mock_factory.side_effect = [MOCK_PRODUCT_RESPONSE, MOCK_LISTING_RESPONSE]
        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        runner = TrialRunner(factory=factory, data_dir=tmp_data_dir / "trial")

        trial = runner.run_trial(self._make_opp())
        assert trial.result == TrialResult.PARTIAL
        assert trial.debate_requested is True

    @patch("nexus.trial.trial_runner.call_api", return_value=json.dumps({
        "total_score": 22, "verdict": "needs_debate", "weaknesses": ["W"], "improvements": [],
    }))
    @patch("nexus.factory.product_generator.call_api")
    def test_run_trial_needs_debate(self, mock_factory, mock_trial, tmp_data_dir):
        mock_factory.side_effect = [MOCK_PRODUCT_RESPONSE, MOCK_LISTING_RESPONSE]
        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        runner = TrialRunner(factory=factory, data_dir=tmp_data_dir / "trial")

        trial = runner.run_trial(self._make_opp())
        assert trial.result == TrialResult.NEEDS_DEBATE
        assert trial.debate_requested is True

    @patch("nexus.trial.trial_runner.call_api", return_value=MOCK_TRIAL_EVAL_RESPONSE)
    @patch("nexus.factory.product_generator.call_api")
    def test_get_success_rate(self, mock_factory, mock_trial, tmp_data_dir):
        mock_factory.side_effect = [MOCK_PRODUCT_RESPONSE, MOCK_LISTING_RESPONSE]
        factory = ProductGenerator(data_dir=tmp_data_dir / "factory")
        runner = TrialRunner(factory=factory, data_dir=tmp_data_dir / "trial")

        runner.run_trial(self._make_opp())
        assert runner.get_success_rate() == 1.0


# ─── Additional Debate Tests ───

class TestDebateEngineExtended:
    def test_get_improvement_plan(self, tmp_data_dir):
        engine = DebateEngine(data_dir=tmp_data_dir / "debate")
        result = DebateResult(
            trial_id="test",
            improvements=["改善A", "改善B", "改善C"],
            should_retry=True,
        )
        plan = engine.get_improvement_plan(result)
        assert plan == ["改善A", "改善B", "改善C"]


# ─── Additional Evolution Tests ───

class TestEvolverExtended:
    def test_get_top_patterns(self, tmp_data_dir):
        evolver = Evolver(data_dir=tmp_data_dir / "evolution")
        for i in range(5):
            evolver.patterns.append(SuccessPattern(
                pattern_id=f"p{i}", title=f"Pattern {i}", category="digital_product",
                description="test", revenue=10000, success_factors=[],
                total_revenue=(i + 1) * 10000,
            ))

        top = evolver.get_top_patterns(limit=3)
        assert len(top) == 3
        assert top[0].total_revenue >= top[1].total_revenue >= top[2].total_revenue

    def test_get_top_patterns_empty(self, tmp_data_dir):
        evolver = Evolver(data_dir=tmp_data_dir / "evolution")
        assert evolver.get_top_patterns() == []


# ─── Additional Monetize Tests ───

class TestMonetizePipelineExtended:
    @patch("nexus.monetize.pipeline.call_api", return_value="提案書の内容です")
    def test_generate_proposal(self, mock_call, tmp_data_dir):
        pipeline = MonetizePipeline(data_dir=tmp_data_dir / "monetize")
        deal = Deal(
            title="テスト案件", channel=Channel.FREELANCE,
            status=DealStatus.ACCEPTED, estimated_revenue=50000,
            description="テスト内容", deliverables=["成果物A"],
        )
        proposal = pipeline.generate_proposal(deal)
        assert len(proposal) > 0
        mock_call.assert_called_once()


# ─── Orchestrator Mode Tests ───

class TestNexusOrchestratorModes:
    @patch("nexus.agents.swarm.call_api", return_value=MOCK_AGENT_RESPONSE)
    @patch("nexus.monetize.pipeline.call_api", return_value=MOCK_MONETIZE_RESPONSE)
    @patch("nexus.omega.engine.call_api", return_value=MOCK_OMEGA_RESPONSE)
    @patch("nexus.alpha.engine.call_api", return_value=MOCK_ALPHA_RESPONSE)
    def test_orchestrator_continuous(self, mock_a, mock_o, mock_m, mock_s, tmp_data_dir):
        orchestrator = NexusOrchestrator(data_dir=tmp_data_dir)
        result = orchestrator.run(mode="continuous", num_cycles=2)
        assert result["mode"] == "continuous"
        assert len(result["cycles"]) == 2
        assert "performance" in result

    @patch("nexus.agents.swarm.call_api", return_value=MOCK_AGENT_RESPONSE)
    def test_orchestrator_swarm(self, mock_call, tmp_data_dir):
        orchestrator = NexusOrchestrator(data_dir=tmp_data_dir)
        result = orchestrator.run(mode="swarm")
        assert result["mode"] == "swarm"
        assert "agent_results" in result
        assert "synthesis" in result

    @patch("nexus.agents.swarm.call_api", return_value=MOCK_AGENT_RESPONSE)
    @patch("nexus.monetize.pipeline.call_api", return_value=MOCK_MONETIZE_RESPONSE)
    @patch("nexus.omega.engine.call_api", return_value=MOCK_OMEGA_RESPONSE)
    @patch("nexus.alpha.engine.call_api", return_value=MOCK_ALPHA_RESPONSE)
    def test_orchestrator_full(self, mock_a, mock_o, mock_m, mock_s, tmp_data_dir):
        orchestrator = NexusOrchestrator(data_dir=tmp_data_dir)
        result = orchestrator.run(mode="full", num_cycles=1)
        assert result["mode"] == "full"
        assert "swarm" in result
        assert "revenue_report" in result

    @patch("nexus.crawler.opportunity_crawler.call_api", return_value=MOCK_CRAWL_RESPONSE)
    def test_orchestrator_crawl(self, mock_call, tmp_data_dir):
        orchestrator = NexusOrchestrator(data_dir=tmp_data_dir)
        result = orchestrator.run(mode="crawl")
        assert result["mode"] == "crawl"
        assert result["opportunities_found"] > 0
        assert "top_opportunities" in result

    @patch("nexus.evolution.evolver.call_api", return_value=MOCK_EVOLVE_RESPONSE)
    def test_orchestrator_evolve(self, mock_call, tmp_data_dir):
        orchestrator = NexusOrchestrator(data_dir=tmp_data_dir)
        result = orchestrator.run(mode="evolve")
        assert result["mode"] == "evolve"
        assert "generation" in result
        assert "stats" in result

    @patch("nexus.trial.trial_runner.call_api", return_value=MOCK_TRIAL_EVAL_RESPONSE)
    @patch("nexus.factory.product_generator.call_api")
    @patch("nexus.crawler.opportunity_crawler.call_api", return_value=MOCK_CRAWL_RESPONSE)
    def test_orchestrator_trial(self, mock_crawl, mock_factory, mock_trial, tmp_data_dir):
        mock_factory.side_effect = [MOCK_PRODUCT_RESPONSE, MOCK_LISTING_RESPONSE] * 3
        orchestrator = NexusOrchestrator(data_dir=tmp_data_dir)
        result = orchestrator.run(mode="trial")
        assert result["mode"] == "trial"
        assert "trials" in result
        assert "stats" in result

    @patch("nexus.evolution.evolver.call_api", return_value=MOCK_EVOLVE_RESPONSE)
    @patch("nexus.monetize.pipeline.call_api", return_value=MOCK_MONETIZE_RESPONSE)
    @patch("nexus.debate.debate_engine.call_api")
    @patch("nexus.trial.trial_runner.call_api", return_value=MOCK_TRIAL_EVAL_RESPONSE)
    @patch("nexus.factory.product_generator.call_api")
    @patch("nexus.crawler.opportunity_crawler.call_api", return_value=MOCK_CRAWL_RESPONSE)
    def test_orchestrator_autonomous(self, mock_crawl, mock_factory, mock_trial,
                                      mock_debate, mock_monetize, mock_evolve, tmp_data_dir):
        mock_factory.side_effect = [MOCK_PRODUCT_RESPONSE, MOCK_LISTING_RESPONSE] * 10
        mock_debate.side_effect = [MOCK_DEBATE_ALPHA, MOCK_DEBATE_OMEGA] * 10 + [MOCK_DEBATE_SYNTHESIS] * 5
        orchestrator = NexusOrchestrator(data_dir=tmp_data_dir)
        result = orchestrator.run(mode="autonomous", num_cycles=1)
        assert result["mode"] == "autonomous"
        assert "loops" in result
        assert len(result["loops"]) == 1
        assert "state" in result
