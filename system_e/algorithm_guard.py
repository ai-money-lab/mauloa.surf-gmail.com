"""System E — Algorithm Guard (引き算ルール).

X/Twitterアルゴリズムのペナルティ要因を投稿前にチェックし、
リーチを下げる行為を自動的にブロック・修正する。

設計原則: 「加点」より「減点を避ける」ことで安定的にリーチを伸ばす。

引き算ルール一覧:
1. 外部リンク → リーチ激減（絶対に投稿本文に入れない）
2. ハッシュタグ過多 → スパム判定（上限制御）
3. エンゲージメントベイト → ペナルティ（パターン検出）
4. 重複コンテンツ → 非表示化（類似度チェック）
5. 高頻度投稿 → シャドウバン（間隔制御）
6. @メンション乱用 → スパム判定（数制限）
7. 禁止トピック → アカウント制限（コンテンツフィルタ）
8. ボット的な投稿パターン → 自動化検出（ランダム化）
"""

import json
import logging
import random
import re
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
POSTED_LOG = Path(__file__).parent.parent / "data" / "system_e" / "posted_log.json"
HEALTH_LOG = Path(__file__).parent.parent / "data" / "system_e" / "analytics" / "account_health.json"
CONFIG_PATH = Path(__file__).parent / "character_config.yaml"


class AlgorithmGuard:
    """Pre-posting filter that blocks or fixes algorithm penalty triggers."""

    # ─── 引き算ルール定数 ───
    MAX_HASHTAGS = 3           # ブランド1 + コンテンツ1 = 最大2（余裕で3）
    MAX_MENTIONS_PER_POST = 2  # @メンション上限
    MIN_POST_INTERVAL_MIN = 30 # 最低投稿間隔（分）
    SIMILARITY_THRESHOLD = 0.7 # 類似度70%以上 = 重複判定
    RECENT_POSTS_WINDOW = 7    # 重複チェック対象日数

    # 外部リンクのパターン
    _URL_PATTERN = re.compile(
        r'https?://\S+|www\.\S+|bit\.ly/\S+|t\.co/\S+|linktr\.ee/\S+'
    )

    # エンゲージメントベイトのパターン（Xが明示的にペナルティ対象としているもの）
    _ENGAGEMENT_BAIT_PATTERNS = [
        r'\blike if\b',
        r'\bretweet if\b',
        r'\brt if\b',
        r'\bfollow me\b',
        r'\bfollow for follow\b',
        r'\bf4f\b',
        r'\bl4l\b',
        r'\blike and retweet\b',
        r'\blike & retweet\b',
        r'\blike and rt\b',
        r'\bshare this\b',
        r'\btag someone\b',
        r'\btag a friend\b',
        r'\brepost this\b',
        r'\bplease retweet\b',
        r'\bpls rt\b',
        r'\bgo follow\b',
        r'\bsmash that like\b',
        r'\bhit that follow\b',
    ]

    # @メンションパターン
    _MENTION_PATTERN = re.compile(r'@\w+')

    def __init__(self):
        self._load_banned_topics()

    def _load_banned_topics(self):
        """character_config.yamlから禁止トピックを読み込み."""
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            self.banned_topics = config.get("character", {}).get(
                "content_voice", {}
            ).get("banned_topics", [])
        except Exception:
            self.banned_topics = []

    def check_post(self, text: str) -> dict:
        """投稿テキストを全引き算ルールでチェック.

        Args:
            text: 投稿予定のテキスト（ハッシュタグ付与後の最終版）

        Returns:
            {
                "approved": bool,
                "violations": [{"rule": str, "severity": str, "detail": str}],
                "warnings": [{"rule": str, "detail": str}],
                "fixed_text": str | None,  # 自動修正可能な場合
            }
        """
        violations = []
        warnings = []
        fixed_text = text

        # ── Rule 1: 外部リンク検出（CRITICAL — リーチ激減）──
        links = self._URL_PATTERN.findall(text)
        if links:
            violations.append({
                "rule": "external_link",
                "severity": "critical",
                "detail": f"外部リンク検出: {links[0]}... — リーチが大幅に低下します",
            })
            # 自動修正: リンクを除去
            fixed_text = self._URL_PATTERN.sub("", fixed_text).strip()
            fixed_text = re.sub(r'\n{3,}', '\n\n', fixed_text)  # 空行整理

        # ── Rule 2: ハッシュタグ過多 ──
        hashtags = re.findall(r'#\w+', text)
        if len(hashtags) > self.MAX_HASHTAGS:
            violations.append({
                "rule": "hashtag_spam",
                "severity": "high",
                "detail": f"ハッシュタグ{len(hashtags)}個（上限{self.MAX_HASHTAGS}）",
            })
        elif len(hashtags) > 2:
            warnings.append({
                "rule": "hashtag_count_high",
                "detail": f"ハッシュタグ{len(hashtags)}個 — 最適は1-2個（リーチ低下リスク）",
            })

        # ── Rule 3: エンゲージメントベイト ──
        text_lower = text.lower()
        for pattern in self._ENGAGEMENT_BAIT_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                violations.append({
                    "rule": "engagement_bait",
                    "severity": "high",
                    "detail": f"エンゲージメントベイト検出: '{match.group()}'",
                })
                break  # 1つ見つかれば十分

        # ── Rule 4: 重複コンテンツチェック ──
        similarity, similar_text = self._check_duplicate(text)
        if similarity >= self.SIMILARITY_THRESHOLD:
            violations.append({
                "rule": "duplicate_content",
                "severity": "high",
                "detail": f"類似度{similarity:.0%}の過去投稿あり: '{similar_text[:60]}...'",
            })

        # ── Rule 5: 投稿間隔チェック ──
        minutes_since_last = self._minutes_since_last_post()
        if minutes_since_last is not None and minutes_since_last < self.MIN_POST_INTERVAL_MIN:
            violations.append({
                "rule": "posting_too_fast",
                "severity": "medium",
                "detail": f"前回投稿から{minutes_since_last}分（最低{self.MIN_POST_INTERVAL_MIN}分必要）",
            })

        # ── Rule 6: @メンション過多 ──
        mentions = self._MENTION_PATTERN.findall(text)
        if len(mentions) > self.MAX_MENTIONS_PER_POST:
            warnings.append({
                "rule": "mention_spam",
                "detail": f"@メンション{len(mentions)}個（推奨上限{self.MAX_MENTIONS_PER_POST}）",
            })

        # ── Rule 7: 禁止トピック ──
        for topic in self.banned_topics:
            # 禁止トピックのキーワードを抽出して検索
            keywords = topic.lower().split()
            # 2語以上が連続でマッチしたら警告
            for kw in keywords:
                if len(kw) > 4 and kw in text_lower:
                    warnings.append({
                        "rule": "banned_topic_risk",
                        "detail": f"禁止トピック関連語検出: '{kw}' (from: {topic})",
                    })
                    break

        # ── Rule 8: AI自称検出（bioで開示済みなので本文では不要）──
        ai_self_patterns = [
            r'\bi am an ai\b', r"\bi'm an ai\b", r'\bas an ai\b',
            r'\bai assistant\b', r'\bartificial intelligence\b',
        ]
        for pattern in ai_self_patterns:
            if re.search(pattern, text_lower):
                warnings.append({
                    "rule": "ai_self_disclosure_in_text",
                    "detail": "投稿内でAI自称 — bioで開示済みなので不要（不自然に見える）",
                })
                break

        # ── Rule 9: 空テキスト / 極端に短い ──
        # ハッシュタグを除いた本文テキストの長さ
        body_text = re.sub(r'#\w+', '', text).strip()
        if len(body_text) < 10:
            violations.append({
                "rule": "empty_or_too_short",
                "severity": "critical",
                "detail": f"本文が短すぎます（{len(body_text)}文字）",
            })

        approved = len(violations) == 0
        return {
            "approved": approved,
            "violations": violations,
            "warnings": warnings,
            "fixed_text": fixed_text if fixed_text != text else None,
        }

    def add_posting_jitter(self, base_minutes: int = 0) -> int:
        """投稿時間にランダムなずれを加えてボット検出を回避.

        Args:
            base_minutes: 基準の遅延分数

        Returns:
            実際の遅延分数（base + random jitter）
        """
        # ±7分のランダムジッター
        jitter = random.randint(-7, 7)
        return max(0, base_minutes + jitter)

    def check_account_health(self, recent_metrics: list[dict]) -> dict:
        """エンゲージメント急落でシャドウバンを検知.

        Args:
            recent_metrics: 直近のツイートメトリクス
                [{"impressions": int, "likes": int, "date": str}, ...]

        Returns:
            {"healthy": bool, "alerts": [...], "recommendation": str}
        """
        alerts = []

        if len(recent_metrics) < 3:
            return {"healthy": True, "alerts": [], "recommendation": "データ不足（3件以上必要）"}

        # インプレッション急落チェック
        impressions = [m.get("impressions", 0) for m in recent_metrics if m.get("impressions", 0) > 0]
        if len(impressions) >= 4:
            avg_older = sum(impressions[:-2]) / max(1, len(impressions) - 2)
            avg_recent = sum(impressions[-2:]) / 2
            if avg_older > 0 and avg_recent / avg_older < 0.3:
                alerts.append({
                    "type": "impression_drop",
                    "severity": "critical",
                    "detail": f"インプレッション急落: {avg_older:.0f} → {avg_recent:.0f} (▼{(1 - avg_recent/avg_older)*100:.0f}%)",
                })

        # エンゲージメント率急落
        engagement_rates = []
        for m in recent_metrics:
            imp = m.get("impressions", 0)
            if imp > 0:
                eng = m.get("likes", 0) + m.get("retweets", 0) + m.get("replies", 0)
                engagement_rates.append(eng / imp)

        if len(engagement_rates) >= 4:
            avg_older_er = sum(engagement_rates[:-2]) / max(1, len(engagement_rates) - 2)
            avg_recent_er = sum(engagement_rates[-2:]) / 2
            if avg_older_er > 0 and avg_recent_er / avg_older_er < 0.4:
                alerts.append({
                    "type": "engagement_rate_drop",
                    "severity": "high",
                    "detail": f"エンゲージメント率急落: {avg_older_er:.2%} → {avg_recent_er:.2%}",
                })

        # ゼロインプレッション（シャドウバンの典型的兆候）
        zero_imp_count = sum(1 for m in recent_metrics[-5:] if m.get("impressions", 0) == 0)
        if zero_imp_count >= 3:
            alerts.append({
                "type": "shadow_ban_suspected",
                "severity": "critical",
                "detail": f"直近5投稿中{zero_imp_count}件がインプレッション0 — シャドウバンの可能性",
            })

        healthy = len([a for a in alerts if a["severity"] == "critical"]) == 0

        recommendation = "正常" if healthy else "投稿を1-2日停止し、手動でアカウント状態を確認してください"

        # ログ保存
        self._save_health_check(alerts, healthy)

        return {
            "healthy": healthy,
            "alerts": alerts,
            "recommendation": recommendation,
        }

    def _check_duplicate(self, text: str) -> tuple[float, str]:
        """過去投稿との類似度をチェック."""
        if not POSTED_LOG.exists():
            return 0.0, ""

        try:
            records = json.loads(POSTED_LOG.read_text(encoding="utf-8"))
        except Exception:
            return 0.0, ""

        cutoff = (datetime.now(JST) - timedelta(days=self.RECENT_POSTS_WINDOW)).strftime("%Y-%m-%d")

        # ハッシュタグを除いた本文で比較
        clean_text = re.sub(r'#\w+', '', text).strip().lower()

        max_similarity = 0.0
        most_similar = ""

        for record in records:
            if record.get("date", "") < cutoff:
                continue
            past_text = re.sub(r'#\w+', '', record.get("text", "")).strip().lower()
            if not past_text:
                continue
            similarity = SequenceMatcher(None, clean_text, past_text).ratio()
            if similarity > max_similarity:
                max_similarity = similarity
                most_similar = record.get("text", "")

        return max_similarity, most_similar

    def _minutes_since_last_post(self) -> int | None:
        """最後の投稿からの経過分数."""
        if not POSTED_LOG.exists():
            return None

        try:
            records = json.loads(POSTED_LOG.read_text(encoding="utf-8"))
        except Exception:
            return None

        if not records:
            return None

        last = records[-1]
        posted_at = last.get("posted_at", "")
        if not posted_at:
            return None

        try:
            last_time = datetime.fromisoformat(posted_at)
            now = datetime.now(JST)
            return int((now - last_time).total_seconds() / 60)
        except (ValueError, TypeError):
            return None

    def _save_health_check(self, alerts: list, healthy: bool) -> None:
        """ヘルスチェック結果をログに保存."""
        HEALTH_LOG.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if HEALTH_LOG.exists():
            try:
                existing = json.loads(HEALTH_LOG.read_text(encoding="utf-8"))
            except Exception:
                existing = []

        existing.append({
            "checked_at": datetime.now(JST).isoformat(),
            "healthy": healthy,
            "alerts": alerts,
        })

        # 直近30件のみ保持
        HEALTH_LOG.write_text(
            json.dumps(existing[-30:], ensure_ascii=False, indent=2), encoding="utf-8"
        )
