"""Bot Insights Bridge — Inquiry Bot → System E の知見フィードバック.

問い合わせBotの運用データ（問い合わせパターン、エスカレーション傾向、
FAQ未対応パターン等）を System E のメタ知性にフィードバックし、
Bot自身の改善提案や全体戦略への反映を行う。

フロー:
  Inquiry Bot logs → BotInsightsBridge → System E evolution metrics
                                       → System E debate topics
                                       → FAQ improvement proposals
"""

import json
import logging
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from system_e.client import ClaudeClient
from system_e.agents import AgentRunner, STRATEGIST, OPTIMIZER

logger = logging.getLogger("system_e.bot_insights_bridge")

JST = timezone(timedelta(hours=9))
BOT_LOGS_DIR = Path(__file__).parent.parent / "data" / "inquiry_bot_logs"
INSIGHTS_DIR = Path(__file__).parent / "data" / "bot_insights"


class BotInsightsBridge:
    """Inquiry Bot の運用データを System E に接続するブリッジ.

    Bot の問い合わせログを分析し、以下を生成する:
    - 進化エンジン用メトリクス（自動応答率、エスカレーション率等）
    - AI議論用トピック（Bot改善施策）
    - FAQ改善提案（低信頼度パターンの検出）

    Args:
        claude_client: ClaudeClient インスタンス。
        bot_logs_dir: Bot ログディレクトリ。
    """

    def __init__(
        self,
        claude_client: Optional[ClaudeClient] = None,
        bot_logs_dir: Optional[Path] = None,
    ):
        self.claude = claude_client or ClaudeClient()
        self.strategist = AgentRunner(STRATEGIST, self.claude)
        self.optimizer = AgentRunner(OPTIMIZER, self.claude)
        self.bot_logs_dir = bot_logs_dir or BOT_LOGS_DIR
        INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    def load_bot_logs(self, days: int = 30) -> list[dict]:
        """Bot の問い合わせログを読み込む.

        Args:
            days: 遡る日数。

        Returns:
            問い合わせログエントリのリスト。
        """
        if not self.bot_logs_dir.exists():
            logger.info("Bot logs directory not found: %s", self.bot_logs_dir)
            return []

        logs: list[dict] = []
        now = datetime.now(JST)
        for i in range(days):
            date = now - timedelta(days=i)
            log_file = self.bot_logs_dir / f"inquiries_{date.strftime('%Y%m%d')}.jsonl"
            if log_file.exists():
                for line in log_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        logs.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        logger.info("Loaded %d bot log entries (%d days)", len(logs), days)
        return logs

    def compute_bot_metrics(self, logs: Optional[list[dict]] = None) -> dict:
        """Bot の KPI メトリクスを算出.

        Returns:
            {
                "total_inquiries": int,
                "auto_resolve_rate": float,
                "escalation_rate": float,
                "avg_confidence": float,
                "category_distribution": dict,
                "channel_distribution": dict,
                "peak_hours": list,
                "low_confidence_count": int,
                "saved_hours": float,
            }
        """
        if logs is None:
            logs = self.load_bot_logs(days=7)

        if not logs:
            return {
                "total_inquiries": 0,
                "auto_resolve_rate": 0.0,
                "escalation_rate": 0.0,
                "avg_confidence": 0.0,
                "category_distribution": {},
                "channel_distribution": {},
                "peak_hours": [],
                "low_confidence_count": 0,
                "saved_hours": 0.0,
            }

        total = len(logs)
        escalated = sum(1 for e in logs if e.get("escalated", False))
        auto_resolved = total - escalated

        confidences = [e.get("confidence", 0.0) for e in logs if "confidence" in e]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        categories: Counter = Counter()
        channels: Counter = Counter()
        hours: Counter = Counter()
        low_confidence = 0

        for entry in logs:
            categories[entry.get("category", "unknown")] += 1
            channels[entry.get("channel", "unknown")] += 1
            hours[entry.get("hour", 0)] += 1
            if entry.get("confidence", 1.0) < 0.5:
                low_confidence += 1

        # ピーク時間帯 (上位3)
        peak_hours = [h for h, _ in hours.most_common(3)]

        return {
            "total_inquiries": total,
            "auto_resolve_rate": auto_resolved / total if total > 0 else 0.0,
            "escalation_rate": escalated / total if total > 0 else 0.0,
            "avg_confidence": round(avg_confidence, 3),
            "category_distribution": dict(categories.most_common()),
            "channel_distribution": dict(channels),
            "peak_hours": peak_hours,
            "low_confidence_count": low_confidence,
            "saved_hours": round(auto_resolved * 5 / 60, 1),
        }

    def detect_improvement_patterns(
        self, logs: Optional[list[dict]] = None,
    ) -> dict:
        """改善が必要なパターンを検出.

        低信頼度の回答、頻出エスカレーション、未対応カテゴリを特定する。

        Returns:
            {
                "faq_gaps": list,           # FAQ に追加すべきパターン
                "escalation_hotspots": list, # エスカレーションが多いカテゴリ
                "confidence_issues": list,   # 信頼度が低い質問パターン
            }
        """
        if logs is None:
            logs = self.load_bot_logs(days=7)

        faq_gaps: Counter = Counter()
        escalation_cats: Counter = Counter()
        low_conf_patterns: list[dict] = []

        for entry in logs:
            confidence = entry.get("confidence", 1.0)
            escalated = entry.get("escalated", False)
            category = entry.get("category", "unknown")
            message = entry.get("message", "")

            if confidence < 0.5 and not escalated:
                pattern_key = f"{category}:{message[:60]}"
                faq_gaps[pattern_key] += 1

            if escalated:
                escalation_cats[category] += 1

            if confidence < 0.3:
                low_conf_patterns.append({
                    "category": category,
                    "message": message[:80],
                    "confidence": confidence,
                })

        return {
            "faq_gaps": [
                {"pattern": k, "count": v}
                for k, v in faq_gaps.most_common(10)
                if v >= 2
            ],
            "escalation_hotspots": [
                {"category": k, "count": v}
                for k, v in escalation_cats.most_common(5)
            ],
            "confidence_issues": low_conf_patterns[:10],
        }

    def generate_evolution_feedback(self) -> dict:
        """System E 進化エンジン用のフィードバックメトリクスを生成.

        進化エンジンが Bot 運用データを含めて戦略を最適化できるようにする。
        """
        logs_7d = self.load_bot_logs(days=7)
        logs_30d = self.load_bot_logs(days=30)

        metrics_7d = self.compute_bot_metrics(logs_7d)
        metrics_30d = self.compute_bot_metrics(logs_30d)
        patterns = self.detect_improvement_patterns(logs_7d)

        feedback = {
            "source": "bot_insights_bridge",
            "collected_at": datetime.now(JST).isoformat(),
            "bot_weekly_metrics": metrics_7d,
            "bot_monthly_metrics": {
                "total_inquiries": metrics_30d["total_inquiries"],
                "auto_resolve_rate": metrics_30d["auto_resolve_rate"],
                "escalation_rate": metrics_30d["escalation_rate"],
                "saved_hours": metrics_30d["saved_hours"],
            },
            "improvement_patterns": patterns,
            "bot_health_indicators": {
                "auto_resolve_rate_healthy": metrics_7d["auto_resolve_rate"] >= 0.7,
                "escalation_rate_healthy": metrics_7d["escalation_rate"] <= 0.3,
                "confidence_healthy": metrics_7d["avg_confidence"] >= 0.6,
                "has_faq_gaps": len(patterns["faq_gaps"]) > 0,
            },
        }

        self._save_insight("evolution_feedback", feedback)
        return feedback

    def analyze_bot_strategy(self) -> dict:
        """Bot の運用戦略を Strategist エージェントが分析.

        Bot のパフォーマンスデータを元に改善施策を提案する。
        """
        logs = self.load_bot_logs(days=7)
        metrics = self.compute_bot_metrics(logs)
        patterns = self.detect_improvement_patterns(logs)

        context = json.dumps(
            {"metrics": metrics, "patterns": patterns},
            ensure_ascii=False,
            indent=2,
        )

        analysis = self.strategist.think(
            task=(
                "問い合わせBot の運用データを分析し、以下を報告してください:\n"
                "1. 現在のBot パフォーマンス評価\n"
                "2. FAQ に追加すべき質問パターン\n"
                "3. エスカレーション削減のための施策\n"
                "4. Bot の応答品質向上のための提案\n"
                "5. System E が介入すべきポイント"
            ),
            context=context,
        )

        self._save_insight("bot_strategy_analysis", analysis)
        return analysis

    def generate_faq_proposals(self) -> dict:
        """FAQ 改善提案を Optimizer エージェントが生成.

        低信頼度パターンから具体的な FAQ エントリ追加を提案する。
        """
        patterns = self.detect_improvement_patterns()

        if not patterns["faq_gaps"]:
            return {
                "proposals": [],
                "note": "No FAQ gaps detected. Current FAQ coverage is adequate.",
            }

        context = json.dumps(patterns, ensure_ascii=False, indent=2)

        proposals = self.optimizer.think(
            task=(
                "以下の問い合わせパターンから、FAQに追加すべきエントリを提案してください。\n"
                "各提案は以下の形式で出力:\n"
                "{\n"
                '  "proposals": [\n'
                '    {"question": "想定質問", "answer": "回答案", "category": "カテゴリ"}\n'
                "  ]\n"
                "}"
            ),
            context=context,
        )

        self._save_insight("faq_proposals", proposals)
        return proposals

    def run_insight_cycle(self) -> dict:
        """Bot Insights の完全サイクルを実行.

        1. Bot メトリクス収集
        2. 改善パターン検出
        3. 戦略分析 (AI)
        4. 進化用フィードバック生成

        Returns:
            サイクル結果 dict。
        """
        logger.info("=== BOT INSIGHTS CYCLE START ===")
        result: dict = {}

        # Step 1: Metrics
        try:
            logger.info("[BotInsight 1/4] Computing bot metrics")
            result["metrics"] = self.compute_bot_metrics()
        except Exception as e:
            logger.error("[BotInsight 1/4] Metrics failed: %s", e)
            result["metrics"] = {"error": str(e)}

        # Step 2: Patterns
        try:
            logger.info("[BotInsight 2/4] Detecting improvement patterns")
            result["patterns"] = self.detect_improvement_patterns()
        except Exception as e:
            logger.error("[BotInsight 2/4] Pattern detection failed: %s", e)
            result["patterns"] = {"error": str(e)}

        # Step 3: Strategy analysis
        try:
            logger.info("[BotInsight 3/4] Analyzing bot strategy")
            result["strategy_analysis"] = self.analyze_bot_strategy()
        except Exception as e:
            logger.error("[BotInsight 3/4] Strategy analysis failed: %s", e)
            result["strategy_analysis"] = {"error": str(e)}

        # Step 4: Evolution feedback
        try:
            logger.info("[BotInsight 4/4] Generating evolution feedback")
            result["evolution_feedback"] = self.generate_evolution_feedback()
        except Exception as e:
            logger.error("[BotInsight 4/4] Feedback generation failed: %s", e)
            result["evolution_feedback"] = {"error": str(e)}

        self._save_insight("insight_cycle", result)
        logger.info("=== BOT INSIGHTS CYCLE COMPLETE ===")
        return result

    def _save_insight(self, action: str, data: dict) -> None:
        """インサイトログを保存."""
        ts = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
        entry = {
            "timestamp": datetime.now(JST).isoformat(),
            "action": action,
            "data": data,
        }
        log_path = INSIGHTS_DIR / f"insight_{action}_{ts}.json"
        log_path.write_text(
            json.dumps(entry, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
