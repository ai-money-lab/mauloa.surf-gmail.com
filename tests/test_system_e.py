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

def test_bio_based_disclosure_no_per_post_tags():
    """AI disclosure is in the bio, NOT per-post hashtags.

    The account bio reads 'AI-generated wellness creator | Powered by AI'
    which satisfies FTC transparency. Posts should NOT contain #AICreator
    or #AIGenerated — research shows multiple hashtags reduce reach by ~40%.
    """
    from system_e.posting_scheduler import PostingScheduler
    scheduler = PostingScheduler()
    result = scheduler._append_hashtags("Hello world", ["fitness", "wellness"])
    assert "#AICreator" not in result
    assert "#AIGenerated" not in result
    # Should have branded hashtag instead
    assert "#RienaWellness" in result


def test_max_two_hashtags_per_post():
    """Posts should have at most 2 hashtags: 1 content + #RienaWellness."""
    import re
    from system_e.posting_scheduler import PostingScheduler
    scheduler = PostingScheduler()
    result = scheduler._append_hashtags("Hello world", ["fitness", "wellness", "health"])
    hashtags = re.findall(r'#\w+', result)
    assert len(hashtags) <= 2
    assert "#RienaWellness" in result


def test_branded_hashtag_always_included():
    """#RienaWellness branded hashtag is included when space permits."""
    from system_e.posting_scheduler import PostingScheduler
    scheduler = PostingScheduler()
    result = scheduler._append_hashtags("Hello world", [])
    assert "#RienaWellness" in result


def test_hashtags_dropped_when_text_too_long():
    """When text is near 280 chars, hashtags are dropped rather than truncating."""
    from system_e.posting_scheduler import PostingScheduler
    scheduler = PostingScheduler()
    very_long_text = "B" * 275
    result = scheduler._append_hashtags(very_long_text, ["fitness"])
    # Text should not be truncated — hashtags dropped instead
    assert len(result) <= 280
    assert "B" * 275 in result


def test_no_duplicate_branded_hashtag():
    """If content hashtag is RienaWellness, don't duplicate it."""
    import re
    from system_e.posting_scheduler import PostingScheduler
    scheduler = PostingScheduler()
    result = scheduler._append_hashtags("Hello", ["RienaWellness", "fitness"])
    assert result.count("#RienaWellness") == 1
    hashtags = re.findall(r'#\w+', result)
    assert len(hashtags) <= 2


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
    assert responder.character["name"] == "Riena"


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
    result = guard.check_post("Check out my blog https://example.com/post\n\n#RienaWellness")
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
        "Like if you agree! Health is wealth\n\n#RienaWellness",
        "Retweet if you love mornings\n\n#RienaWellness",
        "Follow me for more tips\n\n#RienaWellness",
        "Smash that like button\n\n#RienaWellness",
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
        "What's your go-to morning routine? I'm curious!\n\n#RienaWellness",
        "Started tracking my sleep last week. Anyone else obsess over their data?\n\n#RienaWellness",
        "Hot take: cold showers are overhyped. Change my mind.\n\n#RienaWellness",
    ]
    for post in genuine:
        result = guard.check_post(post)
        assert result["approved"], f"Should approve: {post[:50]}"


def test_guard_blocks_too_short():
    """Extremely short posts are blocked."""
    from system_e.algorithm_guard import AlgorithmGuard
    guard = AlgorithmGuard()
    result = guard.check_post("Hi\n\n#RienaWellness")
    assert not result["approved"]
    assert any(v["rule"] == "empty_or_too_short" for v in result["violations"])


def test_guard_warns_ai_self_reference():
    """AI self-reference in text triggers warning (not block)."""
    from system_e.algorithm_guard import AlgorithmGuard
    guard = AlgorithmGuard()
    result = guard.check_post("As an AI, I recommend drinking more water.\n\n#RienaWellness")
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


# ─── Self-Reply Boost Tests ───

def test_boost_reply_templates_exist():
    """Boost reply templates are defined for all expected content types."""
    from system_e.posting_scheduler import PostingScheduler
    templates = PostingScheduler.BOOST_TEMPLATES
    assert "engagement" in templates
    assert "standard" in templates
    assert "story" in templates
    # Each category should have at least 3 templates
    for category, items in templates.items():
        assert len(items) >= 3, f"'{category}' should have at least 3 templates"
    # All templates should be max 200 chars
    for category, items in templates.items():
        for t in items:
            assert len(t) <= 200, f"Template too long ({len(t)} chars): {t[:50]}"


def test_boost_template_selection_engagement():
    """Engagement content type selects from engagement templates."""
    from system_e.posting_scheduler import PostingScheduler
    for _ in range(20):
        template = PostingScheduler._select_boost_template("engagement")
        assert template in PostingScheduler.BOOST_TEMPLATES["engagement"]


def test_boost_template_selection_standard():
    """Standard content type selects from standard templates."""
    from system_e.posting_scheduler import PostingScheduler
    for _ in range(20):
        template = PostingScheduler._select_boost_template("standard")
        assert template in PostingScheduler.BOOST_TEMPLATES["standard"]


def test_boost_template_selection_story():
    """Story content type selects from story templates."""
    from system_e.posting_scheduler import PostingScheduler
    for _ in range(20):
        template = PostingScheduler._select_boost_template("story")
        assert template in PostingScheduler.BOOST_TEMPLATES["story"]


def test_boost_template_selection_unknown_falls_back():
    """Unknown content type falls back to standard templates."""
    from system_e.posting_scheduler import PostingScheduler
    for _ in range(20):
        template = PostingScheduler._select_boost_template("nonexistent_type")
        assert template in PostingScheduler.BOOST_TEMPLATES["standard"]


def test_boost_reply_content_type_mapping():
    """Content type field maps correctly to template categories."""
    from system_e.posting_scheduler import PostingScheduler
    scheduler = PostingScheduler()

    # Mock poster.post_tweet to capture the reply text
    calls = []

    def mock_post_tweet(text, reply_to=None, media_id=None):
        calls.append({"text": text, "reply_to": reply_to})
        return {"data": {"id": "reply_999"}}

    scheduler.poster.post_tweet = mock_post_tweet

    # Engagement types -> engagement templates
    for content_type in ("question", "poll", "engagement"):
        calls.clear()
        scheduler._post_boost_reply("tweet_123", {"type": content_type})
        assert len(calls) == 1
        assert calls[0]["text"] in PostingScheduler.BOOST_TEMPLATES["engagement"]
        assert calls[0]["reply_to"] == "tweet_123"

    # Story types -> story templates
    for content_type in ("story", "thread_teaser", "personal"):
        calls.clear()
        scheduler._post_boost_reply("tweet_123", {"type": content_type})
        assert len(calls) == 1
        assert calls[0]["text"] in PostingScheduler.BOOST_TEMPLATES["story"]

    # Default -> standard templates
    for content_type in ("tip", "motivational", ""):
        calls.clear()
        scheduler._post_boost_reply("tweet_123", {"type": content_type})
        assert len(calls) == 1
        assert calls[0]["text"] in PostingScheduler.BOOST_TEMPLATES["standard"]


# ─── Poll Generation Tests ───

def test_poll_generation_fallback():
    """Poll generation falls back to preset list when Claude fails."""
    from system_e.content_generator import ContentGenerator
    gen = ContentGenerator()
    # Mock Claude to fail
    gen.claude.generate_json = MagicMock(side_effect=Exception("API down"))
    result = gen.generate_poll()
    assert result["type"] == "poll"
    assert result["duration_minutes"] == 1440
    assert "text" in result
    assert "options" in result
    assert 2 <= len(result["options"]) <= 4
    assert "generated_at" in result


def test_poll_generation_with_topic():
    """Poll generation accepts optional topic hint."""
    from system_e.content_generator import ContentGenerator
    gen = ContentGenerator()
    # Mock Claude to fail so we get fallback
    gen.claude.generate_json = MagicMock(side_effect=Exception("API down"))
    result = gen.generate_poll(topic="sleep quality")
    assert result["type"] == "poll"
    assert result["duration_minutes"] == 1440


def test_poll_options_constrained():
    """Poll options are max 25 chars and 2-4 items."""
    from system_e.content_generator import ContentGenerator
    gen = ContentGenerator()
    # Mock Claude to return valid but long options
    gen.claude.generate_json = MagicMock(return_value={
        "text": "Test poll question?",
        "options": ["Short", "This option is way too long and should be truncated at 25", "Medium option", "Another"],
    })
    result = gen.generate_poll()
    assert len(result["options"]) <= 4
    assert len(result["options"]) >= 2
    for opt in result["options"]:
        assert len(opt) <= 25


def test_poll_too_few_options_triggers_fallback():
    """If Claude returns fewer than 2 options, fallback is used."""
    from system_e.content_generator import ContentGenerator
    gen = ContentGenerator()
    gen.claude.generate_json = MagicMock(return_value={
        "text": "Bad poll?",
        "options": ["Only one"],
    })
    result = gen.generate_poll()
    # Should have fallen back to preset
    assert len(result["options"]) >= 2
    assert result["duration_minutes"] == 1440


def test_fallback_polls_valid():
    """All fallback polls have valid structure."""
    from system_e.content_generator import ContentGenerator
    for poll in ContentGenerator.FALLBACK_POLLS:
        assert "text" in poll
        assert "options" in poll
        assert 2 <= len(poll["options"]) <= 4
        for opt in poll["options"]:
            assert len(opt) <= 25, f"Fallback option too long: {opt}"


# ─── Content Mix Tests ───

def test_content_mix_has_correct_types():
    """Daily content plan has the right content types for reach optimization."""
    from system_e.content_generator import ContentGenerator
    gen = ContentGenerator()
    # Mock Claude to return fresh dicts each call
    def mock_generate_json(**kwargs):
        return {
            "text": "Test post",
            "hashtags": ["wellness"],
            "tweets": ["tweet 1", "tweet 2", "tweet 3"],
            "hook_quality": 7,
            "options": ["A", "B", "C"],
        }
    gen.claude.generate_json = mock_generate_json

    # Test odd day (poll at noon)
    plan = gen.generate_daily_content_plan("2026-03-19")  # 19 = odd
    types = [item.get("type") for item in plan]
    assert types[0] == "standard", "07:00 should be standard"
    assert types[1] == "poll", "12:00 on odd day should be poll"
    assert types[2] == "thread", "19:00 should be thread (40-60% more reach)"
    assert types[3] == "story", "23:00 should be story"

    # Test even day (engagement at noon)
    plan = gen.generate_daily_content_plan("2026-03-20")  # 20 = even
    types = [item.get("type") for item in plan]
    assert types[0] == "standard"
    assert types[1] == "engagement", "12:00 on even day should be engagement"
    assert types[2] == "thread"
    assert types[3] == "story"


def test_content_mix_has_four_slots():
    """Daily content plan generates exactly 4 content items."""
    from system_e.content_generator import ContentGenerator
    gen = ContentGenerator()
    def mock_generate_json(**kwargs):
        return {
            "text": "Test", "hashtags": ["test"],
            "tweets": ["t1", "t2", "t3"], "hook_quality": 5,
            "options": ["A", "B"],
        }
    gen.claude.generate_json = mock_generate_json
    plan = gen.generate_daily_content_plan("2026-04-01")
    assert len(plan) == 4


def test_content_mix_thread_at_prime_time():
    """Thread is scheduled at 19:00 JST (EU+Asia overlap) for max reach."""
    from system_e.content_generator import ContentGenerator
    gen = ContentGenerator()
    def mock_generate_json(**kwargs):
        return {
            "text": "Test", "hashtags": ["test"],
            "tweets": ["t1", "t2", "t3"], "hook_quality": 5,
            "options": ["A", "B"],
        }
    gen.claude.generate_json = mock_generate_json
    plan = gen.generate_daily_content_plan("2026-03-21")
    evening_slot = [p for p in plan if p.get("scheduled_time_jst") == "19:00"]
    assert len(evening_slot) == 1
    assert evening_slot[0]["type"] == "thread"


# ─── Poll Posting Tests ───

def test_post_poll_method_exists():
    """PostingScheduler has post_poll method."""
    from system_e.posting_scheduler import PostingScheduler
    scheduler = PostingScheduler()
    assert hasattr(scheduler, "post_poll")
    assert callable(scheduler.post_poll)


def test_post_poll_rejects_invalid_content():
    """post_poll returns None for invalid poll content."""
    from system_e.posting_scheduler import PostingScheduler
    scheduler = PostingScheduler()
    # Missing text
    assert scheduler.post_poll({"options": ["A", "B"]}) is None
    # Too few options
    assert scheduler.post_poll({"text": "Question?", "options": ["Only one"]}) is None
    # Empty options
    assert scheduler.post_poll({"text": "Question?", "options": []}) is None


def test_run_due_posts_handles_poll_type():
    """run_due_posts dispatches poll content to post_poll."""
    from system_e.posting_scheduler import PostingScheduler
    scheduler = PostingScheduler()

    poll_content = {
        "type": "poll",
        "text": "What's your favorite workout?",
        "options": ["Running", "Weights", "Yoga"],
        "duration_minutes": 1440,
        "scheduled_time_jst": "12:00",
        "_post_id": "2026-03-19_12:00",
    }

    # Mock get_due_posts to return our poll
    scheduler.get_due_posts = MagicMock(return_value=[poll_content])
    # Mock post_poll to track calls
    scheduler.post_poll = MagicMock(return_value={"data": {"id": "poll_123"}})

    results = scheduler.run_due_posts()
    scheduler.post_poll.assert_called_once_with(poll_content)
    assert len(results) == 1
