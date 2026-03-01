"""Order Handler — 注文受付から生成・納品までの自動パイプライン."""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from core.notifier import Notifier
from monetize.pricing_engine import PricingEngine
from monetize.asset_generator import AssetGenerator

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
DELIVERABLES_DIR = BASE_DIR / "data" / "monetize" / "deliverables"
ORDERS_LOG_DIR = BASE_DIR / "data" / "monetize" / "orders"


class OrderHandler:
    """セルフサービス注文の受付・生成・納品を自動化."""

    def __init__(self):
        self.pricing = PricingEngine()
        self.generator = AssetGenerator()
        self.notifier = Notifier()
        DELIVERABLES_DIR.mkdir(parents=True, exist_ok=True)
        ORDERS_LOG_DIR.mkdir(parents=True, exist_ok=True)

    def create_order(
        self,
        product_id: str,
        prompt: str,
        customer_id: str = "",
        options: Optional[dict] = None,
    ) -> dict:
        """新規注文を作成.

        Args:
            product_id: 商品ID（catalog.yamlのid）
            prompt: ユーザーの生成プロンプト/要件
            customer_id: 顧客識別子（LINE ID, session ID等）
            options: 追加オプション（model, size, aspect_ratio等）

        Returns:
            {"order_id": str, "status": str, "product": dict, "cost": dict}
        """
        product = self.pricing.get_product(product_id)
        if not product:
            return {"error": f"商品が見つかりません: {product_id}"}

        order_id = self._generate_order_id()
        options = options or {}

        # コスト計算
        cost = self.pricing.calculate_generation_cost(
            product_id,
            model=options.get("model"),
            size=options.get("size"),
        )

        order = {
            "order_id": order_id,
            "product_id": product_id,
            "product_name": product["name"],
            "customer_id": customer_id,
            "prompt": prompt,
            "options": options,
            "price_jpy": cost["price_jpy"],
            "cost_jpy": cost["total_cost_jpy"],
            "margin_jpy": cost["margin_jpy"],
            "status": "pending",
            "created_at": datetime.now(JST).isoformat(),
        }

        self._log_order(order)
        return order

    def fulfill_order(self, order: dict) -> dict:
        """注文を実行して納品物を生成.

        Args:
            order: create_order() の戻り値

        Returns:
            {"order_id": str, "status": str, "files": list, "download_url": str}
        """
        order_id = order["order_id"]
        product_id = order["product_id"]
        prompt = order["prompt"]
        options = order.get("options", {})

        product = self.pricing.get_product(product_id)
        if not product:
            return {"order_id": order_id, "status": "error", "error": "商品不明"}

        gen = product.get("generation", {})
        gen_type = gen.get("type", "image")
        model = options.get("model", gen.get("default_model", "flash"))
        size = options.get("size", gen.get("default_size", "1K"))
        aspect_ratio = options.get("aspect_ratio", gen.get("aspect_ratio", "1:1"))

        output_dir = DELIVERABLES_DIR / order_id
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("[%s] 生成開始: %s (%s)", order_id, product["name"], gen_type)
        order["status"] = "processing"
        self._log_order(order)

        generated_files = []

        try:
            if gen_type == "image":
                path = self.generator.generate_image(
                    prompt=prompt,
                    output_dir=output_dir,
                    model=model,
                    size=size,
                    aspect_ratio=aspect_ratio,
                )
                if path:
                    generated_files.append(str(path))

            elif gen_type in ("image_pack", "image_transparent"):
                count = gen.get("count", 5)
                transparent = gen.get("transparent", False) or gen_type == "image_transparent"
                paths = self.generator.generate_image_pack(
                    base_prompt=prompt,
                    count=count,
                    output_dir=output_dir,
                    model=model,
                    size=size,
                    aspect_ratio=aspect_ratio,
                    transparent=transparent,
                )
                generated_files = [str(p) for p in paths]

            elif gen_type == "content_pack":
                # 画像生成
                img_count = gen.get("images", 5)
                paths = self.generator.generate_image_pack(
                    base_prompt=prompt,
                    count=img_count,
                    output_dir=output_dir / "images",
                    model=model,
                    size=size,
                    aspect_ratio=aspect_ratio,
                )
                generated_files = [str(p) for p in paths]

                # テキスト生成
                post_count = gen.get("posts", 5)
                posts = self.generator.generate_text_content(
                    content_type="sns_post",
                    topic=prompt,
                    count=post_count,
                )
                posts_path = output_dir / "posts.json"
                posts_path.write_text(
                    json.dumps(posts, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                generated_files.append(str(posts_path))

            elif gen_type == "property_pack":
                # 物件マーケティング素材
                img_count = gen.get("images", 5)
                paths = self.generator.generate_image_pack(
                    base_prompt=f"不動産広告写真, {prompt}",
                    count=img_count,
                    output_dir=output_dir / "images",
                    model=model,
                    size=size,
                    aspect_ratio=aspect_ratio,
                )
                generated_files = [str(p) for p in paths]

                # キャッチコピー + 紹介文
                copies = self.generator.generate_text_content(
                    content_type="copy", topic=prompt, count=3,
                )
                listing = self.generator.generate_text_content(
                    content_type="listing", topic=prompt, count=1,
                )
                text_path = output_dir / "marketing_text.json"
                text_path.write_text(
                    json.dumps({"copies": copies, "listing": listing}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                generated_files.append(str(text_path))

            elif gen_type == "brand_kit":
                result = self.generator.generate_brand_kit(
                    brand_info=prompt,
                    output_dir=output_dir,
                    model=model,
                    size=size,
                )
                for key in ("logos", "banners", "icons"):
                    generated_files.extend(str(p) for p in result.get(key, []))
                # パレット情報
                palette_path = output_dir / "brand_palette.json"
                if palette_path.exists():
                    generated_files.append(str(palette_path))

            elif gen_type == "report":
                pages = gen.get("pages", 5)
                self.generator.generate_report(
                    topic=prompt, pages=pages, output_dir=output_dir,
                )
                report_path = output_dir / "report.md"
                if report_path.exists():
                    generated_files.append(str(report_path))

            else:
                logger.error("Unknown generation type: %s", gen_type)
                order["status"] = "error"
                self._log_order(order)
                return {"order_id": order_id, "status": "error", "error": f"不明な生成タイプ: {gen_type}"}

        except Exception as e:
            logger.error("[%s] 生成エラー: %s", order_id, e)
            order["status"] = "error"
            order["error"] = str(e)
            self._log_order(order)
            return {"order_id": order_id, "status": "error", "error": str(e)}

        # ZIPパッケージング
        zip_path = None
        if len(generated_files) > 1:
            zip_path = self.generator.package_deliverables(order_id, output_dir)
            generated_files.append(str(zip_path))

        # コスト記録
        cost_data = self.pricing.calculate_generation_cost(product_id, model=model, size=size)
        self.pricing.log_cost(order_id, product_id, cost_data)

        # 注文完了
        order["status"] = "delivered"
        order["files"] = generated_files
        order["delivered_at"] = datetime.now(JST).isoformat()
        self._log_order(order)

        # 通知
        self.notifier.send_line(
            f"💰 マネタイズエンジン納品完了\n"
            f"注文: {order_id}\n"
            f"商品: {product['name']}\n"
            f"売上: ¥{cost_data['price_jpy']:,}\n"
            f"原価: ¥{cost_data['total_cost_jpy']:,}\n"
            f"利益: ¥{cost_data['margin_jpy']:,} ({cost_data['margin_pct']}%)"
        )

        logger.info(
            "[%s] 納品完了: %d件のファイル, 売上¥%s, 利益¥%s",
            order_id, len(generated_files),
            f"{cost_data['price_jpy']:,}", f"{cost_data['margin_jpy']:,}",
        )

        return {
            "order_id": order_id,
            "status": "delivered",
            "files": generated_files,
            "file_count": len(generated_files),
            "price_jpy": cost_data["price_jpy"],
            "margin_jpy": cost_data["margin_jpy"],
        }

    def process_instant_order(
        self,
        product_id: str,
        prompt: str,
        customer_id: str = "",
        options: Optional[dict] = None,
    ) -> dict:
        """即時商品のワンショット処理（注文作成→生成→納品を一括実行）."""
        order = self.create_order(product_id, prompt, customer_id, options)
        if "error" in order:
            return order
        return self.fulfill_order(order)

    def get_order_status(self, order_id: str) -> Optional[dict]:
        """注文ステータスを取得."""
        order_file = ORDERS_LOG_DIR / f"{order_id}.json"
        if not order_file.exists():
            return None
        return json.loads(order_file.read_text(encoding="utf-8"))

    def list_orders(
        self,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """注文一覧を取得."""
        orders = []
        for f in sorted(ORDERS_LOG_DIR.glob("ORD-*.json"), reverse=True):
            try:
                order = json.loads(f.read_text(encoding="utf-8"))
                if customer_id and order.get("customer_id") != customer_id:
                    continue
                if status and order.get("status") != status:
                    continue
                orders.append(order)
                if len(orders) >= limit:
                    break
            except Exception:
                continue
        return orders

    def _generate_order_id(self) -> str:
        now = datetime.now(JST)
        short_uuid = uuid.uuid4().hex[:6].upper()
        return f"ORD-{now.strftime('%Y%m%d')}-{short_uuid}"

    def _log_order(self, order: dict) -> None:
        """注文データをJSONファイルに保存."""
        order_file = ORDERS_LOG_DIR / f"{order['order_id']}.json"
        order_file.write_text(
            json.dumps(order, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 月次ログにも追記
        monthly_log = ORDERS_LOG_DIR / f"{datetime.now(JST).strftime('%Y%m')}_orders.jsonl"
        with open(monthly_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(order, ensure_ascii=False) + "\n")
