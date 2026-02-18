"""問い合わせBot — LINE Webhook + Web Chat 統合サーバー.

起動方法:
  uvicorn inquiry_bot.server:app --host 0.0.0.0 --port 8080 --reload

本番:
  uvicorn inquiry_bot.server:app --host 0.0.0.0 --port 8080 --workers 2
"""

import logging
from pathlib import Path

import yaml
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from inquiry_bot.bot_engine import BotEngine
from inquiry_bot.line_handler import LineHandler
from inquiry_bot.web_chat_handler import create_app as create_web_app

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def create_server() -> FastAPI:
    """LINE + Web統合サーバーを作成."""
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

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

    @app.get("/")
    async def root():
        return {
            "service": "ROCKEDGE 問い合わせ自動対応Bot",
            "version": "1.0.0",
            "endpoints": {
                "chat_api": "/api/chat",
                "line_webhook": "/webhook/line",
                "widget_demo": "/chat",
                "health": "/api/health",
                "analytics": "/api/analytics",
                "widget_config": "/api/widget-config",
            },
        }

    return app


app = create_server()
