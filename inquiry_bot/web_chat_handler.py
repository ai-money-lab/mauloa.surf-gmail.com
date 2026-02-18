"""Web Chat API Handler — FastAPIベースのWebチャットAPIサーバー."""

import logging
import uuid
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from inquiry_bot.bot_engine import BotEngine

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config.yaml"
WIDGET_DIR = Path(__file__).parent / "web_widget"


class ChatRequest(BaseModel):
    """チャットリクエスト."""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """チャットレスポンス."""
    reply: str
    session_id: str
    category: str = "general"
    escalated: bool = False


def create_app(bot_engine: Optional[BotEngine] = None) -> FastAPI:
    """FastAPIアプリケーションを生成."""
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    web_cfg = config.get("web_chat", {})

    app = FastAPI(
        title="ROCKEDGE 問い合わせBot API",
        description="不動産問い合わせ自動対応Bot Web Chat API",
        version="1.0.0",
    )

    # CORS設定
    cors_origins = web_cfg.get("cors_origins", ["http://localhost:3000"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Bot Engine初期化
    bot = bot_engine or BotEngine()

    # 静的ファイル（ウィジェット）
    if WIDGET_DIR.exists():
        app.mount("/widget", StaticFiles(directory=str(WIDGET_DIR)), name="widget")

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest):
        """チャットメッセージを送信して応答を取得."""
        if not req.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        session_id = req.session_id or f"web_{uuid.uuid4().hex[:12]}"

        response = bot.handle_message(
            user_message=req.message,
            session_id=session_id,
            channel="web",
            user_id=session_id,
        )

        return ChatResponse(
            reply=response["reply"],
            session_id=session_id,
            category=response.get("category", "general"),
            escalated=response.get("escalated", False),
        )

    @app.get("/api/widget-config")
    async def widget_config():
        """ウィジェットの設定を返す."""
        widget_cfg = web_cfg.get("widget", {})
        return JSONResponse({
            "title": widget_cfg.get("title", "AIアシスタント"),
            "subtitle": widget_cfg.get("subtitle", ""),
            "primaryColor": widget_cfg.get("primary_color", "#1a1a2e"),
            "accentColor": widget_cfg.get("accent_color", "#e94560"),
            "position": widget_cfg.get("position", "bottom-right"),
            "welcomeMessage": widget_cfg.get("welcome_message", "こんにちは！"),
        })

    @app.get("/api/health")
    async def health():
        """ヘルスチェック."""
        return {"status": "ok", "service": "inquiry-bot"}

    @app.get("/api/analytics")
    async def analytics():
        """分析データを取得（管理者用）."""
        return bot.get_analytics()

    @app.get("/chat", response_class=HTMLResponse)
    async def chat_demo():
        """デモ用チャットページ."""
        html_path = WIDGET_DIR / "index.html"
        if html_path.exists():
            return HTMLResponse(html_path.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>Widget not found</h1>", status_code=404)

    return app


# uvicorn起動用
app = create_app()
