"""Web Chat API Handler — FastAPIベースのWebチャットAPIサーバー."""

import logging
import re
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
PROPERTIES_PATH = Path(__file__).parent / "properties.yaml"
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


class PropertyRegistration(BaseModel):
    """物件登録リクエスト."""
    name: str
    address: str = ""
    building_type: str = "マンション"
    structure: str = "RC造"
    floor: str = ""
    built_year: Optional[int] = None
    layout: str = "1K"
    area_sqm: Optional[float] = None
    rent: Optional[int] = None
    management_fee: Optional[int] = 0
    deposit: str = ""
    key_money: str = ""
    brokerage_fee: str = ""
    vacancy_status: str = "空室あり"
    available_date: str = "即入居可"
    nearest_station: str = ""
    walk_minutes: Optional[int] = None
    pet_policy: str = "ペット不可"
    parking_info: str = ""
    facility_list: str = ""
    matterport_url: str = ""
    notes: str = ""


def _save_properties_yaml(property_data: dict) -> None:
    """物件データをYAMLファイルに保存."""
    try:
        full = yaml.safe_load(PROPERTIES_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        full = {}
    full["properties"] = property_data
    PROPERTIES_PATH.write_text(
        yaml.dump(full, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )


def _build_property_card(pid: str, info: dict) -> PropertyCard:
    """物件データからPropertyCardを構築."""
    rent = info.get("rent", 0)
    rent_str = f"{rent:,}円" if isinstance(rent, (int, float)) else str(rent)
    mgmt = info.get("management_fee", 0)
    if mgmt:
        rent_str += f"（管理費 {mgmt:,}円）"

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

    return PropertyCard(
        id=pid,
        name=info.get("name", pid),
        rent=rent_str,
        layout=info.get("layout", ""),
        area=f"{info.get('area_sqm', '')}㎡",
        station=info.get("nearest_station", ""),
        walk_minutes=info.get("walk_minutes", 0),
        pet=info.get("pet_policy", ""),
        status=info.get("vacancy_status", ""),
        features=features[:4],
    )


def _get_available_property_cards(property_data: dict) -> List[PropertyCard]:
    """空室ありの全物件をカードとして返す."""
    if not property_data:
        return []
    cards = []
    for pid, info in property_data.items():
        status = info.get("vacancy_status", "")
        if "空室" in status:
            cards.append(_build_property_card(pid, info))
    return cards


def _clean_reply_for_cards(reply_text: str, card_names: List[str]) -> str:
    """物件カード表示時に回答テキストから冗長な物件リスト部分を除去."""
    lines = reply_text.split("\n")
    result_lines = []
    in_listing = False

    for line in lines:
        stripped = line.strip()

        # 物件リストヘッダー検出（例: 【現在空室の物件】）
        if "【" in stripped and ("物件" in stripped or "空室" in stripped):
            in_listing = True
            continue

        # 物件名が含まれる行
        if any(name in stripped for name in card_names):
            in_listing = True
            continue

        # リスト内の詳細行をスキップ
        if in_listing:
            detail_keywords = [
                "賃料", "管理費", "間取", "㎡", "最寄", "徒歩",
                "入居", "敷金", "礼金", "号室", "階建",
            ]
            if stripped.startswith(("・", "- ", "　", "  ")):
                continue
            if any(kw in stripped for kw in detail_keywords):
                continue
            if stripped == "":
                continue
            # 物件選択を促す文もスキップ
            if any(kw in stripped for kw in [
                "どちら", "どの物件", "ご希望", "お選び", "気になる",
            ]):
                continue
            in_listing = False

        result_lines.append(line)

    text = "\n".join(result_lines).strip()

    # 末尾の物件選択促進文を除去
    text = re.sub(
        r"\n*(?:どちら|どの|ご希望の|気になる).*?(?:でしょうか|ですか|ください)[。？?]*\s*$",
        "", text,
    ).strip()

    if not text:
        text = "空室物件をご案内いたします。"

    text += "\n\n気になる物件をタップしてください。"
    return text


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

        # 物件カード: カテゴリがvacancyの場合は常に空室物件カードを表示
        reply_text = response["reply"]
        category = response.get("category", "general")
        property_cards: List[PropertyCard] = []

        if category == "vacancy" and bot.kb.property_data:
            property_cards = _get_available_property_cards(bot.kb.property_data)

        # 物件カードがある場合: テキスト内の物件リスト部分を除去
        if property_cards:
            card_names = [c.name for c in property_cards]
            reply_text = _clean_reply_for_cards(reply_text, card_names)
            # 物件カード表示時は物件選択を促す選択肢は不要
            options = []

        # 全カテゴリでフォールバック選択肢を保証（入力不要を徹底）
        if not options and not property_cards:
            options = ["空室を確認したい", "内見を予約したい", "その他の質問"]

        return ChatResponse(
            reply=reply_text,
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

    # ═══ 物件管理API ═══

    @app.get("/api/properties")
    async def list_properties():
        """登録済み物件一覧を返す."""
        return {"properties": bot.kb.property_data}

    @app.post("/api/properties")
    async def register_property(req: PropertyRegistration):
        """新規物件を登録."""
        # IDを生成（物件名からスラグ化）
        pid = re.sub(r"[^\w]", "_", req.name).lower().strip("_")
        if not pid:
            pid = f"property_{uuid.uuid4().hex[:8]}"

        total_monthly = (req.rent or 0) + (req.management_fee or 0)
        data = {
            "name": req.name,
            "address": req.address,
            "building_type": req.building_type,
            "structure": req.structure,
            "floor": req.floor,
            "built_year": req.built_year,
            "layout": req.layout,
            "area_sqm": req.area_sqm,
            "rent": req.rent,
            "management_fee": req.management_fee,
            "total_monthly": total_monthly,
            "deposit": req.deposit,
            "key_money": req.key_money,
            "brokerage_fee": req.brokerage_fee,
            "vacancy_status": req.vacancy_status,
            "available_date": req.available_date,
            "nearest_station": req.nearest_station,
            "walk_minutes": req.walk_minutes,
            "pet_policy": req.pet_policy,
            "parking_info": req.parking_info,
            "facility_list": req.facility_list,
            "matterport_url": req.matterport_url,
            "notes": req.notes,
        }

        # メモリに追加
        bot.kb.property_data[pid] = data

        # YAMLに保存
        _save_properties_yaml(bot.kb.property_data)

        # システムプロンプトを再構築
        bot.system_prompt = bot._build_system_prompt()

        logger.info("Property registered: %s (%s)", req.name, pid)
        return {"status": "ok", "property_id": pid, "name": req.name}

    @app.delete("/api/properties/{property_id}")
    async def delete_property(property_id: str):
        """物件を削除."""
        if property_id not in bot.kb.property_data:
            raise HTTPException(status_code=404, detail="Property not found")
        del bot.kb.property_data[property_id]
        _save_properties_yaml(bot.kb.property_data)
        bot.system_prompt = bot._build_system_prompt()
        return {"status": "ok"}

    # ═══ ページ ═══

    _no_cache = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}

    @app.get("/chat", response_class=HTMLResponse)
    async def chat_demo():
        """デモ用チャットページ."""
        html_path = WIDGET_DIR / "index.html"
        if html_path.exists():
            return HTMLResponse(html_path.read_text(encoding="utf-8"), headers=_no_cache)
        return HTMLResponse("<h1>Widget not found</h1>", status_code=404)

    @app.get("/admin/properties", response_class=HTMLResponse)
    async def admin_properties():
        """物件管理ページ."""
        html_path = WIDGET_DIR / "admin_properties.html"
        if html_path.exists():
            return HTMLResponse(html_path.read_text(encoding="utf-8"), headers=_no_cache)
        return HTMLResponse("<h1>Admin page not found</h1>", status_code=404)

    # 静的ファイル（ウィジェット）— ルート定義の後にマウント
    if WIDGET_DIR.exists():
        app.mount("/widget", StaticFiles(directory=str(WIDGET_DIR)), name="widget")

    return app


# uvicorn起動用
app = create_app()
