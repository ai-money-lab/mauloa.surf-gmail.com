"""定期タスクスケジューラー — crontabから呼び出される自動化タスク.

使い方:
  python -m inquiry_bot.scheduler daily_report
  python -m inquiry_bot.scheduler health_check
  python -m inquiry_bot.scheduler weekly_summary
  python -m inquiry_bot.scheduler faq_update_check

crontab登録例:
  0 21 * * *  cd /path/to/project && python -m inquiry_bot.scheduler daily_report
  */5 * * * * cd /path/to/project && python -m inquiry_bot.scheduler health_check
  0 10 * * 1  cd /path/to/project && python -m inquiry_bot.scheduler weekly_summary
"""

import sys
import logging
import os
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


def daily_report():
    """日次レポートを生成してLINE/Slackに送信."""
    logger.info("Starting daily report generation...")
    from inquiry_bot.analytics import InquiryAnalytics

    analytics = InquiryAnalytics()
    report = analytics.generate_daily_report()
    analytics.send_daily_report()

    logger.info("Daily report sent successfully")
    print(report)


def health_check():
    """ヘルスチェック — サーバーが動いているか確認."""
    import requests

    bot_url = os.getenv("INQUIRY_BOT_URL", "http://localhost:8080")
    try:
        resp = requests.get(f"{bot_url}/api/health", timeout=5)
        if resp.status_code == 200:
            logger.info("Health check OK: %s", resp.json())
        else:
            logger.error("Health check FAILED: status=%d", resp.status_code)
            _alert_down(f"Bot応答異常: HTTP {resp.status_code}")
    except requests.ConnectionError:
        logger.error("Health check FAILED: Connection refused")
        _alert_down("Bot接続不可: サーバーが停止している可能性あり")
    except requests.Timeout:
        logger.error("Health check FAILED: Timeout")
        _alert_down("Bot応答タイムアウト: 高負荷の可能性あり")


def weekly_summary():
    """週次サマリーを生成して送信."""
    logger.info("Starting weekly summary generation...")
    from inquiry_bot.analytics import InquiryAnalytics
    from core.notifier import Notifier

    analytics = InquiryAnalytics()
    report = analytics.generate_monthly_summary()  # 30日分を含む

    notifier = Notifier()
    notifier.notify(f"📊 週次サマリー\n{report}")

    logger.info("Weekly summary sent")
    print(report)


def faq_update_check():
    """FAQ更新チェック — よくある質問の見逃しパターンを検出.

    分析データからFAQに追加すべき質問パターンを提案する。
    """
    logger.info("Starting FAQ update check...")
    from inquiry_bot.analytics import InquiryAnalytics

    analytics = InquiryAnalytics()
    logs = analytics.load_logs(7)  # 直近7日

    if not logs:
        logger.info("No logs found for FAQ update check")
        return

    # 低信頼度（FAQマッチなし）の質問を抽出
    low_confidence = [
        entry for entry in logs
        if entry.get("confidence", 1.0) < 0.5 and not entry.get("escalated")
    ]

    if not low_confidence:
        logger.info("All inquiries matched FAQ well. No updates needed.")
        return

    # カテゴリ別に集計
    patterns = {}
    for entry in low_confidence:
        msg = entry.get("message", "")
        cat = entry.get("category", "unknown")
        key = f"{cat}: {msg[:50]}"
        patterns[key] = patterns.get(key, 0) + 1

    # 頻出パターン（2回以上）
    frequent = {k: v for k, v in patterns.items() if v >= 2}

    if frequent:
        alert = "📝 FAQ更新提案（直近7日の低信頼度質問）:\n"
        for pattern, count in sorted(frequent.items(), key=lambda x: x[1], reverse=True)[:10]:
            alert += f"  - {pattern} ({count}回)\n"
        alert += "\n→ faq_data.yaml にこれらのパターンを追加することを推奨"

        from core.notifier import Notifier
        notifier = Notifier()
        notifier.notify(alert)
        print(alert)
    else:
        logger.info("No frequent low-confidence patterns found")


def results_to_x():
    """Bot運用実績からX投稿案を生成（System D連携）."""
    logger.info("Generating X post drafts from bot results...")
    from inquiry_bot.results_to_x import generate_bot_results_posts

    posts = generate_bot_results_posts()
    if posts:
        for i, post in enumerate(posts, 1):
            print(f"\n--- 投稿案 {i} ---")
            print(post["draft"])
    else:
        print("投稿データなし（運用データの蓄積を待ってください）")


def auto_restart():
    """サーバー自動再起動（ヘルスチェック失敗時に呼ばれる）."""
    logger.warning("Attempting auto-restart of inquiry bot server...")
    import subprocess

    # systemd管理の場合
    try:
        subprocess.run(
            ["systemctl", "--user", "restart", "inquiry-bot"],
            check=True, timeout=30,
        )
        logger.info("Server restarted via systemd")
        return
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Docker管理の場合
    try:
        subprocess.run(
            ["docker", "compose", "-f", "inquiry_bot/docker-compose.yaml",
             "restart", "inquiry-bot"],
            check=True, timeout=60,
        )
        logger.info("Server restarted via docker compose")
        return
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    logger.error("Auto-restart failed. Manual intervention required.")
    _alert_down("自動再起動に失敗しました。手動で確認してください。")


def _alert_down(message: str):
    """サーバーダウン通知."""
    try:
        from core.notifier import Notifier
        notifier = Notifier()
        notifier.notify(f"🚨 問い合わせBot異常検知\n{message}\n"
                       f"時刻: {datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.error("Failed to send alert: %s", e)


TASKS = {
    "daily_report": daily_report,
    "health_check": health_check,
    "weekly_summary": weekly_summary,
    "faq_update_check": faq_update_check,
    "results_to_x": results_to_x,
    "auto_restart": auto_restart,
}


def main():
    if len(sys.argv) < 2:
        print("使い方: python -m inquiry_bot.scheduler <task>")
        print(f"利用可能なタスク: {', '.join(TASKS.keys())}")
        sys.exit(1)

    task_name = sys.argv[1]
    if task_name not in TASKS:
        print(f"不明なタスク: {task_name}")
        print(f"利用可能: {', '.join(TASKS.keys())}")
        sys.exit(1)

    logger.info("Running scheduled task: %s", task_name)
    try:
        TASKS[task_name]()
        logger.info("Task %s completed successfully", task_name)
    except Exception as e:
        logger.error("Task %s failed: %s", task_name, e, exc_info=True)
        _alert_down(f"定期タスク「{task_name}」が失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
