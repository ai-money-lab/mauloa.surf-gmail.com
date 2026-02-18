"""Bot Engine — Claude APIを使った問い合わせ応答の中枢."""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import yaml

from core.claude_client import ClaudeClient
from core.notifier import Notifier
from inquiry_bot.knowledge_base import KnowledgeBase
from inquiry_bot.conversation_manager import ConversationManager

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
CONFIG_PATH = Path(__file__).parent / "config.yaml"
PROPERTIES_PATH = Path(__file__).parent / "properties.yaml"
SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "inquiry_bot_system.txt"


class BotEngine:
    """問い合わせ自動対応Botの中枢エンジン.

    - ナレッジベースからFAQ検索
    - Claude APIで自然な応答生成
    - エスカレーション判定
    - 会話履歴管理
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        claude_client: Optional[ClaudeClient] = None,
        knowledge_base: Optional[KnowledgeBase] = None,
    ):
        self.config = self._load_config(config_path or CONFIG_PATH)
        bot_cfg = self.config.get("bot", {})

        self.claude = claude_client or ClaudeClient(model=bot_cfg.get("model"))
        self.kb = knowledge_base or KnowledgeBase()
        # 物件データを自動読み込み
        if PROPERTIES_PATH.exists():
            self.kb.load_properties_from_yaml(PROPERTIES_PATH)
        self.conversation = ConversationManager(
            history_limit=bot_cfg.get("conversation_history_limit", 20)
        )
        self.notifier = Notifier()
        self.system_prompt = self._build_system_prompt()

    def _load_config(self, path: Path) -> dict:
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("Config load failed: %s", e)
            return {}

    def _build_system_prompt(self) -> str:
        """システムプロンプトを構築."""
        try:
            template = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error("System prompt not found: %s", SYSTEM_PROMPT_PATH)
            return ""

        bot_cfg = self.config.get("bot", {})
        company = self.kb.company

        prompt = template.replace("{bot_name}", bot_cfg.get("name", "AIアシスタント"))
        prompt = prompt.replace("{company_name}", company.get("name", ""))
        prompt = prompt.replace("{business_hours}", company.get("business_hours", ""))
        prompt = prompt.replace("{knowledge_base}", self.kb.get_faq_context())
        prompt = prompt.replace("{property_data}", self.kb.get_all_properties_summary())

        return prompt

    def handle_message(
        self,
        user_message: str,
        session_id: str,
        channel: str = "web",
        user_id: str = "anonymous",
    ) -> dict:
        """ユーザーメッセージを処理して応答を返す.

        Returns:
            dict: {
                "reply": str,
                "category": str,
                "escalated": bool,
                "escalation_reason": str,
                "session_id": str,
            }
        """
        # セッション取得/作成
        session = self.conversation.get_or_create_session(
            session_id, channel, user_id
        )

        # エスカレーション判定
        should_escalate, reason = self.conversation.check_escalation(
            session_id, user_message
        )
        if should_escalate:
            return self._handle_escalation(session_id, user_message, reason, channel)

        # ユーザーメッセージを記録
        self.conversation.add_message(session_id, "user", user_message)

        # FAQ検索（高速パス）
        faq_results = self.kb.search_faq(user_message)

        # Claude APIで応答生成
        try:
            response = self._generate_response(session_id, user_message, faq_results)
        except Exception as e:
            logger.error("Response generation failed: %s", e)
            response = self._fallback_response()

        # 応答を記録
        reply_text = response.get("reply", "")
        self.conversation.add_message(
            session_id, "assistant", reply_text,
            category=response.get("category", ""),
            confidence=response.get("confidence", 0.0),
        )

        # エスカレーション判定（AI側の判断）
        if response.get("escalate"):
            self._notify_escalation(
                session_id, channel, user_id,
                response.get("escalate_reason", "AI判定によるエスカレーション"),
            )

        return {
            "reply": reply_text,
            "category": response.get("category", "general"),
            "escalated": response.get("escalate", False),
            "escalation_reason": response.get("escalate_reason", ""),
            "session_id": session_id,
            "confidence": response.get("confidence", 0.0),
        }

    def _generate_response(
        self, session_id: str, user_message: str, faq_results: list
    ) -> dict:
        """Claude APIを使って応答を生成."""
        # 会話履歴を取得
        history = self.conversation.get_conversation_history(session_id)

        # FAQコンテキストを追加
        faq_context = ""
        if faq_results:
            top_faq = faq_results[0]["faq"]
            faq_context = (
                f"\n\n## 最も関連性の高いFAQ:\n"
                f"カテゴリ: {top_faq['category']}\n"
                f"回答テンプレート: {top_faq['answer']}\n"
                f"※ テンプレート内の変数は適切な値に置換してください。"
                f"データがない場合は「確認いたします」と回答してください。"
            )

        # プロンプト構築
        prompt = f"ユーザーからのメッセージ:\n{user_message}\n{faq_context}"

        # 会話履歴をシステムプロンプトに含める
        history_text = ""
        if history[:-1]:  # 最新のユーザーメッセージは除く
            history_text = "\n\n## これまでの会話:\n"
            for msg in history[:-1]:
                role = "お客様" if msg["role"] == "user" else "アシスタント"
                history_text += f"{role}: {msg['content']}\n"

        full_system = self.system_prompt + history_text

        bot_cfg = self.config.get("bot", {})
        raw = self.claude.generate(
            prompt=prompt,
            system=full_system,
            max_tokens=bot_cfg.get("max_tokens", 1024),
            temperature=bot_cfg.get("temperature", 0.4),
        )

        # JSONパース
        try:
            text = raw.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [l for l in lines[1:] if not l.strip().startswith("```")]
                text = "\n".join(lines)
            return json.loads(text)
        except json.JSONDecodeError:
            # JSONパース失敗時はテキストをそのまま返す
            logger.warning("Failed to parse bot response as JSON, using raw text")
            return {
                "reply": raw.strip(),
                "category": "general",
                "confidence": 0.5,
                "escalate": False,
            }

    def _handle_escalation(
        self, session_id: str, user_message: str, reason: str, channel: str
    ) -> dict:
        """エスカレーション処理."""
        escalation_cfg = self.config.get("escalation", {})
        reply = escalation_cfg.get(
            "escalation_message",
            "担当者に確認いたします。少々お待ちくださいませ。"
        )

        self.conversation.add_message(session_id, "user", user_message)
        self.conversation.add_message(session_id, "assistant", reply)

        # 通知送信
        session = self.conversation.sessions.get(session_id)
        user_id = session.user_id if session else "unknown"
        self._notify_escalation(session_id, channel, user_id, reason)

        return {
            "reply": reply,
            "category": "escalation",
            "escalated": True,
            "escalation_reason": reason,
            "session_id": session_id,
            "confidence": 1.0,
        }

    def _notify_escalation(
        self, session_id: str, channel: str, user_id: str, reason: str
    ) -> None:
        """エスカレーション通知を送信."""
        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
        msg = (
            f"🚨 エスカレーション発生\n"
            f"日時: {now}\n"
            f"チャネル: {channel}\n"
            f"ユーザー: {user_id}\n"
            f"セッション: {session_id}\n"
            f"理由: {reason}"
        )
        self.notifier.notify(msg)

    def _fallback_response(self) -> dict:
        """APIエラー時のフォールバック応答."""
        return {
            "reply": (
                "申し訳ございません。只今システムに一時的な問題が発生しております。\n"
                "お手数ですが、しばらく経ってから再度お問い合わせいただくか、\n"
                f"お電話（{self.kb.company.get('phone', '')}）にてご連絡ください。"
            ),
            "category": "error",
            "confidence": 0.0,
            "escalate": True,
            "escalate_reason": "システムエラーによる自動エスカレーション",
        }

    def get_analytics(self) -> dict:
        """全セッションの分析データを取得."""
        stats = {
            "total_sessions": len(self.conversation.sessions),
            "active_sessions": 0,
            "escalated_sessions": 0,
            "total_messages": 0,
            "categories": {},
            "channels": {"line": 0, "web": 0},
        }

        import time as _time
        now = _time.time()

        for session in self.conversation.sessions.values():
            if now - session.last_activity < self.conversation.SESSION_TIMEOUT:
                stats["active_sessions"] += 1
            if session.escalated:
                stats["escalated_sessions"] += 1
            stats["total_messages"] += session.message_count
            stats["channels"][session.channel] = (
                stats["channels"].get(session.channel, 0) + 1
            )

            for msg in session.messages:
                if msg.category:
                    stats["categories"][msg.category] = (
                        stats["categories"].get(msg.category, 0) + 1
                    )

        return stats
