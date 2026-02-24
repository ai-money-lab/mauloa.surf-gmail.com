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

    @patch("core.notifier.requests.post")
    def test_send_slack_handles_error(self, mock_post):
        """Slack送信エラーはFalseを返す（例外は伝播しない）."""
        mock_post.side_effect = Exception("Slack down")

        notifier = Notifier()
        notifier.slack_webhook = "https://hooks.slack.com/test"
        result = notifier.send_slack("テスト")

        assert result is False

    @patch("core.notifier.requests.post")
    def test_send_line_sends_correct_headers(self, mock_post):
        """LINEのAuthorizationヘッダーが正しい."""
        mock_post.return_value = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()

        notifier = Notifier()
        notifier.line_token = "my-secret-token"
        notifier.send_line("test")

        call_kwargs = mock_post.call_args
        assert "Bearer my-secret-token" in str(call_kwargs)

    @patch("core.notifier.requests.post")
    def test_send_slack_sends_json_payload(self, mock_post):
        """SlackにJSON形式でtext送信."""
        mock_post.return_value = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()

        notifier = Notifier()
        notifier.slack_webhook = "https://hooks.slack.com/test"
        notifier.send_slack("メッセージ")

        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"] == {"text": "メッセージ"}

    @patch("core.notifier.requests.post")
    def test_notify_calls_both_channels(self, mock_post):
        """notify()はLINEとSlack両方を呼ぶ."""
        mock_post.return_value = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()

        notifier = Notifier()
        notifier.line_token = "token"
        notifier.slack_webhook = "https://hooks.slack.com/test"
        results = notifier.notify("test message")

        assert mock_post.call_count == 2
        assert results["line"] is True
        assert results["slack"] is True

    def test_notify_no_channels_configured(self):
        notifier = Notifier()
        notifier.line_token = ""
        notifier.slack_webhook = ""
        results = notifier.notify("test message")
        assert results["line"] is False
        assert results["slack"] is False

    @patch("core.notifier.requests.post")
    def test_notify_returns_partial_success(self, mock_post):
        """片方だけ成功した場合のステータス."""
        mock_post.return_value = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()

        notifier = Notifier()
        notifier.line_token = "token"
        notifier.slack_webhook = ""  # Slack未設定
        results = notifier.notify("test")
        assert results["line"] is True
        assert results["slack"] is False
