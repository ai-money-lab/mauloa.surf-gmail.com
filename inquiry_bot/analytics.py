"""分析モジュール — 問い合わせデータのKPIトラッキング & 日次レポート生成."""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from core.notifier import Notifier

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
ANALYTICS_DIR = Path(__file__).parent.parent / "data" / "inquiry_bot_logs"


class InquiryAnalytics:
    """問い合わせBotの分析とKPIレポート生成.

    計測するKPI:
    - 総問い合わせ数（日/週/月）
    - 自動応答率（AIが完結した割合）
    - エスカレーション率
    - 平均応答時間
    - カテゴリ別分布
    - チャネル別分布（LINE / Web）
    - ピーク時間帯
    - 削減した対応時間の推定
    """

    # 1件あたりの人間対応時間（分）の推定値
    HUMAN_RESPONSE_MINUTES = 5

    def __init__(self):
        ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
        self.notifier = Notifier()

    def log_inquiry(self, data: dict) -> None:
        """1件の問い合わせをログに記録."""
        now = datetime.now(JST)
        data["logged_at"] = now.isoformat()
        data["date"] = now.strftime("%Y-%m-%d")
        data["hour"] = now.hour

        # 日次ログファイルに追記
        log_file = ANALYTICS_DIR / f"inquiries_{now.strftime('%Y%m%d')}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def load_logs(self, days: int = 30) -> list[dict]:
        """過去N日分のログを読み込み."""
        logs = []
        now = datetime.now(JST)
        for i in range(days):
            date = now - timedelta(days=i)
            log_file = ANALYTICS_DIR / f"inquiries_{date.strftime('%Y%m%d')}.jsonl"
            if log_file.exists():
                for line in log_file.read_text(encoding="utf-8").strip().split("\n"):
                    if line:
                        try:
                            logs.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return logs

    def generate_daily_report(self, date: Optional[str] = None) -> str:
        """日次レポートを生成."""
        if date is None:
            date = datetime.now(JST).strftime("%Y-%m-%d")

        logs = [l for l in self.load_logs(1) if l.get("date") == date]

        if not logs:
            return f"📊 {date} の問い合わせ: 0件"

        total = len(logs)
        auto_resolved = sum(1 for l in logs if not l.get("escalated", False))
        escalated = total - auto_resolved
        auto_rate = (auto_resolved / total * 100) if total > 0 else 0

        # カテゴリ別
        categories = {}
        for l in logs:
            cat = l.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        # チャネル別
        channels = {}
        for l in logs:
            ch = l.get("channel", "unknown")
            channels[ch] = channels.get(ch, 0) + 1

        # 時間帯別
        hours = {}
        for l in logs:
            h = l.get("hour", 0)
            hours[h] = hours.get(h, 0) + 1
        peak_hour = max(hours, key=hours.get) if hours else "-"

        # 削減時間の推定
        saved_minutes = auto_resolved * self.HUMAN_RESPONSE_MINUTES
        saved_hours = saved_minutes / 60

        cat_text = "\n".join(f"  {k}: {v}件" for k, v in
                            sorted(categories.items(), key=lambda x: x[1], reverse=True))
        ch_text = "\n".join(f"  {k}: {v}件" for k, v in channels.items())

        report = f"""📊 問い合わせBot 日次レポート ({date})
━━━━━━━━━━━━━━━━━━━━━━━━━

📌 サマリー
  総問い合わせ数: {total}件
  AI自動応答: {auto_resolved}件 ({auto_rate:.0f}%)
  エスカレーション: {escalated}件 ({100 - auto_rate:.0f}%)

💰 削減効果
  推定削減時間: {saved_hours:.1f}時間 ({saved_minutes}分)
  ※ 1件あたり人間対応{self.HUMAN_RESPONSE_MINUTES}分で計算

📂 カテゴリ別
{cat_text}

📱 チャネル別
{ch_text}

⏰ ピーク時間帯: {peak_hour}時台
━━━━━━━━━━━━━━━━━━━━━━━━━"""

        return report

    def generate_monthly_summary(self) -> str:
        """月次サマリーを生成（Coconala出品用の実績データ）."""
        logs = self.load_logs(30)

        if not logs:
            return "データなし（運用開始前）"

        total = len(logs)
        auto_resolved = sum(1 for l in logs if not l.get("escalated", False))
        auto_rate = (auto_resolved / total * 100) if total > 0 else 0
        saved_minutes = auto_resolved * self.HUMAN_RESPONSE_MINUTES
        saved_hours = saved_minutes / 60

        # 日別の平均
        dates = set(l.get("date", "") for l in logs)
        daily_avg = total / len(dates) if dates else 0

        summary = f"""📊 問い合わせBot 月次サマリー（過去30日間）
━━━━━━━━━━━━━━━━━━━━━━━━━

📌 実績データ
  総問い合わせ数: {total}件
  1日あたり平均: {daily_avg:.1f}件
  AI自動応答率: {auto_rate:.0f}%
  エスカレーション率: {100 - auto_rate:.0f}%

💰 削減効果（月間）
  推定削減時間: {saved_hours:.1f}時間
  推定コスト削減: 約{int(saved_hours * 2000):,}円
  ※ 時給2,000円のスタッフが対応した場合

🏆 商品化用アピールポイント
  「月間{total}件の問い合わせを自動応答率{auto_rate:.0f}%で処理」
  「月{saved_hours:.0f}時間の業務時間を削減」
━━━━━━━━━━━━━━━━━━━━━━━━━"""

        return summary

    def send_daily_report(self) -> None:
        """日次レポートをLINE/Slackに送信."""
        report = self.generate_daily_report()
        self.notifier.notify(report)
        logger.info("Daily inquiry bot report sent")
