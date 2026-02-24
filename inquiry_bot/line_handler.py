"""LINE Messaging API Webhook Handler — LINE公式アカウント連携."""

import hashlib
import hmac
import base64
import json
import logging
import os
from typing import Optional

import requests
from dotenv import load_dotenv

from inquiry_bot.bot_engine import BotEngine

load_dotenv()

logger = logging.getLogger(__name__)

LINE_API_BASE = "https://api.line.me/v2/bot"


class LineHandler:
    """LINE Messaging API のWebhook処理とメッセージ送受信.

    LINE公式アカウントのWebhookイベントを受け取り、
    BotEngineで応答を生成してLINE APIで返信する。
    """

    def __init__(self, bot_engine: Optional[BotEngine] = None):
        self.bot = bot_engine or BotEngine()
        self.channel_secret = os.getenv("LINE_CHANNEL_SECRET", "")
        self.channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")

    def verify_signature(self, body: str, signature: str) -> bool:
        """Webhookリクエストの署名を検証."""
        if not self.channel_secret:
            logger.error("LINE_CHANNEL_SECRET not set — rejecting webhook for security")
            return False

        hash_digest = hmac.new(
            self.channel_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected = base64.b64encode(hash_digest).decode("utf-8")
        return hmac.compare_digest(expected, signature)

    def handle_webhook(self, body: str, signature: str = "") -> dict:
        """LINE Webhookイベントを処理.

        Args:
            body: リクエストボディ（JSON文字列）
            signature: X-Line-Signature ヘッダー値

        Returns:
            処理結果のdict
        """
        # 署名検証
        if signature and not self.verify_signature(body, signature):
            logger.error("Invalid LINE webhook signature")
            return {"error": "Invalid signature", "status": 403}

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in LINE webhook body")
            return {"error": "Invalid JSON", "status": 400}

        events = payload.get("events", [])
        results = []

        for event in events:
            result = self._process_event(event)
            results.append(result)

        return {"status": 200, "results": results}

    def _process_event(self, event: dict) -> dict:
        """個別のLINEイベントを処理."""
        event_type = event.get("type")
        reply_token = event.get("replyToken", "")

        if event_type == "message":
            return self._handle_message_event(event, reply_token)
        elif event_type == "follow":
            return self._handle_follow_event(event, reply_token)
        elif event_type == "unfollow":
            return self._handle_unfollow_event(event)
        elif event_type == "postback":
            return self._handle_postback_event(event, reply_token)
        else:
            logger.info("Unhandled LINE event type: %s", event_type)
            return {"event_type": event_type, "handled": False}

    def _handle_message_event(self, event: dict, reply_token: str) -> dict:
        """テキストメッセージイベントを処理."""
        message = event.get("message", {})
        msg_type = message.get("type")

        if msg_type != "text":
            # テキスト以外は案内メッセージを返す
            self._reply(reply_token, [
                self._text_message(
                    "申し訳ございません。テキストメッセージでお問い合わせください。\n"
                    "※ 写真や設備の故障報告はテキストで状況をお伝えいただき、\n"
                    "写真は担当者にメールでお送りください。"
                )
            ])
            return {"event_type": "message", "msg_type": msg_type, "handled": True}

        user_text = message.get("text", "")
        source = event.get("source", {})
        user_id = source.get("userId", "unknown")
        # LINEはユーザーIDをセッションIDとして使用
        session_id = f"line_{user_id}"

        # BotEngineで応答生成
        response = self.bot.handle_message(
            user_message=user_text,
            session_id=session_id,
            channel="line",
            user_id=user_id,
        )

        reply_text = response.get("reply", "")

        # LINE APIで返信
        messages = [self._text_message(reply_text)]

        # 内見予約カテゴリの場合、クイックリプライを追加
        if response.get("category") == "viewing":
            messages[0]["quickReply"] = {
                "items": [
                    self._quick_reply_action("内見を予約する", "viewing_book"),
                    self._quick_reply_action("3Dバーチャルツアー", "viewing_3d"),
                    self._quick_reply_action("他の物件も見たい", "viewing_others"),
                ]
            }

        self._reply(reply_token, messages)

        return {
            "event_type": "message",
            "msg_type": "text",
            "handled": True,
            "category": response.get("category"),
            "escalated": response.get("escalated", False),
        }

    def _handle_follow_event(self, event: dict, reply_token: str) -> dict:
        """友だち追加イベント."""
        web_chat_cfg = self.bot.config.get("web_chat", {}).get("widget", {})
        welcome = web_chat_cfg.get(
            "welcome_message",
            "友だち追加ありがとうございます！物件のご質問はお気軽にどうぞ。"
        )

        self._reply(reply_token, [
            self._text_message(welcome),
        ])

        source = event.get("source", {})
        user_id = source.get("userId", "unknown")
        logger.info("New LINE follower: %s", user_id)

        return {"event_type": "follow", "handled": True}

    def _handle_unfollow_event(self, event: dict) -> dict:
        """ブロック（友だち解除）イベント."""
        source = event.get("source", {})
        user_id = source.get("userId", "unknown")
        logger.info("LINE unfollowed: %s", user_id)
        return {"event_type": "unfollow", "handled": True}

    def _handle_postback_event(self, event: dict, reply_token: str) -> dict:
        """ポストバックイベント（リッチメニュー/クイックリプライ）."""
        postback_data = event.get("postback", {}).get("data", "")
        source = event.get("source", {})
        user_id = source.get("userId", "unknown")
        session_id = f"line_{user_id}"

        # ポストバックデータに応じた処理
        action_map = {
            "viewing_book": "内見を予約したいです。希望日時を教えてください。",
            "viewing_3d": "3Dバーチャルツアーのリンクを送ってください。",
            "viewing_others": "他にも見たい物件があります。条件を教えてください。",
        }

        user_message = action_map.get(postback_data, postback_data)
        response = self.bot.handle_message(
            user_message=user_message,
            session_id=session_id,
            channel="line",
            user_id=user_id,
        )

        self._reply(reply_token, [self._text_message(response.get("reply", ""))])

        return {"event_type": "postback", "data": postback_data, "handled": True}

    # ─── LINE API Helper Methods ───

    def _reply(self, reply_token: str, messages: list) -> bool:
        """LINE Reply API でメッセージを返信."""
        if not self.channel_access_token:
            logger.warning("LINE_CHANNEL_ACCESS_TOKEN not set, cannot reply")
            return False

        try:
            resp = requests.post(
                f"{LINE_API_BASE}/message/reply",
                headers={
                    "Authorization": f"Bearer {self.channel_access_token}",
                    "Content-Type": "application/json",
                },
                json={"replyToken": reply_token, "messages": messages},
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error("LINE reply failed: %s", e)
            return False

    def _push_message(self, user_id: str, messages: list) -> bool:
        """LINE Push API でメッセージをプッシュ送信."""
        if not self.channel_access_token:
            logger.warning("LINE_CHANNEL_ACCESS_TOKEN not set, cannot push")
            return False

        try:
            resp = requests.post(
                f"{LINE_API_BASE}/message/push",
                headers={
                    "Authorization": f"Bearer {self.channel_access_token}",
                    "Content-Type": "application/json",
                },
                json={"to": user_id, "messages": messages},
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error("LINE push failed: %s", e)
            return False

    @staticmethod
    def _text_message(text: str) -> dict:
        return {"type": "text", "text": text}

    @staticmethod
    def _quick_reply_action(label: str, data: str) -> dict:
        return {
            "type": "action",
            "action": {
                "type": "postback",
                "label": label,
                "data": data,
                "displayText": label,
            },
        }
