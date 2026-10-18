"""Tests for the X API rate-limit handling in system_a/auto_post.py.

Only HTTP 429 may be retried: X refuses the request before creating the
tweet, so a retry cannot double-post. Any other failure must surface on the
first attempt, because the tweet may already exist.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from system_a.auto_post import (
    RATE_LIMIT_MAX_RETRIES,
    RATE_LIMIT_MAX_WAIT_SECONDS,
    _rate_limit_wait_seconds,
)


def _response(status_code, headers=None, body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.json.return_value = body or {"data": {"id": "999"}}
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(str(status_code))
    else:
        resp.raise_for_status.return_value = None
    return resp


@pytest.fixture
def poster():
    """AutoPoster with external collaborators stubbed out."""
    with patch("system_a.auto_post.SheetsClient"), \
         patch("system_a.auto_post.Notifier"), \
         patch("system_a.auto_post.ImageGenerator"):
        from system_a.auto_post import AutoPoster
        yield AutoPoster()


class TestRateLimitWaitSeconds:
    """Test the wait-time calculation."""

    def test_uses_retry_after_header(self):
        assert _rate_limit_wait_seconds(_response(429, {"retry-after": "30"})) == 30

    def test_falls_back_to_rate_limit_reset(self):
        import time as _time
        reset = int(_time.time()) + 20
        wait = _rate_limit_wait_seconds(
            _response(429, {"x-rate-limit-reset": str(reset)})
        )
        assert 15 <= wait <= 21

    def test_default_when_no_headers(self):
        assert _rate_limit_wait_seconds(_response(429)) == 15

    def test_garbage_header_falls_back_to_default(self):
        assert _rate_limit_wait_seconds(_response(429, {"retry-after": "soon"})) == 15

    def test_wait_is_clamped_to_maximum(self):
        wait = _rate_limit_wait_seconds(_response(429, {"retry-after": "99999"}))
        assert wait == RATE_LIMIT_MAX_WAIT_SECONDS

    def test_wait_is_at_least_one_second(self):
        assert _rate_limit_wait_seconds(_response(429, {"retry-after": "-5"})) == 1


class TestPostTweetRateLimit:
    """Test retry behaviour of post_tweet()."""

    @patch("system_a.auto_post.time.sleep")
    @patch("system_a.auto_post.requests.post")
    def test_retries_once_then_succeeds(self, mock_post, mock_sleep, poster):
        mock_post.side_effect = [
            _response(429, {"retry-after": "5"}),
            _response(200, body={"data": {"id": "123"}}),
        ]

        result = poster.post_tweet("テスト")

        assert result["data"]["id"] == "123"
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(5)

    @patch("system_a.auto_post.time.sleep")
    @patch("system_a.auto_post.requests.post")
    def test_raises_after_retries_exhausted(self, mock_post, mock_sleep, poster):
        mock_post.return_value = _response(429, {"retry-after": "1"})

        with pytest.raises(requests.HTTPError):
            poster.post_tweet("テスト")

        assert mock_post.call_count == RATE_LIMIT_MAX_RETRIES + 1
        assert mock_sleep.call_count == RATE_LIMIT_MAX_RETRIES

    @patch("system_a.auto_post.time.sleep")
    @patch("system_a.auto_post.requests.post")
    def test_other_errors_are_not_retried(self, mock_post, mock_sleep, poster):
        """A 403 may mean the tweet was created — never resend it."""
        mock_post.return_value = _response(403)

        with pytest.raises(requests.HTTPError):
            poster.post_tweet("テスト")

        assert mock_post.call_count == 1
        mock_sleep.assert_not_called()

    @patch("system_a.auto_post.time.sleep")
    @patch("system_a.auto_post.requests.post")
    def test_success_does_not_sleep(self, mock_post, mock_sleep, poster):
        mock_post.return_value = _response(200)

        poster.post_tweet("テスト")

        assert mock_post.call_count == 1
        mock_sleep.assert_not_called()


class TestPostThreadRateLimit:
    """post_thread() shares the same retry path."""

    @patch("system_a.auto_post.time.sleep")
    @patch("system_a.auto_post.requests.post")
    def test_thread_retries_rate_limited_tweet(self, mock_post, mock_sleep, poster):
        mock_post.side_effect = [
            _response(200, body={"data": {"id": "1"}}),
            _response(429, {"retry-after": "3"}),
            _response(200, body={"data": {"id": "2"}}),
        ]

        results = poster.post_thread(["一本目", "二本目"])

        assert [r["data"]["id"] for r in results] == ["1", "2"]
        mock_sleep.assert_any_call(3)
