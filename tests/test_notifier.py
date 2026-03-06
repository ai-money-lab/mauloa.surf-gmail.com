"""Tests for core/notifier.py — Notifier class.

Covers:
- send_line(): with token, without token, error handling
- send_slack(): with webhook, without webhook, error handling
- notify(): calls both channels
- Correct API endpoints and payload formats
"""

from unittest.mock import patch, MagicMock


from core.notifier import Notifier


# ---------------------------------------------------------------------------
# send_line() tests
# ---------------------------------------------------------------------------

class TestSendLine:
    """Tests for Notifier.send_line()."""

    def test_returns_false_without_token(self):
        notifier = Notifier()
        notifier.line_token = ""
        assert notifier.send_line("test") is False

    @patch("core.notifier.requests.post")
    def test_returns_true_with_valid_token(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        notifier = Notifier()
        notifier.line_token = "test-token"
        result = notifier.send_line("テスト通知")

        assert result is True
        mock_post.assert_called_once()

    @patch("core.notifier.requests.post")
    def test_sends_to_correct_line_endpoint(self, mock_post):
        mock_post.return_value = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()

        notifier = Notifier()
        notifier.line_token = "test-token"
        notifier.send_line("msg")

        call_args = mock_post.call_args
        assert call_args[0][0] == "https://notify-api.line.me/api/notify"

    @patch("core.notifier.requests.post")
    def test_sends_bearer_authorization_header(self, mock_post):
        mock_post.return_value = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()

        notifier = Notifier()
        notifier.line_token = "my-token-123"
        notifier.send_line("msg")

        call_kwargs = mock_post.call_args
        headers = call_kwargs[1]["headers"]
        assert headers["Authorization"] == "Bearer my-token-123"

    @patch("core.notifier.requests.post")
    def test_message_prefixed_with_newline(self, mock_post):
        mock_post.return_value = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()

        notifier = Notifier()
        notifier.line_token = "test-token"
        notifier.send_line("hello")

        call_kwargs = mock_post.call_args
        data = call_kwargs[1]["data"]
        assert data["message"] == "\nhello"

    @patch("core.notifier.requests.post")
    def test_returns_false_on_network_error(self, mock_post):
        mock_post.side_effect = Exception("Network error")

        notifier = Notifier()
        notifier.line_token = "test-token"
        result = notifier.send_line("テスト")

        assert result is False


# ---------------------------------------------------------------------------
# send_slack() tests
# ---------------------------------------------------------------------------

class TestSendSlack:
    """Tests for Notifier.send_slack()."""

    def test_returns_false_without_webhook(self):
        notifier = Notifier()
        notifier.slack_webhook = ""
        assert notifier.send_slack("test") is False

    @patch("core.notifier.requests.post")
    def test_returns_true_with_valid_webhook(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        notifier = Notifier()
        notifier.slack_webhook = "https://hooks.slack.com/services/xxx"
        result = notifier.send_slack("テスト通知")

        assert result is True
        mock_post.assert_called_once()

    @patch("core.notifier.requests.post")
    def test_sends_to_configured_webhook_url(self, mock_post):
        mock_post.return_value = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()

        webhook_url = "https://hooks.slack.com/services/T00/B00/xxxx"
        notifier = Notifier()
        notifier.slack_webhook = webhook_url
        notifier.send_slack("msg")

        call_args = mock_post.call_args
        assert call_args[0][0] == webhook_url

    @patch("core.notifier.requests.post")
    def test_sends_json_payload_with_text(self, mock_post):
        mock_post.return_value = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()

        notifier = Notifier()
        notifier.slack_webhook = "https://hooks.slack.com/test"
        notifier.send_slack("hello slack")

        call_kwargs = mock_post.call_args
        json_payload = call_kwargs[1]["json"]
        assert json_payload == {"text": "hello slack"}

    @patch("core.notifier.requests.post")
    def test_returns_false_on_network_error(self, mock_post):
        mock_post.side_effect = Exception("Connection refused")

        notifier = Notifier()
        notifier.slack_webhook = "https://hooks.slack.com/test"
        result = notifier.send_slack("テスト")

        assert result is False


# ---------------------------------------------------------------------------
# notify() tests
# ---------------------------------------------------------------------------

class TestNotify:
    """Tests for Notifier.notify()."""

    def test_calls_both_channels_when_configured(self):
        notifier = Notifier()
        notifier.send_line = MagicMock(return_value=True)
        notifier.send_slack = MagicMock(return_value=True)

        notifier.notify("test message")

        notifier.send_line.assert_called_once_with("test message")
        notifier.send_slack.assert_called_once_with("test message")

    def test_does_not_raise_when_both_unconfigured(self):
        notifier = Notifier()
        notifier.line_token = ""
        notifier.slack_webhook = ""
        # Should not raise
        notifier.notify("test message")

    @patch("core.notifier.requests.post")
    def test_line_failure_does_not_prevent_slack(self, mock_post):
        """Even if LINE fails, Slack should still be attempted."""
        notifier = Notifier()
        notifier.line_token = "token"
        notifier.slack_webhook = "https://hooks.slack.com/test"

        # First call (LINE) raises, second call (Slack) succeeds
        mock_post.side_effect = [
            Exception("LINE down"),
            MagicMock(status_code=200, raise_for_status=MagicMock()),
        ]

        notifier.notify("msg")
        # Should have attempted 2 calls
        assert mock_post.call_count == 2
