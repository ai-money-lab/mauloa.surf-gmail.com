"""問い合わせBot — LINE Webhook + Web Chat 統合サーバー.

起動方法:
  uvicorn inquiry_bot.server:app --host 0.0.0.0 --port 8080 --reload

本番:
  uvicorn inquiry_bot.server:app --host 0.0.0.0 --port 8080 --workers 2
"""

import logging
import os
import threading
from pathlib import Path

import yaml
from fastapi import FastAPI, Request, Response, BackgroundTasks

from inquiry_bot.bot_engine import BotEngine
from inquiry_bot.line_handler import LineHandler
from inquiry_bot.web_chat_handler import create_app as create_web_app

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def create_server() -> FastAPI:
    """LINE + Web統合サーバーを作成."""
    yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    # 共有BotEngine（LINE/Web両方で同じインスタンスを使用）
    bot_engine = BotEngine()

    # Web Chat API（メインアプリ）
    app = create_web_app(bot_engine)

    # LINE Handler
    line_handler = LineHandler(bot_engine)

    @app.post("/webhook/line")
    async def line_webhook(request: Request):
        """LINE Messaging API Webhook エンドポイント."""
        body = await request.body()
        body_str = body.decode("utf-8")
        signature = request.headers.get("X-Line-Signature", "")

        result = line_handler.handle_webhook(body_str, signature)

        status_code = result.get("status", 200)
        return Response(status_code=status_code)

    # ═══ 自動化トリガーAPI ═══
    # cron-job.org（無料）からHTTPで呼び出してSystem A/Cを実行
    TRIGGER_SECRET = os.getenv("TRIGGER_SECRET", "hiroki-auto-2026")

    def _check_trigger_auth(request: Request) -> bool:
        """Verify trigger request is authorized."""
        token = request.headers.get("X-Trigger-Secret", "")
        if not token:
            token = request.query_params.get("secret", "")
        return token == TRIGGER_SECRET

    @app.post("/api/trigger/daily-post")
    async def trigger_daily_post(request: Request, background_tasks: BackgroundTasks):
        """System A: 投稿生成→品質チェック→画像→X投稿（1日1回 18:30 JST）"""
        if not _check_trigger_auth(request):
            return Response(status_code=403, content="Forbidden")

        def run_pipeline():
            try:
                from system_a.daily_pipeline import DailyPipeline
                logging.basicConfig(level=logging.INFO)
                pipeline = DailyPipeline()
                pipeline.run()
            except Exception as e:
                logger.error("Daily post pipeline failed: %s", e)

        background_tasks.add_task(run_pipeline)
        return {"status": "started", "task": "daily-post"}

    @app.post("/api/trigger/daily-analysis")
    async def trigger_daily_analysis(request: Request, background_tasks: BackgroundTasks):
        """System A: パフォーマンス分析→LINE通知（1日1回 21:00 JST）"""
        if not _check_trigger_auth(request):
            return Response(status_code=403, content="Forbidden")

        def run_analysis():
            try:
                from system_a.analyze_performance import PerformanceAnalyzer
                logging.basicConfig(level=logging.INFO)
                analyzer = PerformanceAnalyzer()
                analyzer.run_daily()
            except Exception as e:
                logger.error("Daily analysis failed: %s", e)

        background_tasks.add_task(run_analysis)
        return {"status": "started", "task": "daily-analysis"}

    @app.post("/api/trigger/daily-collect")
    async def trigger_daily_collect(request: Request, background_tasks: BackgroundTasks):
        """System C: 日次情報収集（1日1回 07:00 JST）"""
        if not _check_trigger_auth(request):
            return Response(status_code=403, content="Forbidden")

        def run_collection():
            try:
                from system_c.scheduler import SystemCScheduler
                logging.basicConfig(level=logging.INFO)
                scheduler = SystemCScheduler()
                scheduler.run_daily_watch()
            except Exception as e:
                logger.error("Daily data collection failed: %s", e)

        background_tasks.add_task(run_collection)
        return {"status": "started", "task": "daily-collect"}

    @app.get("/")
    async def root():
        return {
            "service": "ROCKEDGE 問い合わせ自動対応Bot",
            "version": "2.0.0",
            "endpoints": {
                "chat_api": "/api/chat",
                "line_webhook": "/webhook/line",
                "widget_demo": "/chat",
                "health": "/api/health",
                "analytics": "/api/analytics",
                "widget_config": "/api/widget-config",
                "trigger_daily_post": "POST /api/trigger/daily-post",
                "trigger_daily_analysis": "POST /api/trigger/daily-analysis",
                "trigger_daily_collect": "POST /api/trigger/daily-collect",
            },
        }

    return app


app = create_server()
