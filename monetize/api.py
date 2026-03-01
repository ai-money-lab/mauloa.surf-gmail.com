"""Monetize API — セルフサービス型ストアフロント REST API."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from monetize.order_handler import OrderHandler
from monetize.pricing_engine import PricingEngine
from monetize.revenue_tracker import RevenueTracker

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
DELIVERABLES_DIR = BASE_DIR / "data" / "monetize" / "deliverables"


# ─── リクエスト/レスポンスモデル ───

class GenerateRequest(BaseModel):
    """即時生成リクエスト."""
    product_id: str
    prompt: str
    customer_id: str = ""
    model: Optional[str] = None
    size: Optional[str] = None
    aspect_ratio: Optional[str] = None


class SubscriptionRequest(BaseModel):
    """サブスクリプション開始リクエスト."""
    customer_id: str
    subscription_id: str


class OrderStatusRequest(BaseModel):
    """注文ステータス照会."""
    order_id: str


# ─── アプリ生成 ───

def create_monetize_app() -> FastAPI:
    """マネタイズAPIアプリケーションを生成."""

    app = FastAPI(
        title="AI Asset Marketplace API",
        description="AI画像・コンテンツの自動生成・販売API",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    handler = OrderHandler()
    pricing = PricingEngine()
    tracker = RevenueTracker()

    # ═══ 商品カタログ ═══

    @app.get("/api/store/products")
    async def list_products():
        """販売中の全商品一覧を返す."""
        return {"products": pricing.get_all_products_summary()}

    @app.get("/api/store/products/{product_id}")
    async def get_product(product_id: str):
        """商品詳細を返す."""
        product = pricing.get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="商品が見つかりません")
        cost = pricing.calculate_generation_cost(product_id)
        return {"product": product, "cost_info": cost}

    @app.get("/api/store/products/{product_id}/estimate")
    async def estimate_cost(
        product_id: str,
        model: Optional[str] = None,
        size: Optional[str] = None,
        count: Optional[int] = None,
    ):
        """生成コストの見積もりを返す."""
        try:
            cost = pricing.calculate_generation_cost(product_id, model, size, count)
            return {"estimate": cost}
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    # ═══ 即時生成（注文→生成→納品を一括） ═══

    @app.post("/api/store/generate")
    async def generate(req: GenerateRequest):
        """即時商品を注文・生成・納品する（ワンショット）.

        支払い完了後に呼ぶ想定。
        本番ではStripe webhook → この endpoint の順で呼ぶ。
        """
        options = {}
        if req.model:
            options["model"] = req.model
        if req.size:
            options["size"] = req.size
        if req.aspect_ratio:
            options["aspect_ratio"] = req.aspect_ratio

        result = handler.process_instant_order(
            product_id=req.product_id,
            prompt=req.prompt,
            customer_id=req.customer_id,
            options=options,
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    # ═══ 注文管理 ═══

    @app.get("/api/store/orders/{order_id}")
    async def get_order(order_id: str):
        """注文ステータスを取得."""
        order = handler.get_order_status(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="注文が見つかりません")
        return {"order": order}

    @app.get("/api/store/orders")
    async def list_orders(
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ):
        """注文一覧を取得."""
        orders = handler.list_orders(customer_id, status, limit)
        return {"orders": orders, "count": len(orders)}

    # ═══ ダウンロード ═══

    @app.get("/api/store/download/{order_id}")
    async def download(order_id: str):
        """納品物をダウンロード.

        ZIPがあればZIP、なければ最初のファイルを返す。
        """
        order = handler.get_order_status(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="注文が見つかりません")
        if order.get("status") != "delivered":
            raise HTTPException(status_code=400, detail="まだ納品されていません")

        files = order.get("files", [])
        if not files:
            raise HTTPException(status_code=404, detail="納品ファイルがありません")

        # ZIPを優先
        for f in files:
            if f.endswith(".zip"):
                return FileResponse(f, filename=f"{order_id}.zip")

        # 単体ファイル
        first_file = Path(files[0])
        if first_file.exists():
            return FileResponse(str(first_file), filename=first_file.name)

        raise HTTPException(status_code=404, detail="ファイルが見つかりません")

    # ═══ サブスクリプション ═══

    @app.post("/api/store/subscribe")
    async def subscribe(req: SubscriptionRequest):
        """サブスクリプションを開始."""
        product = pricing.subscription_products.get(req.subscription_id)
        if not product:
            raise HTTPException(status_code=404, detail="プランが見つかりません")

        tracker.record_subscription(
            customer_id=req.customer_id,
            subscription_id=req.subscription_id,
            price_jpy=product["price_jpy_monthly"],
        )

        return {
            "status": "active",
            "customer_id": req.customer_id,
            "plan": product["name"],
            "price_jpy_monthly": product["price_jpy_monthly"],
        }

    # ═══ 収益ダッシュボード（管理者用） ═══

    @app.get("/api/admin/revenue/daily")
    async def daily_revenue(date: str = ""):
        """日次売上サマリー."""
        return tracker.get_daily_summary(date)

    @app.get("/api/admin/revenue/monthly")
    async def monthly_revenue(month: str = ""):
        """月次売上サマリー."""
        return tracker.get_monthly_summary(month)

    @app.get("/api/admin/revenue/pl")
    async def pl_report(month: str = ""):
        """P&Lレポート（テキスト形式）."""
        return {"report": tracker.get_pl_report(month)}

    # ═══ ヘルスチェック ═══

    @app.get("/api/store/health")
    async def health():
        """ヘルスチェック."""
        return {"status": "ok", "service": "monetize-engine"}

    return app


# uvicorn 起動用
app = create_monetize_app()
