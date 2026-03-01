"""Pricing Engine — コスト計算・利益率管理・動的プライシング."""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
CATALOG_PATH = Path(__file__).parent / "catalog.yaml"
COSTS_LOG_DIR = Path(__file__).parent.parent / "data" / "system_e" / "costs"

# nano-banana の実コスト（USD → JPY換算レート）
USD_TO_JPY = 150

# Gemini API コスト (per 1000 images)
NANO_BANANA_COSTS = {
    "flash": {
        "512": 0.0335,
        "1K": 0.067,
        "2K": 0.134,
        "4K": 0.268,
    },
    "pro": {
        "512": 0.067,
        "1K": 0.134,
        "2K": 0.268,
        "4K": 0.536,
    },
}

# Claude API コスト (per 1K tokens, USD)
CLAUDE_COSTS = {
    "input_per_1k": 0.003,
    "output_per_1k": 0.015,
    "avg_tokens_per_post": 500,
    "avg_tokens_per_report_page": 2000,
}


class PricingEngine:
    """商品価格・コスト・利益率を管理."""

    def __init__(self):
        self._load_catalog()
        COSTS_LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _load_catalog(self):
        with open(CATALOG_PATH, encoding="utf-8") as f:
            self.catalog = yaml.safe_load(f)

        self.instant_products = {
            p["id"]: p for p in self.catalog.get("instant_products", [])
        }
        self.subscription_products = {
            p["id"]: p for p in self.catalog.get("subscription_products", [])
        }
        self.api_pricing = self.catalog.get("api_pricing", {})

    def get_product(self, product_id: str) -> Optional[dict]:
        """商品情報を取得."""
        return (
            self.instant_products.get(product_id)
            or self.subscription_products.get(product_id)
        )

    def calculate_generation_cost(
        self,
        product_id: str,
        model: Optional[str] = None,
        size: Optional[str] = None,
        count: Optional[int] = None,
    ) -> dict:
        """実際の生成コストを計算.

        Returns:
            {
                "image_cost_usd": float,
                "text_cost_usd": float,
                "total_cost_usd": float,
                "total_cost_jpy": int,
                "price_jpy": int,
                "margin_jpy": int,
                "margin_pct": float,
            }
        """
        product = self.get_product(product_id)
        if not product:
            raise ValueError(f"Unknown product: {product_id}")

        gen = product.get("generation", {})
        gen_type = gen.get("type", "image")
        use_model = model or gen.get("default_model", "flash")
        use_size = size or gen.get("default_size", "1K")
        use_count = count or gen.get("count", 1)

        image_cost_usd = 0.0
        text_cost_usd = 0.0

        # 画像コスト
        if gen_type in ("image", "image_pack", "image_transparent"):
            cost_per_image = NANO_BANANA_COSTS.get(use_model, {}).get(use_size, 0.067)
            image_cost_usd = cost_per_image * use_count
        elif gen_type == "content_pack":
            img_count = gen.get("images", 5)
            cost_per_image = NANO_BANANA_COSTS.get(use_model, {}).get(use_size, 0.067)
            image_cost_usd = cost_per_image * img_count
            post_count = gen.get("posts", 5)
            tokens = CLAUDE_COSTS["avg_tokens_per_post"] * post_count
            text_cost_usd = (
                tokens / 1000 * CLAUDE_COSTS["input_per_1k"]
                + tokens / 1000 * CLAUDE_COSTS["output_per_1k"]
            )
        elif gen_type == "property_pack":
            img_count = gen.get("images", 5)
            cost_per_image = NANO_BANANA_COSTS.get(use_model, {}).get(use_size, 0.067)
            image_cost_usd = cost_per_image * img_count
            tokens = 3000  # copy + listing text
            text_cost_usd = (
                tokens / 1000 * CLAUDE_COSTS["input_per_1k"]
                + tokens / 1000 * CLAUDE_COSTS["output_per_1k"]
            )
        elif gen_type == "brand_kit":
            logo_count = gen.get("logos", 3)
            banner_count = gen.get("banners", 2)
            icon_count = gen.get("icons", 5)
            total_images = logo_count + banner_count + icon_count
            cost_per_image = NANO_BANANA_COSTS.get(use_model, {}).get(use_size, 0.134)
            image_cost_usd = cost_per_image * total_images
            text_cost_usd = 0.02  # color palette prompt
        elif gen_type == "report":
            pages = gen.get("pages", 5)
            tokens = CLAUDE_COSTS["avg_tokens_per_report_page"] * pages
            text_cost_usd = (
                tokens / 1000 * CLAUDE_COSTS["input_per_1k"]
                + tokens / 1000 * CLAUDE_COSTS["output_per_1k"]
            )

        total_cost_usd = image_cost_usd + text_cost_usd
        total_cost_jpy = int(total_cost_usd * USD_TO_JPY)

        # 売価
        price_jpy = product.get("price_jpy", 0)
        if not price_jpy:
            price_jpy = product.get("price_jpy_monthly", 0)

        margin_jpy = price_jpy - total_cost_jpy
        margin_pct = (margin_jpy / price_jpy * 100) if price_jpy > 0 else 0

        return {
            "product_id": product_id,
            "image_cost_usd": round(image_cost_usd, 4),
            "text_cost_usd": round(text_cost_usd, 4),
            "total_cost_usd": round(total_cost_usd, 4),
            "total_cost_jpy": total_cost_jpy,
            "price_jpy": price_jpy,
            "margin_jpy": margin_jpy,
            "margin_pct": round(margin_pct, 1),
        }

    def calculate_api_cost(self, call_type: str, model: str = "flash") -> int:
        """API従量課金のコスト（JPY）を計算."""
        pricing = self.api_pricing.get("image_generation", {})
        if call_type == "image":
            return pricing.get(f"{model}_per_call_jpy", 50)
        text_pricing = self.api_pricing.get("text_generation", {})
        if call_type == "post":
            return text_pricing.get("post_per_call_jpy", 30)
        if call_type == "report_page":
            return text_pricing.get("report_page_per_call_jpy", 100)
        return 0

    def check_subscription_usage(
        self, subscription_id: str, current_usage: dict
    ) -> dict:
        """サブスクリプションの利用状況を確認.

        Returns:
            {
                "within_limit": bool,
                "images_remaining": int,
                "posts_remaining": int,
                "overage_cost_jpy": int,
            }
        """
        product = self.subscription_products.get(subscription_id)
        if not product:
            return {"within_limit": False, "error": "Unknown subscription"}

        included = product.get("included", {})
        images_limit = included.get("images_per_month", 0)
        posts_limit = included.get("posts_per_month", 0)

        images_used = current_usage.get("images", 0)
        posts_used = current_usage.get("posts", 0)

        # -1 = unlimited
        if images_limit == -1:
            images_remaining = 999999
        else:
            images_remaining = max(0, images_limit - images_used)

        if posts_limit == -1:
            posts_remaining = 999999
        else:
            posts_remaining = max(0, posts_limit - posts_used)

        within_limit = images_remaining > 0 and posts_remaining > 0

        # 超過料金
        overage_images = max(0, images_used - images_limit) if images_limit != -1 else 0
        overage_per_image = product.get("overage_per_image_jpy", 0)
        overage_cost = overage_images * overage_per_image

        return {
            "within_limit": within_limit,
            "images_remaining": images_remaining,
            "posts_remaining": posts_remaining,
            "overage_images": overage_images,
            "overage_cost_jpy": overage_cost,
        }

    def log_cost(self, order_id: str, product_id: str, cost_data: dict) -> None:
        """コストをログに記録."""
        log_entry = {
            "timestamp": datetime.now(JST).isoformat(),
            "order_id": order_id,
            "product_id": product_id,
            **cost_data,
        }
        log_file = COSTS_LOG_DIR / f"{datetime.now(JST).strftime('%Y%m')}_costs.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    def get_all_products_summary(self) -> list:
        """全商品のサマリーを返す（ストアフロント用）."""
        products = []
        for p in self.catalog.get("instant_products", []):
            cost = self.calculate_generation_cost(p["id"])
            products.append({
                "id": p["id"],
                "name": p["name"],
                "description": p["description"],
                "price_jpy": p["price_jpy"],
                "type": "instant",
                "margin_pct": cost["margin_pct"],
            })
        for p in self.catalog.get("subscription_products", []):
            products.append({
                "id": p["id"],
                "name": p["name"],
                "description": p["description"],
                "price_jpy_monthly": p["price_jpy_monthly"],
                "type": "subscription",
            })
        return products
