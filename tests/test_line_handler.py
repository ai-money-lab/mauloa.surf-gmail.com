"""LINE Handler — 全イベント処理 + API通信テスト.

カバレッジ目標: 39% → 80%+
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from inquiry_bot.line_handler import LineHandler


@pytest.fixture
def handler():
    """モック付きLineHandler."""
    bot = MagicMock()
    bot.config = {"web_chat": {"widget": {"welcome_message": "ようこそ！"}}}
    bot.handle_message.return_value = {
        "reply": "テスト回答",
        "category": "general",
        "escalated": False,
    }
    h = LineHandler(bot_engine=bot)
    h.channel_secret = ""
    h.channel_access_token = "test-token"
    return h


class TestLineHandlerInit:
    def test_init_with_bot(self):
        bot = MagicMock()
        h = LineHandler(bot_engine=bot)
        assert h.bot is bot

    def test_static_text_message(self):
        msg = LineHandler._text_message("hello")
        assert msg == {"type": "text", "text": "hello"}

    def test_static_quick_reply_action(self):
        action = LineHandler._quick_reply_action("ラベル", "data123")
        assert action["type"] == "action"
        assert action["action"]["label"] == "ラベル"
        assert action["action"]["data"] == "data123"
        assert action["action"]["displayText"] == "ラベル"


class TestHandleWebhook:
    def test_empty_events(self, handler):
        body = json.dumps({"events": []})
        result = handler.handle_webhook(body, "")
        assert result["status"] == 200
        assert result["results"] == []

    def test_invalid_json(self, handler):
        result = handler.handle_webhook("{bad json!!!", "")
        assert result["status"] == 400

    def test_invalid_signature_rejects(self, handler):
        handler.channel_secret = "secret"
        result = handler.handle_webhook('{"events":[]}', "wrong-sig")
        assert result["status"] == 403

    def test_no_signature_skips_verification(self, handler):
        handler.channel_secret = "secret"
        result = handler.handle_webhook('{"events":[]}', "")
        assert result["status"] == 200


class TestProcessEvent:
    def test_unhandled_event_type(self, handler):
        result = handler._process_event({"type": "beacon", "replyToken": "tok"})
        assert result["handled"] is False
        assert result["event_type"] == "beacon"


class TestHandleMessageEvent:
    @patch.object(LineHandler, "_reply", return_value=True)
    def test_text_message(self, mock_reply, handler):
        event = {
            "type": "message",
            "replyToken": "tok",
            "message": {"type": "text", "text": "質問です"},
            "source": {"userId": "U12345"},
        }
        result = handler._handle_message_event(event, "tok")
        assert result["event_type"] == "message"
        assert result["msg_type"] == "text"
        assert result["handled"] is True
        handler.bot.handle_message.assert_called_once()
        mock_reply.assert_called_once()

    @patch.object(LineHandler, "_reply", return_value=True)
    def test_non_text_message(self, mock_reply, handler):
        event = {
            "type": "message",
            "replyToken": "tok",
            "message": {"type": "image"},
            "source": {"userId": "U12345"},
        }
        result = handler._handle_message_event(event, "tok")
        assert result["msg_type"] == "image"
        assert result["handled"] is True
        # テキスト案内メッセージが送信される
        mock_reply.assert_called_once()
        sent_messages = mock_reply.call_args[0][1]
        assert "テキストメッセージ" in sent_messages[0]["text"]

    @patch.object(LineHandler, "_reply", return_value=True)
    def test_viewing_category_adds_quick_reply(self, mock_reply, handler):
        handler.bot.handle_message.return_value = {
            "reply": "内見について",
            "category": "viewing",
            "escalated": False,
        }
        event = {
            "type": "message",
            "replyToken": "tok",
            "message": {"type": "text", "text": "内見したい"},
            "source": {"userId": "U12345"},
        }
        handler._handle_message_event(event, "tok")
        sent_messages = mock_reply.call_args[0][1]
        assert "quickReply" in sent_messages[0]
        items = sent_messages[0]["quickReply"]["items"]
        assert len(items) == 3

    @patch.object(LineHandler, "_reply", return_value=True)
    def test_escalated_flag(self, mock_reply, handler):
        handler.bot.handle_message.return_value = {
            "reply": "担当者に...", "category": "general", "escalated": True,
        }
        event = {
            "type": "message",
            "replyToken": "tok",
            "message": {"type": "text", "text": "弁護士"},
            "source": {"userId": "U12345"},
        }
        result = handler._handle_message_event(event, "tok")
        assert result["escalated"] is True


class TestHandleFollowEvent:
    @patch.object(LineHandler, "_reply", return_value=True)
    def test_follow_event(self, mock_reply, handler):
        event = {"type": "follow", "replyToken": "tok", "source": {"userId": "U99"}}
        result = handler._handle_follow_event(event, "tok")
        assert result["event_type"] == "follow"
        assert result["handled"] is True
        mock_reply.assert_called_once()
        # ウェルカムメッセージが送信される
        msg = mock_reply.call_args[0][1][0]
        assert msg["type"] == "text"


class TestHandleUnfollowEvent:
    def test_unfollow_event(self, handler):
        event = {"type": "unfollow", "source": {"userId": "U99"}}
        result = handler._handle_unfollow_event(event)
        assert result["event_type"] == "unfollow"
        assert result["handled"] is True


class TestHandlePostbackEvent:
    @patch.object(LineHandler, "_reply", return_value=True)
    def test_postback_known_action(self, mock_reply, handler):
        event = {
            "type": "postback",
            "replyToken": "tok",
            "postback": {"data": "viewing_book"},
            "source": {"userId": "U12345"},
        }
        result = handler._handle_postback_event(event, "tok")
        assert result["event_type"] == "postback"
        assert result["data"] == "viewing_book"
        assert result["handled"] is True
        # BotEngineに変換されたメッセージが送信される
        call_args = handler.bot.handle_message.call_args
        assert "内見" in call_args.kwargs.get("user_message", call_args[1].get("user_message", ""))

    @patch.object(LineHandler, "_reply", return_value=True)
    def test_postback_unknown_action(self, mock_reply, handler):
        event = {
            "type": "postback",
            "replyToken": "tok",
            "postback": {"data": "custom_action"},
            "source": {"userId": "U12345"},
        }
        result = handler._handle_postback_event(event, "tok")
        assert result["data"] == "custom_action"
        # Unknown actionではpostback dataがそのままuser_messageになる
        handler.bot.handle_message.assert_called_once()


class TestReplyMethod:
    @patch("inquiry_bot.line_handler.requests.post")
    def test_reply_success(self, mock_post, handler):
        mock_post.return_value = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()
        result = handler._reply("tok", [{"type": "text", "text": "hello"}])
        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert "Bearer test-token" in str(call_kwargs)

    @patch("inquiry_bot.line_handler.requests.post")
    def test_reply_failure(self, mock_post, handler):
        mock_post.side_effect = ConnectionError("network error")
        result = handler._reply("tok", [{"type": "text", "text": "hello"}])
        assert result is False

    def test_reply_no_token(self, handler):
        handler.channel_access_token = ""
        result = handler._reply("tok", [{"type": "text", "text": "hello"}])
        assert result is False


class TestPushMessageMethod:
    @patch("inquiry_bot.line_handler.requests.post")
    def test_push_success(self, mock_post, handler):
        mock_post.return_value = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()
        result = handler._push_message("U12345", [{"type": "text", "text": "push"}])
        assert result is True

    @patch("inquiry_bot.line_handler.requests.post")
    def test_push_failure(self, mock_post, handler):
        mock_post.side_effect = ConnectionError("fail")
        result = handler._push_message("U12345", [{"type": "text", "text": "push"}])
        assert result is False

    def test_push_no_token(self, handler):
        handler.channel_access_token = ""
        result = handler._push_message("U12345", [{"type": "text", "text": "push"}])
        assert result is False


class TestFullWebhookFlow:
    """Webhook受信→イベント処理→Reply の統合テスト."""

    @patch.object(LineHandler, "_reply", return_value=True)
    def test_full_text_message_flow(self, mock_reply, handler):
        body = json.dumps({
            "events": [
                {
                    "type": "message",
                    "replyToken": "token123",
                    "message": {"type": "text", "text": "賃料はいくらですか"},
                    "source": {"userId": "U_test_user"},
                },
            ]
        })
        result = handler.handle_webhook(body, "")
        assert result["status"] == 200
        assert len(result["results"]) == 1
        assert result["results"][0]["handled"] is True

    @patch.object(LineHandler, "_reply", return_value=True)
    def test_multiple_events(self, mock_reply, handler):
        body = json.dumps({
            "events": [
                {"type": "follow", "replyToken": "tok1", "source": {"userId": "U1"}},
                {"type": "message", "replyToken": "tok2",
                 "message": {"type": "text", "text": "hi"},
                 "source": {"userId": "U1"}},
            ]
        })
        result = handler.handle_webhook(body, "")
        assert len(result["results"]) == 2
