"""Tests for core/notifier.py."""

from unittest.mock import patch, MagicMock


from core.notifier import Notifier


class TestNotifier:
    """Test notification module."""

    def test_send_line_without_token_returns_false(self):
        with patch.dict("os.environ", {"LINE_NOTIFY_TOKEN": ""}):
            notifier = Notifier()
            notifier.line_token = ""
            assert notifier.send_line("test") is False

    def test_send_slack_without_webhook_returns_false(self):
        with patch.dict("os.environ", {"SLACK_WEBHOOK_URL": ""}):
            notifier = Notifier()
            notifier.slack_webhook = ""
            assert notifier.send_slack("test") is False

    @patch("core.notifier.requests.post")
    def test_send_line_with_token(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        notifier = Notifier()
        notifier.line_token = "test-token"
        result = notifier.send_line("テスト通知")

        assert result is True
        mock_post.assert_called_once()

    @patch("core.notifier.requests.post")
    def test_send_slack_with_webhook(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        notifier = Notifier()
        notifier.slack_webhook = "https://hooks.slack.com/test"
        result = notifier.send_slack("テスト通知")

        assert result is True
        mock_post.assert_called_once()

    @patch("core.notifier.requests.post")
    def test_send_line_handles_error(self, mock_post):
        mock_post.side_effect = Exception("Network error")

        notifier = Notifier()
        notifier.line_token = "test-token"
        result = notifier.send_line("テスト")

        assert result is False

    def test_notify_calls_both_channels(self):
        notifier = Notifier()
        notifier.line_token = ""
        notifier.slack_webhook = ""
        # Should not raise
        notifier.notify("test message")
