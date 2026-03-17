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
    """ImagePipeline reports disabled when FAL_API_KEY is not set."""
    with patch.dict("os.environ", {"FAL_API_KEY": ""}, clear=False):
        from system_e.image_pipeline import ImagePipeline
        pipeline = ImagePipeline()
        pipeline.fal_api_key = ""
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
