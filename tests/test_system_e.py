"""Tests for System E — AI Character Content Monetization Pipeline."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml


# ─── Character Config Tests ───

def test_character_config_loads():
    """Character config YAML loads without errors."""
    config_path = Path(__file__).parent.parent / "system_e" / "character_config.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    assert "character" in config
    assert "monetization" in config
    assert "image_generation" in config
    assert "disclosure" in config


def test_character_config_has_required_fields():
    """Character config contains all required fields."""
    config_path = Path(__file__).parent.parent / "system_e" / "character_config.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    char = config["character"]
    assert char["name"]
    assert char["age"] > 0
    assert char["personality"]["traits"]
    assert char["personality"]["values"]
    assert char["backstory"]["origin"]
    assert char["visual_identity"]["style"]
    assert char["content_voice"]["tone"]
    assert char["content_voice"]["topics"]
    assert char["content_voice"]["banned_topics"]


def test_character_config_disclosure_present():
    """FTC disclosure configuration is present."""
    config_path = Path(__file__).parent.parent / "system_e" / "character_config.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    assert "disclosure" in config
    assert config["disclosure"]["bio_text"]
    assert "AI" in config["disclosure"]["bio_text"]


def test_fanvue_tiers_configured():
    """Fanvue monetization tiers are properly configured."""
    config_path = Path(__file__).parent.parent / "system_e" / "character_config.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    tiers = config["monetization"]["fanvue_tiers"]
    assert "free" in tiers
    assert "basic" in tiers
    assert "premium" in tiers
    assert "vip" in tiers
    assert tiers["free"]["price"] == 0
    assert tiers["basic"]["price"] > 0
    assert tiers["premium"]["price"] > tiers["basic"]["price"]
    assert tiers["vip"]["price"] > tiers["premium"]["price"]


# ─── Image Pipeline Tests ───

def test_image_pipeline_init():
    """ImagePipeline initializes without errors."""
    from system_e.image_pipeline import ImagePipeline
    pipeline = ImagePipeline()
    assert pipeline.config is not None
    assert pipeline.character is not None


def test_image_pipeline_disabled_without_key():
    """ImagePipeline reports disabled when no API keys are set."""
    env_overrides = {
        "FAL_API_KEY": "",
        "RUNPOD_API_KEY": "",
        "RUNPOD_ENDPOINT_ID": "",
        "RUNPOD_POD_ID": "",
    }
    with patch.dict("os.environ", env_overrides, clear=False):
        from system_e.image_pipeline import ImagePipeline
        pipeline = ImagePipeline()
        assert not pipeline.enabled


def test_build_character_prompt():
    """Character prompt builder includes key identity elements."""
    from system_e.image_pipeline import ImagePipeline
    pipeline = ImagePipeline()
    prompt = pipeline._build_character_prompt("morning_routine")
    assert "woman" in prompt.lower()
    assert "professional photography" in prompt.lower()


# ─── Content Generator Tests ───

def test_content_generator_init():
    """ContentGenerator initializes without errors."""
    from system_e.content_generator import ContentGenerator
    gen = ContentGenerator()
    assert gen.config is not None
    assert gen.character is not None


def test_content_generator_system_prompt():
    """System prompt includes character personality."""
    from system_e.content_generator import ContentGenerator
    gen = ContentGenerator()
    prompt = gen._build_system_prompt()
    assert gen.character["name"] in prompt
    assert "first person" in prompt.lower()


def test_content_generator_pick_scene():
    """Scene picker returns valid scene names."""
    from system_e.content_generator import ContentGenerator
    gen = ContentGenerator()
    scenes = gen.config["image_generation"]["scene_categories"]
    for _ in range(20):
        scene = gen._pick_scene()
        assert scene in scenes


# ─── Posting Scheduler Tests ───

def test_posting_scheduler_init():
    """PostingScheduler initializes without errors."""
    from system_e.posting_scheduler import PostingScheduler
    scheduler = PostingScheduler()
    assert scheduler.MAX_POSTS_PER_DAY == 5


def test_posting_scheduler_get_pending_no_plan(tmp_path):
    """Returns empty list when no content plan exists."""
    from system_e.posting_scheduler import PostingScheduler
    scheduler = PostingScheduler()
    pending = scheduler.get_pending_posts("2099-01-01")
    assert pending == []


# ─── Fanvue Manager Tests ───

def test_fanvue_manager_init():
    """FanvueManager initializes without errors."""
    from system_e.fanvue_manager import FanvueManager
    manager = FanvueManager()
    assert manager.tiers is not None


def test_fanvue_categorize_content():
    """Content tier categorization works correctly."""
    from system_e.fanvue_manager import FanvueManager
    manager = FanvueManager()

    assert manager.categorize_content("/fake/path.jpg", "workout") == "premium"
    assert manager.categorize_content("/fake/path.jpg", "studio") == "premium"
    assert manager.categorize_content("/fake/path.jpg", "morning_routine") == "basic"
    assert manager.categorize_content("/fake/path.jpg", "lifestyle") == "basic"
    assert manager.categorize_content("/fake/path.jpg", "unknown_scene") == "free"


# ─── Analytics Tests ───

def test_analytics_init():
    """Analytics initializes without errors."""
    from system_e.analytics import Analytics
    analytics = Analytics()
    assert analytics is not None


def test_analytics_daily_summary_no_data():
    """Daily summary returns gracefully when no data exists."""
    from system_e.analytics import Analytics
    analytics = Analytics()
    summary = analytics.get_daily_summary("2099-01-01")
    assert summary["posts"] == 0


def test_analytics_revenue_summary_no_data():
    """Revenue summary returns gracefully when no data exists."""
    from system_e.analytics import Analytics
    analytics = Analytics()
    summary = analytics.get_revenue_summary("2099-01")
    assert summary["total_revenue"] == 0
    assert summary["transaction_count"] == 0


# ─── Daily Pipeline Tests ───

def test_daily_pipeline_init():
    """SystemEPipeline initializes without errors."""
    from system_e.daily_pipeline import SystemEPipeline
    pipeline = SystemEPipeline()
    assert pipeline.content_gen is not None
    assert pipeline.image_pipeline is not None
    assert pipeline.scheduler is not None
    assert pipeline.fanvue is not None
    assert pipeline.analytics is not None


def test_daily_pipeline_budget_check():
    """Budget check passes when no cost data exists."""
    from system_e.daily_pipeline import SystemEPipeline
    pipeline = SystemEPipeline()
    assert pipeline._check_budget() is True


def test_daily_pipeline_monthly_spend_empty():
    """Monthly spend returns 0 when no cost log exists."""
    from system_e.daily_pipeline import SystemEPipeline
    pipeline = SystemEPipeline()
    assert pipeline._get_monthly_spend("2099-01") == 0.0


def test_daily_pipeline_record_cost(tmp_path):
    """Cost recording creates and appends to cost log."""
    from system_e.daily_pipeline import SystemEPipeline, COST_LOG
    pipeline = SystemEPipeline()

    # Use a temp cost log
    original_log = COST_LOG
    import system_e.daily_pipeline as dp
    dp.COST_LOG = tmp_path / "cost_log.json"
    try:
        pipeline._record_cost("test_image", 0.10)
        assert dp.COST_LOG.exists()
        entries = json.loads(dp.COST_LOG.read_text(encoding="utf-8"))
        assert len(entries) == 1
        assert entries[0]["item"] == "test_image"
        assert entries[0]["cost_usd"] == 0.10

        # Append another
        pipeline._record_cost("test_image_2", 0.20)
        entries = json.loads(dp.COST_LOG.read_text(encoding="utf-8"))
        assert len(entries) == 2
    finally:
        dp.COST_LOG = original_log


def test_daily_pipeline_budget_exceeded(tmp_path):
    """Budget check fails when monthly spend exceeds limit."""
    from system_e.daily_pipeline import SystemEPipeline
    import system_e.daily_pipeline as dp

    pipeline = SystemEPipeline()
    original_log = dp.COST_LOG
    dp.COST_LOG = tmp_path / "cost_log.json"
    try:
        from datetime import datetime, timezone, timedelta
        JST = timezone(timedelta(hours=9))
        month_key = datetime.now(JST).strftime("%Y-%m")
        # Write costs that exceed the $50 budget
        entries = [
            {"date": f"{month_key}-01T10:00:00+09:00", "item": "big_batch", "cost_usd": 55.0}
        ]
        dp.COST_LOG.write_text(json.dumps(entries), encoding="utf-8")
        assert pipeline._check_budget() is False
    finally:
        dp.COST_LOG = original_log


# ─── Posting Scheduler Account Separation Tests ───

def test_posting_scheduler_uses_default_credentials():
    """PostingScheduler falls back to default X credentials when SYSTEM_E_X_* not set."""
    env_overrides = {
        "SYSTEM_E_X_API_KEY": "",
        "SYSTEM_E_X_ACCESS_TOKEN": "",
    }
    with patch.dict("os.environ", env_overrides, clear=False):
        from system_e.posting_scheduler import PostingScheduler
        scheduler = PostingScheduler()
        # Should still be using default creds (from X_API_KEY env)
        assert scheduler.poster is not None


def test_posting_scheduler_uses_dedicated_credentials():
    """PostingScheduler uses SYSTEM_E_X_* credentials when available."""
    env_overrides = {
        "SYSTEM_E_X_API_KEY": "test_se_key",
        "SYSTEM_E_X_API_SECRET_KEY": "test_se_secret",
        "SYSTEM_E_X_ACCESS_TOKEN": "test_se_token",
        "SYSTEM_E_X_ACCESS_TOKEN_SECRET": "test_se_token_secret",
        "SYSTEM_E_X_BEARER_TOKEN": "test_se_bearer",
    }
    with patch.dict("os.environ", env_overrides, clear=False):
        from system_e.posting_scheduler import PostingScheduler
        scheduler = PostingScheduler()
        assert scheduler.poster.api_key == "test_se_key"
        assert scheduler.poster.access_token == "test_se_token"


# ─── FTC Compliance Tests ───

def test_disclosure_tags_always_added():
    """Every post must include AI disclosure hashtags."""
    from system_e.posting_scheduler import PostingScheduler
    scheduler = PostingScheduler()
    result = scheduler._append_hashtags("Hello world", ["fitness", "wellness"])
    assert "#AICreator" in result
    assert "#AIGenerated" in result


def test_disclosure_tags_prioritized_over_content_tags():
    """Disclosure tags are included even if content tags get dropped for space."""
    from system_e.posting_scheduler import PostingScheduler
    scheduler = PostingScheduler()
    # Long text near 280 char limit
    long_text = "A" * 240
    result = scheduler._append_hashtags(long_text, ["fitness", "wellness", "health"])
    assert "#AICreator" in result
    assert "#AIGenerated" in result
    assert len(result) <= 280


def test_disclosure_tags_with_truncation():
    """Text is truncated to fit disclosure tags if necessary."""
    from system_e.posting_scheduler import PostingScheduler
    scheduler = PostingScheduler()
    # Text that's already near 280 chars
    very_long_text = "B" * 275
    result = scheduler._append_hashtags(very_long_text, [])
    assert "#AICreator" in result
    assert "#AIGenerated" in result
    assert len(result) <= 280
    assert "…" in result  # text was truncated


def test_disclosure_tags_no_duplicates():
    """If content already has AICreator tag, don't duplicate it."""
    from system_e.posting_scheduler import PostingScheduler
    scheduler = PostingScheduler()
    result = scheduler._append_hashtags("Hello", ["AICreator", "fitness"])
    # Should only appear once in the tag section
    assert result.count("#AICreator") == 1


def test_fanvue_post_includes_ai_disclosure():
    """Every Fanvue post must include AI-generated disclosure."""
    from system_e.fanvue_manager import FanvueManager
    manager = FanvueManager()
    post = manager.prepare_fanvue_post("/fake/image.jpg", "workout", "Great workout today!")
    assert "ai-generated" in post["caption"].lower()


def test_fanvue_fallback_caption_includes_disclosure():
    """Fanvue fallback caption includes AI disclosure."""
    from system_e.fanvue_manager import FanvueManager
    manager = FanvueManager()
    # Call the fallback caption directly
    post = manager.prepare_fanvue_post("/fake/image.jpg", "lifestyle", "Check this out")
    assert "ai-generated" in post["caption"].lower()


# ─── Engagement Collector Tests ───

def test_engagement_collector_init():
    """EngagementCollector initializes without errors."""
    from system_e.engagement_collector import EngagementCollector
    collector = EngagementCollector()
    assert collector.analytics is not None


def test_engagement_collector_no_bearer_token():
    """Metrics collection gracefully handles missing bearer token."""
    with patch.dict("os.environ", {"SYSTEM_E_X_BEARER_TOKEN": "", "X_BEARER_TOKEN": ""}, clear=False):
        from system_e.engagement_collector import EngagementCollector
        collector = EngagementCollector()
        collector.bearer_token = ""
        assert collector.collect_tweet_metrics() == 0
        assert collector.collect_mentions() == []


def test_engagement_collector_get_unreplied_empty():
    """get_unreplied_mentions returns empty when no file."""
    from system_e.engagement_collector import EngagementCollector
    collector = EngagementCollector()
    assert collector.get_unreplied_mentions() == []


# ─── Mention Responder Tests ───

def test_mention_responder_init():
    """MentionResponder initializes without errors."""
    from system_e.mention_responder import MentionResponder
    responder = MentionResponder()
    assert responder.character["name"] == "Maia"


def test_mention_responder_should_skip_spam():
    """Spam mentions are filtered out."""
    from system_e.mention_responder import MentionResponder
    responder = MentionResponder()
    spam_mention = {
        "text": "Buy followers cheap! Check my bio for details",
        "author_id": "12345",
        "tweet_id": "99999",
    }
    assert responder._should_skip(spam_mention) is True


def test_mention_responder_should_not_skip_genuine():
    """Genuine mentions pass the filter."""
    from system_e.mention_responder import MentionResponder
    responder = MentionResponder()
    genuine_mention = {
        "text": "Love your morning routine! What matcha brand do you use?",
        "author_id": "12345",
        "tweet_id": "99999",
    }
    assert responder._should_skip(genuine_mention) is False


def test_mention_responder_hourly_limit():
    """Hourly limit returns 0 when no log exists."""
    from system_e.mention_responder import MentionResponder
    responder = MentionResponder()
    count = responder._hourly_reply_count()
    assert count == 0


def test_mention_responder_run_no_mentions():
    """run() returns empty when no unreplied mentions."""
    from system_e.mention_responder import MentionResponder
    responder = MentionResponder()
    # Mock the collector to return empty
    responder.collector.get_unreplied_mentions = lambda: []
    results = responder.run()
    assert results == []


# ─── Algorithm Guard Tests (引き算ルール) ───

def test_algorithm_guard_init():
    """AlgorithmGuard initializes."""
    from system_e.algorithm_guard import AlgorithmGuard
    guard = AlgorithmGuard()
    assert guard is not None


def test_guard_blocks_external_links():
    """External links are detected and blocked (リーチ激減)."""
    from system_e.algorithm_guard import AlgorithmGuard
    guard = AlgorithmGuard()
    result = guard.check_post("Check out my blog https://example.com/post\n\n#AICreator #AIGenerated")
    assert not result["approved"]
    assert any(v["rule"] == "external_link" for v in result["violations"])
    # Auto-fix should remove the link
    assert result["fixed_text"] is not None
    assert "https://" not in result["fixed_text"]


def test_guard_blocks_engagement_bait():
    """Engagement bait patterns are blocked."""
    from system_e.algorithm_guard import AlgorithmGuard
    guard = AlgorithmGuard()
    bait_posts = [
        "Like if you agree! Health is wealth\n\n#AICreator #AIGenerated",
        "Retweet if you love mornings\n\n#AICreator #AIGenerated",
        "Follow me for more tips\n\n#AICreator #AIGenerated",
        "Smash that like button\n\n#AICreator #AIGenerated",
    ]
    for post in bait_posts:
        result = guard.check_post(post)
        assert not result["approved"], f"Should block: {post[:50]}"
        assert any(v["rule"] == "engagement_bait" for v in result["violations"])


def test_guard_approves_genuine_engagement():
    """Genuine engagement questions are NOT blocked."""
    from system_e.algorithm_guard import AlgorithmGuard
    guard = AlgorithmGuard()
    genuine = [
        "What's your go-to morning routine? I'm curious!\n\n#AICreator #AIGenerated",
        "Started tracking my sleep last week. Anyone else obsess over their data?\n\n#AICreator #AIGenerated",
        "Hot take: cold showers are overhyped. Change my mind.\n\n#AICreator #AIGenerated",
    ]
    for post in genuine:
        result = guard.check_post(post)
        assert result["approved"], f"Should approve: {post[:50]}"


def test_guard_blocks_too_short():
    """Extremely short posts are blocked."""
    from system_e.algorithm_guard import AlgorithmGuard
    guard = AlgorithmGuard()
    result = guard.check_post("Hi\n\n#AICreator #AIGenerated")
    assert not result["approved"]
    assert any(v["rule"] == "empty_or_too_short" for v in result["violations"])


def test_guard_warns_ai_self_reference():
    """AI self-reference in text triggers warning (not block)."""
    from system_e.algorithm_guard import AlgorithmGuard
    guard = AlgorithmGuard()
    result = guard.check_post("As an AI, I recommend drinking more water.\n\n#AICreator #AIGenerated")
    assert result["approved"]  # warning, not block
    assert any(w["rule"] == "ai_self_disclosure_in_text" for w in result["warnings"])


def test_guard_posting_jitter():
    """Posting jitter adds randomness to avoid bot detection."""
    from system_e.algorithm_guard import AlgorithmGuard
    guard = AlgorithmGuard()
    jitters = [guard.add_posting_jitter(5) for _ in range(20)]
    # Should have some variation
    assert len(set(jitters)) > 1, "Jitter should produce varied results"
    # All should be non-negative
    assert all(j >= 0 for j in jitters)


def test_guard_account_health_normal():
    """Normal metrics = healthy account."""
    from system_e.algorithm_guard import AlgorithmGuard
    guard = AlgorithmGuard()
    metrics = [
        {"impressions": 1000, "likes": 50, "retweets": 10, "replies": 5, "date": "2026-03-15"},
        {"impressions": 1200, "likes": 60, "retweets": 12, "replies": 6, "date": "2026-03-16"},
        {"impressions": 1100, "likes": 55, "retweets": 11, "replies": 5, "date": "2026-03-17"},
        {"impressions": 1300, "likes": 65, "retweets": 13, "replies": 7, "date": "2026-03-18"},
    ]
    result = guard.check_account_health(metrics)
    assert result["healthy"]


def test_guard_detects_shadow_ban():
    """Zero impressions on recent posts = shadow ban suspected."""
    from system_e.algorithm_guard import AlgorithmGuard
    guard = AlgorithmGuard()
    metrics = [
        {"impressions": 1000, "likes": 50, "retweets": 10, "replies": 5, "date": "2026-03-13"},
        {"impressions": 1200, "likes": 60, "retweets": 12, "replies": 6, "date": "2026-03-14"},
        {"impressions": 0, "likes": 0, "retweets": 0, "replies": 0, "date": "2026-03-15"},
        {"impressions": 0, "likes": 0, "retweets": 0, "replies": 0, "date": "2026-03-16"},
        {"impressions": 0, "likes": 0, "retweets": 0, "replies": 0, "date": "2026-03-17"},
    ]
    result = guard.check_account_health(metrics)
    assert not result["healthy"]
    assert any(a["type"] == "shadow_ban_suspected" for a in result["alerts"])


def test_guard_detects_impression_drop():
    """Sudden impression drop = potential restriction."""
    from system_e.algorithm_guard import AlgorithmGuard
    guard = AlgorithmGuard()
    metrics = [
        {"impressions": 5000, "likes": 200, "retweets": 50, "replies": 30, "date": "2026-03-13"},
        {"impressions": 4800, "likes": 190, "retweets": 45, "replies": 25, "date": "2026-03-14"},
        {"impressions": 5200, "likes": 210, "retweets": 55, "replies": 35, "date": "2026-03-15"},
        {"impressions": 500, "likes": 10, "retweets": 2, "replies": 1, "date": "2026-03-16"},
        {"impressions": 300, "likes": 5, "retweets": 1, "replies": 0, "date": "2026-03-17"},
    ]
    result = guard.check_account_health(metrics)
    assert not result["healthy"]
    assert any(a["type"] == "impression_drop" for a in result["alerts"])


def test_guard_integrated_in_scheduler():
    """PostingScheduler has AlgorithmGuard integrated."""
    from system_e.posting_scheduler import PostingScheduler
    scheduler = PostingScheduler()
    assert hasattr(scheduler, 'guard')
    assert scheduler.guard is not None
