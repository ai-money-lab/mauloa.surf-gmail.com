"""
PRODUCT GENERATOR — 売れるデジタル商品を自動生成する

商品カテゴリ:
1. プロンプトパック — 業種特化のChatGPT/Claudeプロンプト集
2. 自動化スクリプト — 業務効率化ツール（Python/GAS/n8n）
3. テンプレート集 — レポート/提案書/分析テンプレート
4. APIマイクロサービス — 特定用途のAI API
5. 教育コンテンツ — チュートリアル/ハンズオン教材
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from anthropic import Anthropic


class ProductCategory(str, Enum):
    """商品カテゴリ"""
    PROMPT_PACK = "prompt_pack"
    AUTOMATION_SCRIPT = "automation_script"
    TEMPLATE_SET = "template_set"
    API_SERVICE = "api_service"
    EDUCATION = "education"


class ProductStatus(str, Enum):
    """商品ステータス"""
    DRAFT = "draft"
    GENERATING = "generating"
    REVIEW = "review"
    READY = "ready"
    LISTED = "listed"
    SELLING = "selling"


class Marketplace(str, Enum):
    """販売プラットフォーム"""
    COCONALA = "coconala"
    NOTE = "note"
    BOOTH = "booth"
    GUMROAD = "gumroad"
    ZENN = "zenn"
    SELF = "self"


@dataclass
class Product:
    """デジタル商品"""
    name: str
    category: ProductCategory
    status: ProductStatus
    price: int  # 円
    description: str = ""
    content: str = ""
    files: list[str] = field(default_factory=list)
    target_marketplaces: list[str] = field(default_factory=list)
    listing_copy: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    product_id: str = ""

    def __post_init__(self):
        if not self.product_id:
            raw = f"{self.name}{self.category}{self.created_at}"
            self.product_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "name": self.name,
            "category": self.category.value,
            "status": self.status.value,
            "price": self.price,
            "description": self.description,
            "content_length": len(self.content),
            "files": self.files,
            "target_marketplaces": self.target_marketplaces,
            "listing_copy": self.listing_copy,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


GENERATION_PROMPTS: dict[ProductCategory, str] = {
    ProductCategory.PROMPT_PACK: """あなたはプロンプトエンジニアリングの専門家です。
指定されたテーマで、即座に使えるプロンプトパックを作成してください。

出力（JSON）:
- "product_name": 商品名（魅力的に）
- "description": 商品説明（購入者目線で具体的なメリットを）
- "prompts": プロンプトのリスト（最低10個）
  - 各プロンプト: {"title": "", "prompt": "", "use_case": "", "expected_output": ""}
- "bonus": ボーナスコンテンツ（使い方ガイド等）
- "price_suggestion": 推奨価格（円）
- "target_audience": ターゲット層""",

    ProductCategory.AUTOMATION_SCRIPT: """あなたは自動化のプロフェッショナルです。
指定されたテーマで、すぐに使える自動化スクリプトを作成してください。

出力（JSON）:
- "product_name": 商品名
- "description": 何を自動化するか、導入効果
- "scripts": スクリプトのリスト
  - 各スクリプト: {"filename": "", "language": "", "code": "", "description": ""}
- "setup_guide": セットアップ手順
- "price_suggestion": 推奨価格（円）
- "time_saved": 導入による時間節約（月あたり）""",

    ProductCategory.TEMPLATE_SET: """あなたはビジネステンプレートの専門家です。
指定されたテーマで、プロ品質のテンプレート集を作成してください。

出力（JSON）:
- "product_name": 商品名
- "description": 商品説明
- "templates": テンプレートのリスト
  - 各テンプレート: {"name": "", "content": "", "use_case": "", "format": ""}
- "customization_guide": カスタマイズ方法
- "price_suggestion": 推奨価格（円）""",

    ProductCategory.EDUCATION: """あなたは教育コンテンツの専門家です。
指定されたテーマで、実践的な教育コンテンツを作成してください。

出力（JSON）:
- "product_name": コース/教材名
- "description": 学習内容と到達目標
- "chapters": 章立て
  - 各章: {"title": "", "content": "", "exercises": [], "key_takeaways": []}
- "prerequisites": 前提知識
- "price_suggestion": 推奨価格（円）
- "completion_time": 想定学習時間""",

    ProductCategory.API_SERVICE: """あなたはAPI設計の専門家です。
指定されたテーマで、マイクロSaaS APIの設計書を作成してください。

出力（JSON）:
- "product_name": サービス名
- "description": 何を解決するAPIか
- "endpoints": APIエンドポイント設計
  - 各エンドポイント: {"method": "", "path": "", "description": "", "request": {}, "response": {}}
- "pricing_model": 課金モデル（月額/従量/フリーミアム）
- "tech_stack": 技術構成
- "price_suggestion": 推奨月額価格（円）""",
}


LISTING_PROMPT = """あなたはマーケットプレイスの出品コピーライターです。
以下の商品情報から、購買意欲を掻き立てる出品文を作成してください。

出力（JSON）:
- "title": 出品タイトル（30文字以内、インパクト重視）
- "subtitle": サブタイトル（メリットを端的に）
- "description": 商品説明文（購入者が「買いたい」と思う構成で）
- "bullet_points": セールスポイント（5つ）
- "tags": 検索用タグ（10個）
- "category_suggestion": 推奨カテゴリ"""


class ProductGenerator:
    """
    デジタル商品の自動生成エンジン

    テーマとカテゴリを指定すると、販売可能な商品を丸ごと生成する。
    出品用コピーも同時に生成する。
    """

    def __init__(self, data_dir: Path | None = None):
        self.client = Anthropic()
        self.data_dir = data_dir or Path("nexus/data/factory")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.products: list[Product] = []
        self._load_products()

    def generate(self, theme: str, category: ProductCategory, target_price: int = 0) -> Product:
        """テーマとカテゴリから商品を生成する"""
        system_prompt = GENERATION_PROMPTS.get(category, GENERATION_PROMPTS[ProductCategory.TEMPLATE_SET])

        instruction = f"テーマ: {theme}"
        if target_price:
            instruction += f"\n目標価格帯: {target_price}円"
        instruction += "\n\n上記テーマで、即座に販売可能な品質の商品を生成してください。"

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": instruction}],
        )

        product = self._parse_product(response.content[0].text, category)

        # 出品コピーも生成
        listing = self._generate_listing(product)
        product.listing_copy = listing
        product.status = ProductStatus.READY

        self.products.append(product)
        self._save_product(product)
        return product

    def generate_batch(self, themes: list[dict[str, Any]]) -> list[Product]:
        """複数商品をバッチ生成"""
        products = []
        for t in themes:
            theme = t.get("theme", "")
            category = ProductCategory(t.get("category", "prompt_pack"))
            price = t.get("price", 0)
            product = self.generate(theme, category, price)
            products.append(product)
        return products

    def get_catalog(self) -> list[dict]:
        """全商品カタログを返す"""
        return [p.to_dict() for p in self.products]

    def get_product(self, product_id: str) -> Product | None:
        """IDで商品を取得"""
        for p in self.products:
            if p.product_id == product_id:
                return p
        return None

    def update_status(self, product_id: str, new_status: ProductStatus) -> Product | None:
        """商品ステータスを更新"""
        product = self.get_product(product_id)
        if product:
            product.status = new_status
            self._save_product(product)
        return product

    def _generate_listing(self, product: Product) -> dict[str, str]:
        """出品用コピーを生成"""
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=LISTING_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"商品名: {product.name}\n"
                    f"カテゴリ: {product.category.value}\n"
                    f"価格: {product.price}円\n"
                    f"説明: {product.description}\n"
                    f"内容（一部）: {product.content[:500]}"
                ),
            }],
        )

        try:
            raw = response.content[0].text
            json_start = raw.find("{")
            json_end = raw.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(raw[json_start:json_end])
        except (json.JSONDecodeError, IndexError):
            pass
        return {}

    def _parse_product(self, raw_text: str, category: ProductCategory) -> Product:
        """Claude応答をProductにパース"""
        try:
            json_start = raw_text.find("{")
            json_end = raw_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(raw_text[json_start:json_end])
            else:
                parsed = {}
        except json.JSONDecodeError:
            parsed = {}

        name = parsed.get("product_name", f"AI商品_{category.value}")
        description = parsed.get("description", "")
        price = parsed.get("price_suggestion", 3000)

        # コンテンツ抽出（カテゴリに応じて）
        content_keys = ["prompts", "scripts", "templates", "chapters", "endpoints"]
        content_data = {}
        for key in content_keys:
            if key in parsed:
                content_data[key] = parsed[key]
                break

        content = json.dumps(content_data, ensure_ascii=False, indent=2) if content_data else raw_text

        return Product(
            name=name,
            category=category,
            status=ProductStatus.GENERATING,
            price=price if isinstance(price, int) else 3000,
            description=description,
            content=content,
            target_marketplaces=[Marketplace.COCONALA.value, Marketplace.NOTE.value],
            metadata={
                "raw_parsed": {k: v for k, v in parsed.items() if k not in content_keys},
                "target_audience": parsed.get("target_audience", ""),
            },
        )

    def _save_product(self, product: Product) -> None:
        """商品をファイルに保存"""
        product_file = self.data_dir / f"{product.product_id}.json"
        product_file.write_text(
            json.dumps(product.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # コンテンツ本体も別ファイル保存
        content_file = self.data_dir / f"{product.product_id}_content.json"
        content_file.write_text(product.content, encoding="utf-8")

    def _load_products(self) -> None:
        """保存済み商品を読み込み"""
        for f in self.data_dir.glob("*.json"):
            if f.name.endswith("_content.json") or f.name == "catalog.json":
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                content_file = self.data_dir / f"{data['product_id']}_content.json"
                content = content_file.read_text(encoding="utf-8") if content_file.exists() else ""
                self.products.append(Product(
                    name=data["name"],
                    category=ProductCategory(data["category"]),
                    status=ProductStatus(data["status"]),
                    price=data["price"],
                    description=data.get("description", ""),
                    content=content,
                    files=data.get("files", []),
                    target_marketplaces=data.get("target_marketplaces", []),
                    listing_copy=data.get("listing_copy", {}),
                    metadata=data.get("metadata", {}),
                    created_at=data.get("created_at", ""),
                    product_id=data.get("product_id", ""),
                ))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
