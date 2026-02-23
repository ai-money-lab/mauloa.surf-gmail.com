"""Shared test fixtures."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set dummy env vars for testing
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("X_API_KEY", "test-x-key")
os.environ.setdefault("X_API_SECRET_KEY", "test-x-secret")
os.environ.setdefault("X_ACCESS_TOKEN", "test-token")
os.environ.setdefault("X_ACCESS_TOKEN_SECRET", "test-token-secret")
os.environ.setdefault("X_BEARER_TOKEN", "test-bearer")
os.environ.setdefault("TWITTERAPI_IO_KEY", "test-twitter-io")
os.environ.setdefault("LINE_NOTIFY_TOKEN", "")
os.environ.setdefault("SLACK_WEBHOOK_URL", "")


@pytest.fixture
def mock_claude_client():
    """Mock ClaudeClient for tests."""
    with patch("core.claude_client.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"test": "response"}')]
        mock_client.messages.create.return_value = mock_response

        from core.claude_client import ClaudeClient
        client = ClaudeClient()
        yield client


@pytest.fixture
def sample_quality_result():
    """Sample quality check result."""
    return {
        "scores": {
            "hook_power": 8,
            "persona_match": 9,
            "pillar_alignment": 8,
            "algorithm_optimization": 7,
            "no_external_links": 10,
            "no_banned_content": 10,
            "character_limit": 10,
            "number_included": 7,
            "cta_ending": 8,
            "originality": 8,
            "tone_balance": 9,
            "algorithm_hooks": 7,
        },
        "total_score": 101,
        "threshold": 84,
        "result": "auto_approved",
        "rejection_reasons": [],
        "improvement_suggestions": [],
    }


@pytest.fixture
def sample_tweet():
    """Sample tweet data."""
    return {
        "id": "123456789",
        "text": "不動産業界24年のプロが教える内見の極意",
        "likeCount": 15000,
        "retweetCount": 3000,
        "replyCount": 500,
        "author": {
            "userName": "test_user",
            "followersCount": 50000,
        },
        "createdAt": "2026-02-17T10:00:00Z",
    }


@pytest.fixture
def sample_order():
    """Sample order data."""
    return {
        "order_id": "ORD-20260216-001",
        "product_id": "tier1_area_analysis",
        "client_name": "田中太郎",
        "parameters": {"area": "港区赤坂", "budget": "1億円"},
        "deadline": "2026-02-23",
        "platform": "lancers",
    }


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create temporary data directory structure."""
    dirs = [
        "data/system_a/pipeline1/collected",
        "data/system_a/pipeline1/generated",
        "data/system_a/pipeline2/sources",
        "data/system_a/pipeline2/generated",
        "data/system_a/pipeline3/generated",
        "data/system_a/stock_pool",
        "data/system_b/deliverables",
        "data/system_c/reports",
        "data/system_c/daily",
        "data/system_c/weekly",
        "data/quality_logs",
    ]
    for d in dirs:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    return tmp_path
