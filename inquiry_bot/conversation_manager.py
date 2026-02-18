"""会話状態管理 — セッション・履歴の保持とエスカレーション判定."""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


@dataclass
class Message:
    """1つのメッセージを表す."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    category: str = ""
    confidence: float = 0.0


@dataclass
class Session:
    """1つの会話セッション."""
    session_id: str
    channel: str  # "line" or "web"
    user_id: str
    messages: list[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    escalated: bool = False
    escalation_reason: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def user_message_count(self) -> int:
        return sum(1 for m in self.messages if m.role == "user")


class ConversationManager:
    """会話セッションの管理とエスカレーション判定."""

    ESCALATION_KEYWORDS = [
        "クレーム", "契約解除", "訴訟", "弁護士",
        "人間と話したい", "担当者", "責任者",
        "消費者センター", "退去", "解約",
    ]

    # セッションの有効期限（秒）
    SESSION_TIMEOUT = 3600  # 1時間

    def __init__(self, history_limit: int = 20):
        self.sessions: dict[str, Session] = {}
        self.history_limit = history_limit

    def get_or_create_session(
        self, session_id: str, channel: str, user_id: str
    ) -> Session:
        """セッションを取得。なければ新規作成."""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            # タイムアウトチェック
            if time.time() - session.last_activity > self.SESSION_TIMEOUT:
                logger.info("Session %s timed out, creating new", session_id)
                return self._create_session(session_id, channel, user_id)
            return session
        return self._create_session(session_id, channel, user_id)

    def _create_session(self, session_id: str, channel: str, user_id: str) -> Session:
        session = Session(session_id=session_id, channel=channel, user_id=user_id)
        self.sessions[session_id] = session
        return session

    def add_message(self, session_id: str, role: str, content: str, **kwargs) -> None:
        """メッセージをセッションに追加."""
        session = self.sessions.get(session_id)
        if not session:
            logger.warning("Session %s not found", session_id)
            return

        msg = Message(role=role, content=content, **kwargs)
        session.messages.append(msg)
        session.last_activity = time.time()

        # 履歴上限を超えたら古いメッセージを削除
        if len(session.messages) > self.history_limit * 2:
            session.messages = session.messages[-self.history_limit * 2:]

    def get_conversation_history(self, session_id: str) -> list[dict]:
        """Claude API用の会話履歴を取得."""
        session = self.sessions.get(session_id)
        if not session:
            return []

        # 直近N往復を取得
        messages = session.messages[-(self.history_limit * 2):]
        return [{"role": m.role, "content": m.content} for m in messages]

    def check_escalation(self, session_id: str, user_message: str) -> tuple[bool, str]:
        """エスカレーションが必要かどうかを判定."""
        session = self.sessions.get(session_id)
        if not session:
            return False, ""

        # 既にエスカレーション済み
        if session.escalated:
            return True, session.escalation_reason

        # キーワードチェック
        for keyword in self.ESCALATION_KEYWORDS:
            if keyword in user_message:
                reason = f"エスカレーションキーワード検出: 「{keyword}」"
                self._escalate(session, reason)
                return True, reason

        # 同じ質問の繰り返しチェック（直近3件のユーザーメッセージが類似）
        user_msgs = [m.content for m in session.messages if m.role == "user"]
        if len(user_msgs) >= 3:
            recent = user_msgs[-3:]
            # 簡易的な類似判定（同じキーワードが繰り返されている）
            words_sets = [set(msg) for msg in recent]
            if len(words_sets) >= 3:
                common = words_sets[0] & words_sets[1] & words_sets[2]
                if len(common) > len(recent[0]) * 0.5:
                    reason = "同じ質問が3回以上繰り返されました"
                    self._escalate(session, reason)
                    return True, reason

        return False, ""

    def _escalate(self, session: Session, reason: str) -> None:
        session.escalated = True
        session.escalation_reason = reason
        logger.warning(
            "Session %s escalated: %s (user: %s, channel: %s)",
            session.session_id, reason, session.user_id, session.channel,
        )

    def get_session_stats(self, session_id: str) -> dict:
        """セッションの統計情報を取得."""
        session = self.sessions.get(session_id)
        if not session:
            return {}

        return {
            "session_id": session.session_id,
            "channel": session.channel,
            "message_count": session.message_count,
            "user_messages": session.user_message_count,
            "escalated": session.escalated,
            "duration_seconds": time.time() - session.created_at,
            "created_at": datetime.fromtimestamp(
                session.created_at, tz=JST
            ).isoformat(),
        }

    def cleanup_expired_sessions(self) -> int:
        """期限切れセッションを削除."""
        now = time.time()
        expired = [
            sid for sid, s in self.sessions.items()
            if now - s.last_activity > self.SESSION_TIMEOUT
        ]
        for sid in expired:
            del self.sessions[sid]
        if expired:
            logger.info("Cleaned up %d expired sessions", len(expired))
        return len(expired)
