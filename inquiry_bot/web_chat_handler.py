"""Web Chat API Handler — FastAPIベースのWebチャットAPIサーバー."""

import logging
import uuid
from pathlib import Path
from typing import List, Optional

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


class PropertyCard(BaseModel):
    """物件カード情報."""
    id: str
    name: str
    rent: str
    layout: str
    area: str
    station: str
    walk_minutes: int = 0
    pet: str = ""
    status: str = ""
    features: List[str] = []


class ChatResponse(BaseModel):
    """チャットレスポンス."""
    reply: str
    session_id: str
    category: str = "general"
    escalated: bool = False
    options: List[str] = []
    property_cards: List[PropertyCard] = []


class FeedbackRequest(BaseModel):
    """フィードバックリクエスト."""
    session_id: str
    type: str  # "positive" or "negative"
    message_index: int = 0


def _extract_property_cards(
    reply_text: str, property_data: dict,
) -> List[PropertyCard]:
    """回答テキストから物件名を検出し、該当する物件カードを生成."""
    if not property_data:
        return []

    cards: List[PropertyCard] = []
    for pid, info in property_data.items():
        name = info.get("name", "")
        if not name:
            continue
        # 物件名(またはその主要部分)が回答テキストに含まれているか
        if name in reply_text or pid in reply_text:
            rent = info.get("rent", 0)
            rent_str = f"{rent:,}円" if isinstance(rent, (int, float)) else str(rent)
            mgmt = info.get("management_fee", 0)
            if mgmt:
                rent_str += f"（管理費 {mgmt:,}円）"

            # 主要特徴を抽出
            features = []
            if info.get("available_date"):
                features.append(info["available_date"])
            if info.get("pet_policy") and "不可" not in str(info["pet_policy"]):
                features.append("ペット可")
            if info.get("facility_list"):
                fac = str(info["facility_list"])
                if "インターネット無料" in fac:
                    features.append("ネット無料")
                if "オートロック" in fac:
                    features.append("オートロック")
                if "宅配ボックス" in fac:
                    features.append("宅配BOX")

            cards.append(PropertyCard(
                id=pid,
                name=name,
                rent=rent_str,
                layout=info.get("layout", ""),
                area=f"{info.get('area_sqm', '')}㎡",
                station=info.get("nearest_station", ""),
                walk_minutes=info.get("walk_minutes", 0),
                pet=info.get("pet_policy", ""),
                status=info.get("vacancy_status", ""),
                features=features[:4],
            ))

    return cards


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

        # suggested_actionsからタップ可能な選択肢を生成
        options = response.get("suggested_actions") or []
        # カテゴリベースのフォールバック選択肢
        if not options:
            cat = response.get("category", "")
            if cat == "vacancy":
                options = ["内見を予約したい", "他の空室を見たい", "初期費用を教えて"]
            elif cat == "viewing":
                options = ["3Dツアーを見たい", "今週末に内見したい", "他の物件も見たい"]
            elif cat in ("rent_inquiry", "cost"):
                options = ["内見を予約したい", "空室を確認したい", "設備を教えて"]
            elif cat == "facility":
                options = ["内見を予約したい", "賃料を教えて", "空室を確認したい"]
            elif cat == "maintenance":
                options = ["担当者と話したい", "他の問い合わせ"]

        # 物件カード: 回答テキストに物件名が含まれている場合にカードデータを付与
        property_cards = _extract_property_cards(
            response.get("reply", ""), bot.kb.property_data,
        )

        return ChatResponse(
            reply=response["reply"],
            session_id=session_id,
            category=response.get("category", "general"),
            escalated=response.get("escalated", False),
            options=options[:5],
            property_cards=property_cards,
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

    @app.get("/api/report/daily")
    async def daily_report():
        """日次レポートを取得."""
        return {"report": bot.analytics.generate_daily_report()}

    @app.get("/api/report/monthly")
    async def monthly_report():
        """月次サマリーを取得（Coconala出品用の実績データ）."""
        return {"report": bot.analytics.generate_monthly_summary()}

    @app.post("/api/feedback")
    async def feedback(req: FeedbackRequest):
        """チャット回答へのフィードバックを記録."""
        logger.info(
            "Feedback received: session=%s type=%s msg_index=%d",
            req.session_id, req.type, req.message_index,
        )
        try:
            bot.analytics.record_feedback(
                session_id=req.session_id,
                feedback_type=req.type,
                message_index=req.message_index,
            )
        except AttributeError:
            # analytics にrecord_feedbackが未実装の場合はログのみ
            pass
        return {"status": "ok"}

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
