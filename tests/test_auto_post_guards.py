"""Tests for AutoPoster safety guards — duplicate and daily limit protection."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from system_a.auto_post import AutoPoster, MAX_POSTS_PER_DAY

JST = timezone(timedelta(hours=9))


@pytest.fixture
def poster(tmp_path, monkeypatch):
    """Create AutoPoster with temp log path."""
    log_path = tmp_path / "posted_tweets.json"
    monkeypatch.setattr("system_a.auto_post.POSTED_LOG_PATH", log_path)
    p = AutoPoster()
    p._log_path = log_path
    return p


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    path = tmp_path / "posted_tweets.json"
    monkeypatch.setattr("system_a.auto_post.POSTED_LOG_PATH", path)
    return path


class TestDailyLimit:
    """Guard 1: MAX_POSTS_PER_DAY enforcement."""

    def test_max_posts_per_day_is_one(self):
        assert MAX_POSTS_PER_DAY == 1

    def test_blocks_when_already_posted_today(self, poster, log_path):
        today = datetime.now(JST).isoformat()
        log_path.write_text(json.dumps([
            {"datetime": today, "tweet_id": "123", "text": "既投稿", "status": "posted"},
        ]))

        with pytest.raises(RuntimeError, match="投稿上限"):
            poster.post_and_record({"text": "新しい投稿", "pillar": 1})

    def test_allows_first_post_of_day(self, poster, log_path):
        # Yesterday's post only
        yesterday = (datetime.now(JST) - timedelta(days=1)).isoformat()
        log_path.write_text(json.dumps([
            {"datetime": yesterday, "tweet_id": "100", "text": "昨日の投稿", "status": "posted"},
        ]))

        today_posts = poster._get_today_posts()
        assert len(today_posts) == 0

    def test_allows_when_no_log_exists(self, poster):
        today_posts = poster._get_today_posts()
        assert len(today_posts) == 0


class TestDuplicateDetection:
    """Guard 2: Duplicate text prevention."""

    def test_detects_exact_duplicate(self, poster, log_path):
        log_path.write_text(json.dumps([
            {"datetime": "2026-03-01T10:00:00", "text": "これはテスト投稿です" * 5, "status": "posted"},
        ]))

        assert poster._is_duplicate_text("これはテスト投稿です" * 5) is True

    def test_allows_different_text(self, poster, log_path):
        log_path.write_text(json.dumps([
            {"datetime": "2026-03-01T10:00:00", "text": "過去の投稿内容", "status": "posted"},
        ]))

        assert poster._is_duplicate_text("全く異なる新しい投稿") is False

    def test_allows_when_no_log(self, poster):
        assert poster._is_duplicate_text("何でもOK") is False

    def test_blocks_duplicate_post(self, poster, log_path):
        today_str = (datetime.now(JST) - timedelta(days=1)).isoformat()
        log_path.write_text(json.dumps([
            {"datetime": today_str, "tweet_id": "999", "text": "重複テスト投稿", "status": "posted"},
        ]))

        # No today posts, but text is duplicate
        with pytest.raises(RuntimeError, match="同一テキスト"):
            poster.post_and_record({"text": "重複テスト投稿", "pillar": 1})
