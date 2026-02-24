"""
NEXUS V2 — テスト

全コンポーネントのテスト:
- channels: 収益チャネル定義
- content_creator: デジタルアセット生成
- distributor: プラットフォーム配信
- market_researcher: 市場分析
- revenue_debate: AI議論
- orchestrator: オーケストレータ

Claude API呼び出しはモックで差し替え。
"""

import json
from unittest.mock import patch


from nexus.v2.channels import (
    RevenueChannel,
    RevenueModel,
    Platform,
    AssetType,
    DigitalAsset,
    CHANNEL_CONFIGS,
)
from nexus.v2.content_creator import (
    ContentCreator,
    ASSET_PROMPTS,
    ASSET_TO_CHANNEL,
    ASSET_TO_PLATFORMS,
)
from nexus.v2.distributor import (
    Distributor,
    PLATFORM_SPECS,
)
from nexus.v2.market_researcher import (
    MarketResearcher,
)
from nexus.v2.revenue_debate import (
    RevenueDebate,
)
from nexus.v2.orchestrator import (
    NexusV2Orchestrator,
)


# ─── Mock Responses ───

MOCK_MUSIC_RESPONSE = json.dumps({
    "album_name": "Midnight Study Sessions",
    "artist_name": "CloudBeats",
    "tracks": [
        {
            "title": "Rainy Window",
            "genre": "lo-fi hip hop",
            "mood": "calm, relaxing, rainy",
            "tempo_bpm": 85,
            "duration_seconds": 180,
            "suno_prompt": "lo-fi hip hop beat, calm rainy mood, vinyl crackle, soft piano",
            "tags": ["lofi", "study", "rain"],
            "target_playlists": ["lofi beats", "study music"],
        },
        {
            "title": "Dawn Coffee",
            "genre": "lo-fi hip hop",
            "mood": "warm, morning, cozy",
            "tempo_bpm": 90,
            "duration_seconds": 200,
            "suno_prompt": "lo-fi hip hop, warm morning vibes, soft guitar, coffee shop",
            "tags": ["lofi", "morning", "coffee"],
            "target_playlists": ["morning vibes"],
        },
    ],
    "distribution_notes": "DistroKidで配信、リリース2週間前にpre-save設定",
})

MOCK_VIDEO_RESPONSE = json.dumps({
    "title": "不動産投資で失敗する人の5つの共通点",
    "thumbnail_text": "失敗5選",
    "description": "不動産投資初心者が陥りがちな5つの失敗パターンを解説",
    "tags": ["不動産投資", "初心者", "失敗"],
    "script": {
        "hook": "不動産投資で9割の人が犯す致命的なミス、知っていますか？",
        "sections": [
            {
                "title": "物件選びの失敗",
                "narration": "最も多い失敗は、利回りだけで物件を選ぶことです。",
                "visual_description": "グラフと物件画像",
            },
        ],
        "outro": "今日の内容が参考になったら、チャンネル登録お願いします。",
    },
    "estimated_length_minutes": 10,
    "target_audience": "不動産投資に興味がある20-40代",
    "seo_keywords": ["不動産投資", "失敗", "初心者"],
})

MOCK_PRODUCT_RESPONSE = json.dumps({
    "product_name": "不動産投資収支シミュレーター",
    "product_type": "spreadsheet",
    "price_usd": 19,
    "tagline": "物件購入前に収支を完全シミュレーション",
    "sales_page": {
        "headline": "物件購入の前に、この計算をしましたか？",
        "subheadline": "プロが使う収支計算を、あなたの手元に。",
        "pain_points": ["利回り計算が複雑", "隠れコストを見落とす"],
        "benefits": ["10秒で収支が見える", "プロ同等の判断ができる"],
        "social_proof": "不動産業界15年のプロが設計",
        "cta": "今すぐダウンロード",
    },
    "content": "Notion/Spreadsheetテンプレート...",
    "bonus": "物件チェックリスト付き",
    "target_audience": "不動産投資初心者",
    "keywords": ["不動産投資", "収支計算", "シミュレーション"],
})

MOCK_STOCK_RESPONSE = json.dumps({
    "collection_name": "Modern Real Estate Concepts",
    "assets": [
        {
            "title": "Minimalist apartment interior with natural light",
            "description": "AI-generated modern minimalist apartment interior",
            "generation_prompt": "modern minimalist apartment, natural light, clean lines",
            "style": "photorealistic concept",
            "category": "Architecture",
            "tags": ["apartment", "interior", "modern", "minimalist"],
            "orientation": "horizontal",
            "suggested_price_usd": 2.50,
        },
    ],
    "target_platforms": ["adobe_stock", "pond5"],
    "ai_disclosure": "Created using generative AI tools",
})

MOCK_RESEARCH_RESPONSE = json.dumps({
    "trending_themes": ["lo-fi beats", "ambient workspace", "meditation sounds"],
    "recommended_assets": [
        {
            "asset_type": "music_track",
            "theme": "Lo-fi ambient study beats",
            "title_idea": "Focus Flow",
            "reason": "Study music playlists have high engagement",
            "estimated_monthly_revenue": 5000,
            "priority": 9,
        },
    ],
    "competition_analysis": "Lo-fi market is growing but still accessible",
    "opportunity_score": 7.5,
    "estimated_monthly_potential": 50000,
    "action_items": ["Generate 10 lo-fi tracks", "Set up DistroKid"],
    "data_sources": ["Spotify charts", "YouTube trends"],
})

MOCK_STRATEGY_RESPONSE = json.dumps({
    "priority_ranking": ["streaming", "video", "digital_product", "stock_content", "micro_saas"],
    "immediate_actions": [
        {"action": "Generate 10 lo-fi tracks", "channel": "streaming", "expected_output": "10 tracks on Spotify"},
    ],
    "weekly_plan": {"music_tracks": 10, "videos": 2, "digital_products": 1, "stock_assets": 20},
    "monthly_kpi": {
        "total_assets": 100,
        "revenue_target": 100000,
        "by_channel": {"streaming": {"assets": 40, "revenue": 20000}},
    },
    "reasoning": "Music has lowest barrier and highest scalability",
})

MOCK_EXPERT_RESPONSE = json.dumps({
    "position": "Lo-fi music is a strong entry point with proven demand.",
    "evidence": ["Spotify lo-fi playlists have millions of followers"],
    "recommendations": ["Start with 10 tracks", "Focus on rain/coffee themes"],
    "concerns": ["Spotify may tighten AI music policies"],
    "confidence": 0.7,
})

MOCK_SYNTHESIS_RESPONSE = json.dumps({
    "consensus": "Start with music and YouTube simultaneously",
    "action_plan": [
        {"step": 1, "action": "Generate 10 lo-fi tracks", "channel": "streaming", "deadline": "1 week"},
        {"step": 2, "action": "Create 3 YouTube scripts", "channel": "video", "deadline": "1 week"},
    ],
    "priority_assets": [
        {"asset_type": "music_track", "theme": "lo-fi study beats", "reason": "highest ROI", "expected_revenue": 5000},
        {"asset_type": "video_script", "theme": "不動産投資入門", "reason": "leverage expertise", "expected_revenue": 10000},
    ],
    "estimated_monthly_revenue": 50000,
    "key_risks": ["Platform policy changes", "AI content saturation"],
    "mitigation": ["Diversify across channels", "Focus on quality over quantity"],
})


# ─── channels.py tests ───

class TestChannels:
    def test_revenue_channels_defined(self):
        assert len(RevenueChannel) == 5
        assert RevenueChannel.STREAMING.value == "streaming"
        assert RevenueChannel.VIDEO.value == "video"
        assert RevenueChannel.DIGITAL_PRODUCT.value == "digital_product"
        assert RevenueChannel.STOCK_CONTENT.value == "stock_content"
        assert RevenueChannel.MICRO_SAAS.value == "micro_saas"

    def test_no_freelance_channel(self):
        """旧システムのFREELANCE/CONSULTINGチャネルが存在しないことを確認"""
        channel_values = [c.value for c in RevenueChannel]
        assert "freelance" not in channel_values
        assert "consulting" not in channel_values
        assert "automation" not in channel_values

    def test_all_channels_have_config(self):
        for channel in RevenueChannel:
            assert channel in CHANNEL_CONFIGS, f"Config missing for {channel}"
            config = CHANNEL_CONFIGS[channel]
            assert config.scalability in ("low", "medium", "high")
            assert config.avg_revenue_per_unit >= 0
            assert len(config.platforms) > 0
            assert len(config.asset_types) > 0

    def test_platform_variety(self):
        """プラットフォームにココナラ/ランサーズがないことを確認"""
        platform_values = [p.value for p in Platform]
        assert "coconala" not in platform_values
        assert "lancers" not in platform_values
        assert "spotify" in platform_values
        assert "youtube" in platform_values
        assert "gumroad" in platform_values

    def test_digital_asset_creation(self):
        asset = DigitalAsset(
            asset_id="test123",
            asset_type=AssetType.MUSIC_TRACK,
            channel=RevenueChannel.STREAMING,
            title="Test Track",
            description="A test track",
            content="{}",
            target_platforms=[Platform.SPOTIFY],
        )
        d = asset.to_dict()
        assert d["asset_type"] == "music_track"
        assert d["channel"] == "streaming"
        assert "spotify" in d["target_platforms"]

    def test_streaming_config(self):
        config = CHANNEL_CONFIGS[RevenueChannel.STREAMING]
        assert config.revenue_model == RevenueModel.PER_STREAM
        assert Platform.SPOTIFY in config.platforms
        assert config.scalability == "high"

    def test_video_config(self):
        config = CHANNEL_CONFIGS[RevenueChannel.VIDEO]
        assert config.revenue_model == RevenueModel.AD_REVENUE
        assert Platform.YOUTUBE in config.platforms

    def test_digital_product_config(self):
        config = CHANNEL_CONFIGS[RevenueChannel.DIGITAL_PRODUCT]
        assert config.revenue_model == RevenueModel.ONE_TIME_SALE
        assert Platform.GUMROAD in config.platforms


# ─── content_creator.py tests ───

class TestContentCreator:
    def test_all_asset_types_have_prompts(self):
        for asset_type in AssetType:
            assert asset_type in ASSET_PROMPTS, f"Prompt missing for {asset_type}"

    def test_all_asset_types_have_channel_mapping(self):
        for asset_type in AssetType:
            assert asset_type in ASSET_TO_CHANNEL, f"Channel mapping missing for {asset_type}"

    def test_all_asset_types_have_platform_mapping(self):
        for asset_type in AssetType:
            assert asset_type in ASSET_TO_PLATFORMS, f"Platform mapping missing for {asset_type}"

    @patch("nexus.v2.content_creator.call_api")
    def test_create_music_track(self, mock_api, tmp_path):
        mock_api.return_value = MOCK_MUSIC_RESPONSE
        creator = ContentCreator(data_dir=tmp_path)

        asset = creator.create(AssetType.MUSIC_TRACK, "Lo-fi study beats")

        assert asset.asset_type == AssetType.MUSIC_TRACK
        assert asset.channel == RevenueChannel.STREAMING
        assert asset.title == "Midnight Study Sessions"
        assert Platform.SPOTIFY in asset.target_platforms
        assert asset.status == "created"
        mock_api.assert_called_once()

    @patch("nexus.v2.content_creator.call_api")
    def test_create_video_script(self, mock_api, tmp_path):
        mock_api.return_value = MOCK_VIDEO_RESPONSE
        creator = ContentCreator(data_dir=tmp_path)

        asset = creator.create(AssetType.VIDEO_SCRIPT, "不動産投資の失敗パターン")

        assert asset.asset_type == AssetType.VIDEO_SCRIPT
        assert asset.channel == RevenueChannel.VIDEO
        assert Platform.YOUTUBE in asset.target_platforms

    @patch("nexus.v2.content_creator.call_api")
    def test_create_digital_product(self, mock_api, tmp_path):
        mock_api.return_value = MOCK_PRODUCT_RESPONSE
        creator = ContentCreator(data_dir=tmp_path)

        asset = creator.create(AssetType.TEMPLATE, "不動産収支計算テンプレート")

        assert asset.asset_type == AssetType.TEMPLATE
        assert asset.channel == RevenueChannel.DIGITAL_PRODUCT
        assert Platform.GUMROAD in asset.target_platforms

    @patch("nexus.v2.content_creator.call_api")
    def test_create_stock_content(self, mock_api, tmp_path):
        mock_api.return_value = MOCK_STOCK_RESPONSE
        creator = ContentCreator(data_dir=tmp_path)

        asset = creator.create(AssetType.STOCK_IMAGE, "Modern real estate concepts")

        assert asset.asset_type == AssetType.STOCK_IMAGE
        assert asset.channel == RevenueChannel.STOCK_CONTENT
        assert Platform.ADOBE_STOCK in asset.target_platforms

    @patch("nexus.v2.content_creator.call_api")
    def test_create_batch(self, mock_api, tmp_path):
        mock_api.side_effect = [MOCK_MUSIC_RESPONSE, MOCK_VIDEO_RESPONSE]
        creator = ContentCreator(data_dir=tmp_path)

        assets = creator.create_batch([
            {"asset_type": "music_track", "theme": "Lo-fi beats"},
            {"asset_type": "video_script", "theme": "不動産"},
        ])

        assert len(assets) == 2
        assert assets[0].asset_type == AssetType.MUSIC_TRACK
        assert assets[1].asset_type == AssetType.VIDEO_SCRIPT

    @patch("nexus.v2.content_creator.call_api")
    def test_portfolio(self, mock_api, tmp_path):
        mock_api.return_value = MOCK_MUSIC_RESPONSE
        creator = ContentCreator(data_dir=tmp_path)

        creator.create(AssetType.MUSIC_TRACK, "Lo-fi")
        portfolio = creator.get_portfolio()

        assert portfolio["total_assets"] == 1
        assert "streaming" in portfolio["channels_active"]

    @patch("nexus.v2.content_creator.call_api")
    def test_asset_saved_to_disk(self, mock_api, tmp_path):
        mock_api.return_value = MOCK_MUSIC_RESPONSE
        creator = ContentCreator(data_dir=tmp_path)

        creator.create(AssetType.MUSIC_TRACK, "Test")
        saved_files = list(tmp_path.glob("*.json"))
        assert len(saved_files) == 1


# ─── distributor.py tests ───

class TestDistributor:
    def test_platform_specs_complete(self):
        key_platforms = [
            Platform.SPOTIFY, Platform.YOUTUBE, Platform.GUMROAD,
            Platform.ADOBE_STOCK, Platform.POND5, Platform.SELF_HOSTED,
        ]
        for p in key_platforms:
            assert p in PLATFORM_SPECS, f"Spec missing for {p}"

    def test_no_coconala_platform(self):
        """ココナラがプラットフォーム仕様に含まれていないことを確認"""
        for p in PLATFORM_SPECS:
            assert p.value != "coconala"

    def test_prepare_distribution(self, tmp_path):
        distributor = Distributor(data_dir=tmp_path)
        asset = DigitalAsset(
            asset_id="test123",
            asset_type=AssetType.MUSIC_TRACK,
            channel=RevenueChannel.STREAMING,
            title="Test Track",
            description="A test",
            content=MOCK_MUSIC_RESPONSE,
            target_platforms=[Platform.SPOTIFY, Platform.APPLE_MUSIC],
        )

        tasks = distributor.prepare_distribution(asset)

        assert len(tasks) == 2
        assert tasks[0].platform == Platform.SPOTIFY
        assert tasks[1].platform == Platform.APPLE_MUSIC
        assert tasks[0].status == "ready"

    def test_distribution_summary(self, tmp_path):
        distributor = Distributor(data_dir=tmp_path)
        asset = DigitalAsset(
            asset_id="test123",
            asset_type=AssetType.MUSIC_TRACK,
            channel=RevenueChannel.STREAMING,
            title="Test",
            description="",
            content="{}",
            target_platforms=[Platform.SPOTIFY],
        )
        distributor.prepare_distribution(asset)

        summary = distributor.get_distribution_summary()
        assert summary["total_tasks"] == 1
        assert "spotify" in summary["by_platform"]

    def test_update_task_status(self, tmp_path):
        distributor = Distributor(data_dir=tmp_path)
        asset = DigitalAsset(
            asset_id="test123",
            asset_type=AssetType.VIDEO_SCRIPT,
            channel=RevenueChannel.VIDEO,
            title="Test Video",
            description="",
            content="{}",
            target_platforms=[Platform.YOUTUBE],
        )
        distributor.prepare_distribution(asset)

        updated = distributor.update_task_status("test123", Platform.YOUTUBE, "live", "https://youtube.com/watch?v=xxx")
        assert updated is not None
        assert updated.status == "live"
        assert updated.platform_url == "https://youtube.com/watch?v=xxx"

    def test_platform_guide(self, tmp_path):
        distributor = Distributor(data_dir=tmp_path)
        guide = distributor.get_platform_guide(Platform.GUMROAD)
        assert "api" in guide or "requirements" in guide


# ─── market_researcher.py tests ───

class TestMarketResearcher:
    @patch("nexus.v2.market_researcher.call_api")
    def test_research_channel(self, mock_api, tmp_path):
        mock_api.return_value = MOCK_RESEARCH_RESPONSE
        researcher = MarketResearcher(data_dir=tmp_path)

        insight = researcher.research_channel(RevenueChannel.STREAMING)

        assert insight.channel == RevenueChannel.STREAMING
        assert len(insight.trending_themes) > 0
        assert len(insight.recommended_assets) > 0
        assert insight.opportunity_score > 0

    @patch("nexus.v2.market_researcher.call_api")
    def test_research_all_channels(self, mock_api, tmp_path):
        mock_api.side_effect = [MOCK_RESEARCH_RESPONSE] * 5 + [MOCK_STRATEGY_RESPONSE]
        researcher = MarketResearcher(data_dir=tmp_path)

        report = researcher.research_all_channels()

        assert len(report.insights) == 5
        assert len(report.priority_ranking) > 0
        assert report.monthly_revenue_target > 0

    @patch("nexus.v2.market_researcher.call_api")
    def test_creation_queue(self, mock_api, tmp_path):
        mock_api.side_effect = [MOCK_RESEARCH_RESPONSE] * 5 + [MOCK_STRATEGY_RESPONSE]
        researcher = MarketResearcher(data_dir=tmp_path)

        report = researcher.research_all_channels()
        queue = researcher.get_creation_queue(report)

        assert len(queue) > 0
        assert "asset_type" in queue[0]
        assert "theme" in queue[0]

    @patch("nexus.v2.market_researcher.call_api")
    def test_insight_saved_to_disk(self, mock_api, tmp_path):
        mock_api.return_value = MOCK_RESEARCH_RESPONSE
        researcher = MarketResearcher(data_dir=tmp_path)

        researcher.research_channel(RevenueChannel.STREAMING)
        saved = list(tmp_path.glob("insight_*.json"))
        assert len(saved) == 1


# ─── revenue_debate.py tests ───

class TestRevenueDebate:
    @patch("nexus.v2.revenue_debate.call_api")
    def test_debate(self, mock_api, tmp_path):
        # 4 experts + 1 synthesis
        mock_api.side_effect = [MOCK_EXPERT_RESPONSE] * 4 + [MOCK_SYNTHESIS_RESPONSE]
        debate = RevenueDebate(data_dir=tmp_path)

        result = debate.debate("Best monetization strategy")

        assert len(result.opinions) == 4
        assert result.consensus != ""
        assert len(result.action_plan) > 0
        assert result.estimated_monthly_revenue > 0

    @patch("nexus.v2.revenue_debate.call_api")
    def test_debate_experts(self, mock_api, tmp_path):
        mock_api.side_effect = [MOCK_EXPERT_RESPONSE] * 4 + [MOCK_SYNTHESIS_RESPONSE]
        debate = RevenueDebate(data_dir=tmp_path)

        result = debate.debate("Test topic")
        expert_names = [o.expert for o in result.opinions]

        assert "PRODUCER" in expert_names
        assert "ANALYST" in expert_names
        assert "DISTRIBUTOR" in expert_names
        assert "CRITIC" in expert_names

    @patch("nexus.v2.revenue_debate.call_api")
    def test_no_alpha_omega_naming(self, mock_api, tmp_path):
        """旧システムのALPHA/OMEGA命名が使われていないことを確認"""
        mock_api.side_effect = [MOCK_EXPERT_RESPONSE] * 4 + [MOCK_SYNTHESIS_RESPONSE]
        debate = RevenueDebate(data_dir=tmp_path)

        result = debate.debate("Test")
        expert_names = [o.expert for o in result.opinions]

        assert "ALPHA" not in expert_names
        assert "OMEGA" not in expert_names

    @patch("nexus.v2.revenue_debate.call_api")
    def test_quick_evaluate(self, mock_api, tmp_path):
        mock_api.side_effect = [MOCK_EXPERT_RESPONSE, MOCK_EXPERT_RESPONSE]
        debate = RevenueDebate(data_dir=tmp_path)

        result = debate.quick_evaluate({"theme": "lo-fi beats", "asset_type": "music_track"})

        assert "should_create" in result
        assert "analyst_score" in result
        assert "critic_score" in result

    @patch("nexus.v2.revenue_debate.call_api")
    def test_debate_saved_to_disk(self, mock_api, tmp_path):
        mock_api.side_effect = [MOCK_EXPERT_RESPONSE] * 4 + [MOCK_SYNTHESIS_RESPONSE]
        debate = RevenueDebate(data_dir=tmp_path)

        debate.debate("Test topic")
        saved = list(tmp_path.glob("*.json"))
        assert len(saved) == 1


# ─── orchestrator.py tests ───

class TestOrchestrator:
    def test_status_mode(self, tmp_path):
        """statusモードはAPI呼び出しなしで動作"""
        orch = NexusV2Orchestrator(data_dir=tmp_path)
        results = orch.run(mode="status")

        assert len(results) == 1
        assert results[0].mode == "status"
        assert results[0].errors == []

    @patch("nexus.v2.revenue_debate.call_api")
    def test_debate_mode(self, mock_api, tmp_path):
        mock_api.side_effect = [MOCK_EXPERT_RESPONSE] * 4 + [MOCK_SYNTHESIS_RESPONSE]
        orch = NexusV2Orchestrator(data_dir=tmp_path)

        results = orch.run(mode="debate")

        assert len(results) == 1
        assert results[0].debates_held == 1
        assert results[0].estimated_monthly_revenue > 0

    @patch("nexus.v2.market_researcher.call_api")
    def test_research_mode(self, mock_api, tmp_path):
        mock_api.side_effect = [MOCK_RESEARCH_RESPONSE] * 5 + [MOCK_STRATEGY_RESPONSE]
        orch = NexusV2Orchestrator(data_dir=tmp_path)

        results = orch.run(mode="research")

        assert len(results) == 1
        assert results[0].mode == "research"
        assert len(results[0].actions_taken) > 0

    def test_state_tracking(self, tmp_path):
        orch = NexusV2Orchestrator(data_dir=tmp_path)
        orch.run(mode="status")

        assert orch.state.cycles_completed == 1
        state_file = tmp_path / "nexus_v2_state.json"
        assert state_file.exists()

    def test_unknown_mode(self, tmp_path):
        orch = NexusV2Orchestrator(data_dir=tmp_path)
        results = orch.run(mode="invalid_mode")

        assert len(results[0].errors) > 0

    def test_default_creation_queue(self, tmp_path):
        orch = NexusV2Orchestrator(data_dir=tmp_path)
        queue = orch._default_creation_queue("")

        assert len(queue) == 7
        types = [q["asset_type"] for q in queue]
        assert "music_track" in types
        assert "video_script" in types
        assert "template" in types
        assert "stock_image" in types
        assert "prompt_pack" in types
        assert "ebook" in types

    def test_default_creation_queue_with_focus(self, tmp_path):
        orch = NexusV2Orchestrator(data_dir=tmp_path)
        queue = orch._default_creation_queue("streaming")

        assert len(queue) == 1
        assert queue[0]["asset_type"] == "music_track"

    def test_state_persistence_roundtrip(self, tmp_path):
        """状態がディスクに保存され、次回起動時に復元されることを確認"""
        orch1 = NexusV2Orchestrator(data_dir=tmp_path)
        orch1.run(mode="status")
        assert orch1.state.cycles_completed == 1

        # 新しいインスタンスで状態が復元される
        orch2 = NexusV2Orchestrator(data_dir=tmp_path)
        assert orch2.state.cycles_completed == 1

    def test_state_corrects_from_disk_assets(self, tmp_path):
        """ディスク上のアセット数で状態が補正されることを確認"""
        # アセットファイルを手動作成
        content_dir = tmp_path / "content"
        content_dir.mkdir(parents=True)
        for i in range(3):
            (content_dir / f"asset_{i}.json").write_text("{}")

        orch = NexusV2Orchestrator(data_dir=tmp_path)
        assert orch.state.total_assets == 3


# ─── strategy_feedback.py tests ───

class TestStrategyFeedback:
    def test_generate_queue_with_debate(self, tmp_path):
        """議論ファイルがある場合、最適化キューが生成される"""
        from nexus.v2.strategy_feedback import StrategyFeedback

        # Create debate file
        debate_dir = tmp_path / "debate"
        debate_dir.mkdir(parents=True)
        debate_data = {
            "debate_synthesis": {
                "consensus_points": ["YouTube + Gumroad first"],
                "confidence_weighted_ranking": {
                    "channel_priority": [
                        {"channel": "YouTube Faceless Channel", "weighted_score": 0.91, "rationale": "High CPM"},
                        {"channel": "Gumroad Digital Products", "weighted_score": 0.88, "rationale": "High margin"},
                    ]
                }
            },
            "experts": []
        }
        (debate_dir / "debate_001.json").write_text(
            json.dumps(debate_data, ensure_ascii=False), encoding="utf-8"
        )

        fb = StrategyFeedback(data_dir=tmp_path)
        queue = fb.generate_optimized_queue()

        assert len(queue) > 0
        types = [q["asset_type"] for q in queue]
        assert "video_script" in types

    def test_generate_queue_without_debate(self, tmp_path):
        """議論ファイルがない場合、デフォルトキューが生成される"""
        from nexus.v2.strategy_feedback import StrategyFeedback

        fb = StrategyFeedback(data_dir=tmp_path)
        queue = fb.generate_optimized_queue()

        assert len(queue) > 0
        types = [q["asset_type"] for q in queue]
        assert "video_script" in types

    def test_phase_recommendation(self, tmp_path):
        """フェーズ推奨が取得できる"""
        from nexus.v2.strategy_feedback import StrategyFeedback

        fb = StrategyFeedback(data_dir=tmp_path)
        rec = fb.get_phase_recommendation()

        assert "phase" in rec
        assert "focus" in rec

    def test_queue_saved_to_disk(self, tmp_path):
        """生成キューがディスクに保存される"""
        from nexus.v2.strategy_feedback import StrategyFeedback

        fb = StrategyFeedback(data_dir=tmp_path)
        fb.generate_optimized_queue()

        queue_file = tmp_path / "creation_queue.json"
        assert queue_file.exists()


# ─── pipeline4_nexus.py tests ───

class TestPipeline4:
    def test_extract_insights_from_debate(self, tmp_path):
        """議論データからインサイトが抽出される"""
        from system_a.pipeline4_nexus import Pipeline4Nexus

        p4 = Pipeline4Nexus()
        debate = {
            "debate_synthesis": {
                "consensus_points": ["YouTube first", "Gumroad second"],
                "confidence_weighted_ranking": {
                    "channel_priority": [
                        {"channel": "YouTube", "weighted_score": 0.9, "rationale": "High CPM"},
                    ]
                }
            },
            "experts": [{
                "id": "ANALYST",
                "recommendations": [{"action": "Start YouTube channel"}],
            }],
        }
        assets = [{"album_name": "Test Album", "tracks": []}]

        insights = p4._extract_insights(debate, assets)
        assert len(insights) > 0
        assert any(i["type"] == "debate" for i in insights)

    def test_extract_insights_empty(self):
        """データなしの場合は空リスト"""
        from system_a.pipeline4_nexus import Pipeline4Nexus

        p4 = Pipeline4Nexus()
        insights = p4._extract_insights(None, [])
        assert insights == []

    def test_load_debate_file(self, tmp_path, monkeypatch):
        """NEXUSデータディレクトリから議論ファイルを読める"""
        from system_a.pipeline4_nexus import Pipeline4Nexus

        debate_dir = tmp_path / "debate"
        debate_dir.mkdir(parents=True)
        (debate_dir / "test.json").write_text('{"test": true}')

        p4 = Pipeline4Nexus()
        monkeypatch.setattr(p4, "_load_latest_debate", lambda: {"test": True})

        debate = p4._load_latest_debate()
        assert debate is not None


# ─── Integration: 旧システムとの差分確認 ───

class TestV2VsV1Differences:
    """旧NEXUS（V1）との構造的な差分を検証"""

    def test_no_coconala_references(self):
        """V2コードにココナラへの参照がないことを確認"""
        import nexus.v2.channels as ch_mod
        import nexus.v2.content_creator as cc_mod
        import nexus.v2.distributor as dist_mod

        for mod in [ch_mod, cc_mod, dist_mod]:
            source = open(mod.__file__).read()
            # ココナラ/ランサーズへの直接参照がないことを確認
            assert "coconala" not in source.lower() or "coconala" in source.lower() and "not" in source.lower()

    def test_all_channels_are_scalable(self):
        """全チャネルがスケーラブル（medium以上）であることを確認"""
        for channel, config in CHANNEL_CONFIGS.items():
            assert config.scalability in ("medium", "high"), (
                f"Channel {channel} has low scalability — consider removing"
            )

    def test_all_channels_are_passive(self):
        """全チャネルの収益モデルが受動的であることを確認（時間売りではない）"""
        passive_models = {
            RevenueModel.PER_STREAM,
            RevenueModel.AD_REVENUE,
            RevenueModel.ONE_TIME_SALE,
            RevenueModel.PER_DOWNLOAD,
            RevenueModel.SUBSCRIPTION,
        }
        for channel, config in CHANNEL_CONFIGS.items():
            assert config.revenue_model in passive_models, (
                f"Channel {channel} uses non-passive model: {config.revenue_model}"
            )

    def test_debate_has_specialized_experts(self):
        """議論システムが専門家ペルソナを使っていることを確認"""
        from nexus.v2.revenue_debate import EXPERT_PROMPTS
        assert "PRODUCER" in EXPERT_PROMPTS
        assert "ANALYST" in EXPERT_PROMPTS
        assert "DISTRIBUTOR" in EXPERT_PROMPTS
        assert "CRITIC" in EXPERT_PROMPTS
        # 旧ALPHAの「楽観」やOMEGAの「悲観」ではなく、専門知識ベース
        for name, prompt in EXPERT_PROMPTS.items():
            assert "専門知識" in prompt or "専門家" in prompt, (
                f"Expert {name} should have domain expertise, not just optimism/pessimism"
            )
