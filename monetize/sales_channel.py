"""Sales Channel — inquiry_bot との連携で商品を自動販売.

inquiry_bot のチャットから「画像を作りたい」「コンテンツパックが欲しい」等の
購買意図を検出し、商品提案→注文→納品までを会話内で完結させる。
"""

import logging
from typing import Optional

from monetize.pricing_engine import PricingEngine
from monetize.order_handler import OrderHandler

logger = logging.getLogger(__name__)


# 購買意図を検出するキーワード
PURCHASE_INTENT_KEYWORDS = [
    "画像を作", "画像生成", "画像ほしい", "画像欲しい",
    "イラスト", "ロゴ", "バナー", "アイコン",
    "コンテンツパック", "SNS素材", "投稿素材",
    "ブランドキット", "マーケティング素材",
    "レポート作成", "AI分析",
    "料金", "いくら", "値段", "プラン", "サブスク",
]

# 商品IDとキーワードのマッピング
KEYWORD_TO_PRODUCT = {
    "ロゴ": "brand_kit",
    "バナー": "brand_kit",
    "アイコン": "img_transparent",
    "透過": "img_transparent",
    "ブランドキット": "brand_kit",
    "SNS素材": "sns_content_pack",
    "コンテンツパック": "sns_content_pack",
    "投稿素材": "sns_content_pack",
    "物件マーケティング": "property_marketing",
    "不動産広告": "property_marketing",
    "レポート": "ai_report_mini",
}


class SalesChannel:
    """inquiry_bot に組み込む販売チャネル."""

    def __init__(self):
        self.pricing = PricingEngine()
        self.handler = OrderHandler()

    def detect_purchase_intent(self, message: str) -> bool:
        """メッセージから購買意図を検出."""
        return any(kw in message for kw in PURCHASE_INTENT_KEYWORDS)

    def suggest_product(self, message: str) -> Optional[dict]:
        """メッセージ内容に応じて商品を提案.

        Returns:
            {"product": dict, "suggestion_text": str} or None
        """
        # キーワードマッチで最適商品を選定
        matched_id = None
        for keyword, product_id in KEYWORD_TO_PRODUCT.items():
            if keyword in message:
                matched_id = product_id
                break

        # 画像系のデフォルト
        if not matched_id:
            for kw in ["画像", "イラスト", "写真"]:
                if kw in message:
                    matched_id = "img_single"
                    break

        if not matched_id:
            return None

        product = self.pricing.get_product(matched_id)
        if not product:
            return None

        price = product.get("price_jpy", product.get("price_jpy_monthly", 0))

        suggestion = (
            f"✨ おすすめ: **{product['name']}**\n"
            f"{product['description']}\n"
            f"💰 料金: ¥{price:,}\n\n"
            f"ご希望の内容（プロンプト）を教えてください。すぐに生成できます。"
        )

        return {
            "product": product,
            "product_id": matched_id,
            "suggestion_text": suggestion,
        }

    def get_product_menu(self) -> str:
        """チャット用の商品メニューテキストを生成."""
        products = self.pricing.get_all_products_summary()

        lines = ["🛒 **AI Asset Marketplace メニュー**\n"]

        # 即時商品
        instant = [p for p in products if p["type"] == "instant"]
        if instant:
            lines.append("**📸 即時生成商品:**")
            for p in instant:
                lines.append(f"  • {p['name']} — ¥{p['price_jpy']:,}")
            lines.append("")

        # サブスク
        subs = [p for p in products if p["type"] == "subscription"]
        if subs:
            lines.append("**📅 月額プラン:**")
            for p in subs:
                lines.append(f"  • {p['name']} — ¥{p['price_jpy_monthly']:,}/月")
            lines.append("")

        lines.append("気になる商品名を教えてください。")
        return "\n".join(lines)

    def handle_purchase(
        self,
        product_id: str,
        prompt: str,
        customer_id: str,
        options: Optional[dict] = None,
    ) -> dict:
        """購入処理を実行.

        Returns:
            {"success": bool, "message": str, "order": dict}
        """
        result = self.handler.process_instant_order(
            product_id=product_id,
            prompt=prompt,
            customer_id=customer_id,
            options=options,
        )

        if "error" in result:
            return {
                "success": False,
                "message": f"生成に失敗しました: {result['error']}",
                "order": result,
            }

        return {
            "success": True,
            "message": (
                f"✅ 生成完了！\n"
                f"注文ID: {result['order_id']}\n"
                f"ファイル数: {result.get('file_count', 0)}件\n"
                f"料金: ¥{result.get('price_jpy', 0):,}"
            ),
            "order": result,
        }
