"""
収益チャネル定義 — デジタルアセット量産型

旧モデル（FREELANCE/CONSULTING/AUTOMATION）を廃止し、
スケーラブルな5チャネルに再設計。

全チャネルの共通点:
- 1回作れば永久に売れる
- AIが量産できる
- 人間の労働時間に比例しない
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RevenueChannel(str, Enum):
    """収益チャネル"""
    STREAMING = "streaming"           # AI音楽 → Spotify/Apple Music
    VIDEO = "video"                   # YouTube広告収益
    DIGITAL_PRODUCT = "digital_product"  # Gumroad/Lemon Squeezy
    STOCK_CONTENT = "stock_content"   # Adobe Stock/Pond5
    MICRO_SAAS = "micro_saas"         # サブスクリプションAPI


class RevenueModel(str, Enum):
    """課金モデル"""
    PER_STREAM = "per_stream"         # 再生あたり（$0.003-0.005）
    AD_REVENUE = "ad_revenue"         # 広告収益（CPM $2-10）
    ONE_TIME_SALE = "one_time_sale"   # 買い切り
    PER_DOWNLOAD = "per_download"     # DLあたり（$0.25-3.00）
    SUBSCRIPTION = "subscription"     # 月額課金


class Platform(str, Enum):
    """配信プラットフォーム"""
    # 音楽
    SPOTIFY = "spotify"
    APPLE_MUSIC = "apple_music"
    YOUTUBE_MUSIC = "youtube_music"
    AMAZON_MUSIC = "amazon_music"
    # 動画
    YOUTUBE = "youtube"
    # デジタル商品
    GUMROAD = "gumroad"
    LEMON_SQUEEZY = "lemon_squeezy"
    NOTE = "note"
    # ストック
    ADOBE_STOCK = "adobe_stock"
    POND5 = "pond5"
    SHUTTERSTOCK = "shutterstock"
    # SaaS
    SELF_HOSTED = "self_hosted"


class AssetType(str, Enum):
    """生成するアセットの種類"""
    MUSIC_TRACK = "music_track"
    VIDEO_SCRIPT = "video_script"
    EBOOK = "ebook"
    TEMPLATE = "template"
    TOOL = "tool"
    PROMPT_PACK = "prompt_pack"
    STOCK_IMAGE = "stock_image"
    STOCK_VIDEO = "stock_video"
    API_SERVICE = "api_service"


@dataclass
class ChannelConfig:
    """チャネルの詳細設定"""
    channel: RevenueChannel
    revenue_model: RevenueModel
    platforms: list[Platform]
    asset_types: list[AssetType]
    avg_revenue_per_unit: float       # 1単位あたりの平均収益（円/月）
    creation_cost: float              # 1単位の生成コスト（円）
    time_to_first_revenue: str        # 初収益までの期間
    scalability: str                  # low/medium/high
    description: str = ""


# 各チャネルの現実的な設定
CHANNEL_CONFIGS: dict[RevenueChannel, ChannelConfig] = {
    RevenueChannel.STREAMING: ChannelConfig(
        channel=RevenueChannel.STREAMING,
        revenue_model=RevenueModel.PER_STREAM,
        platforms=[Platform.SPOTIFY, Platform.APPLE_MUSIC, Platform.YOUTUBE_MUSIC, Platform.AMAZON_MUSIC],
        asset_types=[AssetType.MUSIC_TRACK],
        avg_revenue_per_unit=50,        # 1曲あたり月50円（控えめ見積）
        creation_cost=0,                # Suno無料枠 or 月額$10
        time_to_first_revenue="2-4週間",
        scalability="high",
        description=(
            "AI音楽生成（Suno/Udio）でlo-fi、ambient、meditation等のトラックを量産。"
            "DistroKidで全ストリーミングサービスに配信。"
            "100曲で月5,000円、1000曲で月50,000円のペース。"
            "複利的に資産が積み上がる。"
        ),
    ),
    RevenueChannel.VIDEO: ChannelConfig(
        channel=RevenueChannel.VIDEO,
        revenue_model=RevenueModel.AD_REVENUE,
        platforms=[Platform.YOUTUBE],
        asset_types=[AssetType.VIDEO_SCRIPT],
        avg_revenue_per_unit=500,       # 1動画あたり月500円（再生数による）
        creation_cost=10,               # TTS/画像生成のAPIコスト
        time_to_first_revenue="1-3ヶ月",
        scalability="high",
        description=(
            "ファセレスYouTubeチャンネル。"
            "Claude脚本→TTS音声→プログラマティック映像生成。"
            "不動産解説、AI活用術、meditation/ambientなど。"
            "CPM $2-10、月100本で月50,000-500,000円。"
        ),
    ),
    RevenueChannel.DIGITAL_PRODUCT: ChannelConfig(
        channel=RevenueChannel.DIGITAL_PRODUCT,
        revenue_model=RevenueModel.ONE_TIME_SALE,
        platforms=[Platform.GUMROAD, Platform.LEMON_SQUEEZY, Platform.NOTE],
        asset_types=[AssetType.EBOOK, AssetType.TEMPLATE, AssetType.TOOL, AssetType.PROMPT_PACK],
        avg_revenue_per_unit=3000,      # 1商品あたり月3,000円
        creation_cost=50,               # Claude API生成コスト
        time_to_first_revenue="1-2週間",
        scalability="medium",
        description=(
            "Notionテンプレート、不動産投資計算ツール、AIプロンプト集、"
            "業務効率化テンプレートなど。"
            "Gumroadで$5-50で販売。手数料5%+$0.50。"
            "10商品×月3件で月150,000円。"
        ),
    ),
    RevenueChannel.STOCK_CONTENT: ChannelConfig(
        channel=RevenueChannel.STOCK_CONTENT,
        revenue_model=RevenueModel.PER_DOWNLOAD,
        platforms=[Platform.ADOBE_STOCK, Platform.SHUTTERSTOCK],
        asset_types=[AssetType.STOCK_IMAGE, AssetType.STOCK_VIDEO],
        avg_revenue_per_unit=100,       # 1素材あたり月100円
        creation_cost=5,                # 画像生成APIコスト
        time_to_first_revenue="1-4週間",
        scalability="high",
        description=(
            "AI生成の不動産ビジュアル、建築コンセプト、ビジネスシーン画像。"
            "Adobe Stock（33%コミッション、AI明示必須）、Shutterstock（15-40%、AI明示必須）。"
            "Pond5はAI画像不可のため除外。Pond5はAI動画・音楽のみ対応。"
            "Getty ImagesはAI全面禁止。"
            "DLあたり$0.25-3.00、月500素材で月50,000円。"
        ),
    ),
    RevenueChannel.MICRO_SAAS: ChannelConfig(
        channel=RevenueChannel.MICRO_SAAS,
        revenue_model=RevenueModel.SUBSCRIPTION,
        platforms=[Platform.SELF_HOSTED],
        asset_types=[AssetType.API_SERVICE],
        avg_revenue_per_unit=50000,     # 1サービスあたり月50,000円（顧客数次第）
        creation_cost=5000,             # 開発コスト
        time_to_first_revenue="1-3ヶ月",
        scalability="high",
        description=(
            "不動産AI分析ツール、物件レポート自動生成API、"
            "賃貸市場予測ツールなど。"
            "月額¥980-4,980。10顧客で月49,800円。"
        ),
    ),
}


@dataclass
class DigitalAsset:
    """生成されたデジタルアセット"""
    asset_id: str
    asset_type: AssetType
    channel: RevenueChannel
    title: str
    description: str
    content: str                        # 生成されたコンテンツ（JSON）
    target_platforms: list[Platform] = field(default_factory=list)
    status: str = "created"             # created/distributed/earning/archived
    monthly_revenue: float = 0.0
    total_revenue: float = 0.0
    created_at: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "asset_type": self.asset_type.value,
            "channel": self.channel.value,
            "title": self.title,
            "description": self.description,
            "target_platforms": [p.value for p in self.target_platforms],
            "status": self.status,
            "monthly_revenue": self.monthly_revenue,
            "total_revenue": self.total_revenue,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }
