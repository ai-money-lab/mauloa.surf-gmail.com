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
