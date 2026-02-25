"""
CONTENT CREATOR — デジタルアセット自動生成エンジン

旧ProductGeneratorとの違い:
- 旧: ココナラ出品用の商品説明を生成するだけ
- 新: 実際に配信可能なデジタルアセットを生成する

生成できるもの:
1. 音楽仕様書 → Suno/Udio APIで音楽生成
2. 動画脚本 → TTS + 映像で動画生成
3. デジタル商品 → Gumroadで即販売
4. ストック素材仕様 → 画像/動画生成
5. SaaS設計書 → デプロイ可能なAPI
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nexus.common import call_api, parse_json
from nexus.v2.channels import (
    AssetType,
    DigitalAsset,
    Platform,
    RevenueChannel,
)

logger = logging.getLogger("nexus.v2.content_creator")


# ─── 各アセットタイプの生成プロンプト ───

MUSIC_PROMPT = """あなたはAI音楽プロデューサーです。
ストリーミングプラットフォームで再生されやすい楽曲の仕様を設計してください。

重要な知識:
- lo-fi hip hop、ambient、meditation、study musicは再生回数が多いジャンル
- プレイリスト収録されやすい楽曲が月間再生数を伸ばす
- 2-4分の長さが最適（短すぎると再生単価が下がる）
- タイトルとアーティスト名は英語が有利（グローバルリーチ）

法的コンプライアンス（必須）:
- Sunoプロンプトに実在のアーティスト名を絶対に含めない
- 既存楽曲の模倣・盗用を示唆するプロンプトを使わない
- DistroKidで配信（AI音楽に最も柔軟）、TuneCorは100%AI拒否
- Spotifyは年間1,000再生未満はロイヤリティ対象外
- AI生成であることをメタデータに明示する
- 人間による編集・アレンジを加えて著作権を強化する指示を含める

出力（JSON）:
- "tracks": トラックリスト（5-10曲）
  - 各トラック: {
      "title": "英語タイトル",
      "genre": "ジャンル",
      "mood": "雰囲気キーワード（Sunoプロンプト用）",
      "tempo_bpm": BPM,
      "duration_seconds": 秒数,
      "suno_prompt": "Sunoに渡す生成プロンプト（英語・アーティスト名禁止）",
      "human_edit_notes": "人間が加えるべき編集・アレンジの指示",
      "tags": ["タグ1", "タグ2"],
      "target_playlists": ["狙うプレイリスト名"]
    }
- "album_name": アルバム/EP名
- "artist_name": アーティスト名（ブランド）
- "ai_disclosure": "AI生成であることの明示文"
- "distribution_notes": 配信時の注意点（DistroKid推奨）"""

VIDEO_PROMPT = """あなたはYouTubeコンテンツストラテジストです。
ファセレス（顔出しなし）チャンネルで高再生される動画の台本を作成してください。

重要な知識:
- フック（最初の5秒）が視聴維持率を決める
- 8-15分が広告収益を最大化する長さ
- サムネイルのテキストは7文字以内
- SEOタイトルにメインキーワードを含める
- 説明欄の最初の2行がクリック率に影響

法的コンプライアンス（2025年7月YouTube規約改定対応・必須）:
- AI生成コンテンツである旨の開示が必須（説明欄に明記）
- 低品質AIコンテンツは収益化剥奪の対象
- 「大量生産・反復的・独自の洞察なし」は不可
- 実在の人物のAI合成音声・映像は禁止
- 台本は独自の分析・専門知識を含む「実質的に変革的」なものにする
- 収益化要件: チャンネル登録者1,000人 + 公開再生時間4,000時間

出力（JSON）:
- "title": "SEO最適化されたタイトル",
- "thumbnail_text": "サムネイルテキスト（7文字以内）",
- "description": "説明欄テキスト（AI開示文を含む）",
- "ai_disclosure": "この動画はAIツールを活用して制作されています",
- "tags": ["SEOタグ"],
- "script": {
    "hook": "最初の5秒のセリフ（視聴者を引きつける）",
    "sections": [
      {"title": "セクション名", "narration": "ナレーション全文（独自分析を含む）", "visual_description": "画面に映すもの"}
    ],
    "outro": "締めのセリフ + CTA"
  },
- "estimated_length_minutes": 分数,
- "target_audience": "ターゲット視聴者",
- "seo_keywords": ["検索キーワード"],
- "original_insight": "この動画独自の分析・知見（他にはない価値）"
"""

DIGITAL_PRODUCT_PROMPT = """あなたはデジタル商品の設計者です。
Gumroadで実際に売れる商品を設計・生成してください。

重要な知識:
- Notionテンプレートは月$110,000売るクリエイターもいる
- $5-50の価格帯が最もコンバージョン率が高い
- 「時間を節約」「お金を稼ぐ」が最も売れる価値提案
- 商品ページのコピーが売上の80%を決める
- 最初の$1,000はGumroadで検証、成功したらLemon Squeezyに移行

出力（JSON）:
- "product_name": "商品名",
- "product_type": "ebook/template/tool/prompt_pack/spreadsheet",
- "price_usd": 価格（ドル）,
- "tagline": "一行キャッチコピー",
- "sales_page": {
    "headline": "メインヘッドライン",
    "subheadline": "サブヘッドライン",
    "pain_points": ["解決する悩み"],
    "benefits": ["得られるメリット"],
    "social_proof": "信頼性を示す要素",
    "cta": "購入ボタンのテキスト"
  },
- "content": "商品の実際のコンテンツ（全文）",
- "bonus": "ボーナスコンテンツ",
- "target_audience": "ターゲット層",
- "keywords": ["検索用キーワード"]"""

STOCK_CONTENT_PROMPT = """あなたはストックコンテンツの専門家です。
Adobe StockとShutterstockで売れるAI生成素材の仕様を設計してください。

重要な知識:
- AI生成コンテンツは「Created using generative AI tools」の明示が必須
- 特定アーティスト名/ブランド名の使用は厳禁（IPストライク3回で永久BAN）
- 不動産、ビジネス、テクノロジー系の需要が高い
- ハイパーリアルより明らかにAI的なスタイルの方が承認されやすい

法的コンプライアンス（必須）:
- Adobe Stock: AI明示チェックボックス必須、33%コミッション、最低4MP
- Shutterstock: AI明示タグ必須、15-40%コミッション（累計売上で変動）
- Pond5: AI画像は不可（AI動画・音楽は可）
- Getty Images: AI全面禁止（投稿不可）
- プロンプトに実在のアーティスト名・ブランド名・有名人名を絶対に含めない
- 著作権保護された作品の模倣を示唆するプロンプトを使わない
- 生成AIツール名（Midjourney, DALL-E等）をメタデータに含めない

出力（JSON）:
- "collection_name": "コレクション名",
- "assets": 素材リスト（10-20枚）
  - 各素材: {
      "title": "タイトル（英語）",
      "description": "説明（英語・50文字以上）",
      "generation_prompt": "画像生成AIに渡すプロンプト（英語・アーティスト名禁止）",
      "style": "スタイル指定",
      "category": "カテゴリ",
      "tags": ["タグ1", "タグ2", ...],
      "orientation": "horizontal/vertical/square",
      "suggested_price_usd": 価格
    }
- "target_platforms": ["adobe_stock", "shutterstock"],
- "ai_disclosure": "Created using generative AI tools",
- "legal_checklist": ["アーティスト名不使用", "ブランド名不使用", "AI明示済み"]
"""

SAAS_PROMPT = """あなたはマイクロSaaSの設計者です。
Claude APIを活用した、月額課金可能なサービスを設計してください。

重要な知識:
- 特定の業界/職種に特化したツールが最も売れる
- 月額$9.80-49.80の価格帯
- フリーミアムモデルで無料ユーザーから有料ユーザーへ転換
- APIとWebダッシュボードの両方を提供
- 不動産業界にはまだAIツールの空白がある

出力（JSON）:
- "service_name": "サービス名",
- "tagline": "一行説明",
- "problem": "解決する課題",
- "solution": "ソリューション概要",
- "features": [
    {"name": "機能名", "description": "説明", "tier": "free/pro/enterprise"}
  ],
- "pricing": {
    "free": {"price": 0, "limits": "制限事項"},
    "pro": {"price": 月額円, "limits": "制限事項"},
    "enterprise": {"price": 月額円, "limits": "制限事項"}
  },
- "tech_stack": {
    "backend": "技術",
    "frontend": "技術",
    "ai": "モデル",
    "hosting": "ホスティング"
  },
- "api_endpoints": [
    {"method": "GET/POST", "path": "/api/...", "description": "説明"}
  ],
- "mvp_scope": "MVP（最小実行可能製品）の範囲",
- "estimated_dev_days": 開発日数
"""

ASSET_PROMPTS: dict[AssetType, str] = {
    AssetType.MUSIC_TRACK: MUSIC_PROMPT,
    AssetType.VIDEO_SCRIPT: VIDEO_PROMPT,
    AssetType.EBOOK: DIGITAL_PRODUCT_PROMPT,
    AssetType.TEMPLATE: DIGITAL_PRODUCT_PROMPT,
    AssetType.TOOL: DIGITAL_PRODUCT_PROMPT,
    AssetType.PROMPT_PACK: DIGITAL_PRODUCT_PROMPT,
    AssetType.STOCK_IMAGE: STOCK_CONTENT_PROMPT,
    AssetType.STOCK_VIDEO: STOCK_CONTENT_PROMPT,
    AssetType.API_SERVICE: SAAS_PROMPT,
}

ASSET_TO_CHANNEL: dict[AssetType, RevenueChannel] = {
    AssetType.MUSIC_TRACK: RevenueChannel.STREAMING,
    AssetType.VIDEO_SCRIPT: RevenueChannel.VIDEO,
    AssetType.EBOOK: RevenueChannel.DIGITAL_PRODUCT,
    AssetType.TEMPLATE: RevenueChannel.DIGITAL_PRODUCT,
    AssetType.TOOL: RevenueChannel.DIGITAL_PRODUCT,
    AssetType.PROMPT_PACK: RevenueChannel.DIGITAL_PRODUCT,
    AssetType.STOCK_IMAGE: RevenueChannel.STOCK_CONTENT,
    AssetType.STOCK_VIDEO: RevenueChannel.STOCK_CONTENT,
    AssetType.API_SERVICE: RevenueChannel.MICRO_SAAS,
}

ASSET_TO_PLATFORMS: dict[AssetType, list[Platform]] = {
    AssetType.MUSIC_TRACK: [Platform.SPOTIFY, Platform.APPLE_MUSIC, Platform.YOUTUBE_MUSIC],
    AssetType.VIDEO_SCRIPT: [Platform.YOUTUBE],
    AssetType.EBOOK: [Platform.GUMROAD, Platform.NOTE],
    AssetType.TEMPLATE: [Platform.GUMROAD],
    AssetType.TOOL: [Platform.GUMROAD],
    AssetType.PROMPT_PACK: [Platform.GUMROAD, Platform.NOTE],
    AssetType.STOCK_IMAGE: [Platform.ADOBE_STOCK, Platform.SHUTTERSTOCK],
    AssetType.STOCK_VIDEO: [Platform.ADOBE_STOCK, Platform.SHUTTERSTOCK, Platform.POND5],
    AssetType.API_SERVICE: [Platform.SELF_HOSTED],
}


class ContentCreator:
    """
    デジタルアセット自動生成エンジン

    指定されたアセットタイプとテーマから、
    配信可能な品質のデジタルコンテンツを生成する。
    """

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path("nexus/data/v2/content")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.assets: list[DigitalAsset] = []

    def create(self, asset_type: AssetType, theme: str, context: str = "") -> DigitalAsset:
        """テーマからデジタルアセットを生成する"""
        prompt = ASSET_PROMPTS.get(asset_type)
        if not prompt:
            raise ValueError(f"Unknown asset type: {asset_type}")

        instruction = f"テーマ: {theme}"
        if context:
            instruction += f"\n\nコンテキスト（市場分析結果）:\n{context}"
        instruction += "\n\n上記テーマで、即座に配信・販売可能な品質で生成してください。"

        logger.info("Creating asset (type=%s, theme=%s)", asset_type.value, theme)
        raw_text = call_api(
            system=prompt,
            messages=[{"role": "user", "content": instruction}],
            max_tokens=8192,
        )

        parsed = parse_json(raw_text)
        asset = self._build_asset(asset_type, theme, parsed, raw_text)

        self.assets.append(asset)
        self._save_asset(asset)
        logger.info("Created asset: %s (id=%s)", asset.title, asset.asset_id)
        return asset

    def create_batch(self, specs: list[dict[str, Any]]) -> list[DigitalAsset]:
        """複数アセットをバッチ生成"""
        assets = []
        for spec in specs:
            asset_type = AssetType(spec["asset_type"])
            theme = spec["theme"]
            context = spec.get("context", "")
            asset = self.create(asset_type, theme, context)
            assets.append(asset)
        return assets

    def get_portfolio(self) -> dict[str, Any]:
        """全アセットのポートフォリオサマリー"""
        by_channel: dict[str, list[dict]] = {}
        total_monthly = 0.0

        for asset in self.assets:
            ch = asset.channel.value
            if ch not in by_channel:
                by_channel[ch] = []
            by_channel[ch].append(asset.to_dict())
            total_monthly += asset.monthly_revenue

        return {
            "total_assets": len(self.assets),
            "total_monthly_revenue": total_monthly,
            "by_channel": by_channel,
            "channels_active": list(by_channel.keys()),
        }

    def _build_asset(self, asset_type: AssetType, theme: str, parsed: dict, raw_text: str) -> DigitalAsset:
        """パースされたデータからDigitalAssetを構築"""
        channel = ASSET_TO_CHANNEL.get(asset_type, RevenueChannel.DIGITAL_PRODUCT)
        platforms = ASSET_TO_PLATFORMS.get(asset_type, [])

        # タイトル抽出（アセットタイプに応じて）
        title_raw = (
            parsed.get("album_name")
            or parsed.get("title")
            or parsed.get("product_name")
            or parsed.get("collection_name")
            or parsed.get("service_name")
            or f"{theme}_{asset_type.value}"
        )
        title = title_raw if isinstance(title_raw, str) else str(title_raw)

        desc_raw = (
            parsed.get("description")
            or parsed.get("tagline")
            or parsed.get("problem")
            or ""
        )
        description = desc_raw if isinstance(desc_raw, str) else json.dumps(desc_raw, ensure_ascii=False)

        ts = datetime.now(timezone.utc).isoformat()
        asset_id = hashlib.sha256(f"{title}{asset_type}{ts}".encode()).hexdigest()[:16]

        return DigitalAsset(
            asset_id=asset_id,
            asset_type=asset_type,
            channel=channel,
            title=title,
            description=description,
            content=json.dumps(parsed, ensure_ascii=False, indent=2),
            target_platforms=platforms,
            status="created",
            created_at=ts,
            metadata={"theme": theme, "raw_length": len(raw_text)},
        )

    def _save_asset(self, asset: DigitalAsset) -> None:
        """アセットをファイルに保存"""
        output_file = self.data_dir / f"{asset.asset_id}.json"
        data = asset.to_dict()
        data["content"] = asset.content  # 全コンテンツも保存
        output_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
