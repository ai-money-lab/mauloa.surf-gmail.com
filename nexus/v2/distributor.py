"""
DISTRIBUTOR — プラットフォーム配信システム

生成されたデジタルアセットを各プラットフォームに配信する。
現段階ではAPI連携の仕様書を生成（実際のAPI呼び出しは外部ツール経由）。

配信先:
1. 音楽 → DistroKid経由でSpotify/Apple Music/YouTube Music
2. 動画 → YouTube Data API
3. デジタル商品 → Gumroad API
4. ストック素材 → Adobe Stock Contributor Portal / Pond5
5. SaaS → Render/Vercel/Railway
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus.v2.channels import (
    AssetType,
    DigitalAsset,
    Platform,
    RevenueChannel,
)

logger = logging.getLogger("nexus.v2.distributor")


@dataclass
class DistributionTask:
    """配信タスク"""
    asset_id: str
    platform: Platform
    status: str = "pending"  # pending/ready/submitted/live/failed
    submission_data: dict = field(default_factory=dict)
    platform_url: str = ""
    submitted_at: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "platform": self.platform.value,
            "status": self.status,
            "submission_data": self.submission_data,
            "platform_url": self.platform_url,
            "submitted_at": self.submitted_at,
            "notes": self.notes,
        }


# 各プラットフォームの配信仕様
PLATFORM_SPECS: dict[Platform, dict[str, Any]] = {
    Platform.SPOTIFY: {
        "distributor": "DistroKid",
        "cost": "$22.99/年",
        "requirements": [
            "WAV/FLAC音源ファイル",
            "アルバムアートワーク（3000x3000px以上、JPG/PNG）",
            "メタデータ（タイトル、アーティスト、ジャンル、リリース日）",
            "ISRC/UPCコード（DistroKidが自動付与）",
        ],
        "timeline": "配信まで2-5営業日",
        "revenue_model": "$0.003-0.005/ストリーム",
        "ai_policy": "AI生成音楽は許可（ただしスパム的大量投稿は制限される可能性）",
    },
    Platform.YOUTUBE: {
        "api": "YouTube Data API v3",
        "requirements": [
            "動画ファイル（MP4、1080p以上推奨）",
            "サムネイル（1280x720px）",
            "タイトル、説明、タグ",
            "YouTube Data API OAuthトークン",
        ],
        "monetization": "チャンネル登録者500人 + 再生時間3000時間 or ショート300万回",
        "revenue_model": "CPM $2-10（ニッチによる）",
        "ai_policy": "AI生成コンテンツは許可（改変されたメディアの開示が必要）",
    },
    Platform.GUMROAD: {
        "api": "Gumroad API v2",
        "requirements": [
            "商品ファイル（PDF/ZIP/任意）",
            "商品名、説明文、価格",
            "カバー画像（1280x720px推奨）",
            "Gumroadアカウント + Stripe接続",
        ],
        "fee": "10% + $0.50/取引（Discover経由は30%）",
        "revenue_model": "売上 - 手数料",
        "ai_policy": "AI生成コンテンツ許可",
    },
    Platform.LEMON_SQUEEZY: {
        "api": "Lemon Squeezy API",
        "requirements": [
            "商品ファイル",
            "商品名、説明文、価格",
            "Lemon Squeezyアカウント",
        ],
        "fee": "5% + $0.50/取引",
        "revenue_model": "売上 - 手数料",
        "ai_policy": "AI生成コンテンツ許可",
    },
    Platform.ADOBE_STOCK: {
        "portal": "Adobe Stock Contributor",
        "requirements": [
            "画像: JPEG 4MP以上",
            "動画: MOV/MP4 HD以上",
            "AI生成の明示チェックボックス必須",
            "メタデータ: タイトル、説明、キーワード（英語）",
            "Adobe Contributorアカウント",
        ],
        "fee": "ロイヤリティ33%（画像）、35%（動画）",
        "revenue_model": "$0.33/画像DL、動画は$数/DL",
        "ai_policy": "AI生成OK（明示必須、著名人/ブランド名のプロンプト禁止）",
    },
    Platform.POND5: {
        "portal": "Pond5 Contributor",
        "requirements": [
            "動画: MOV/MP4 HD/4K",
            "画像: JPEG/TIFF",
            "音楽: WAV/AIF",
            "AI生成の明示",
            "メタデータ（英語）",
        ],
        "fee": "ロイヤリティ40-60%（独占/非独占で異なる）",
        "revenue_model": "クリエイターが価格設定可能",
        "ai_policy": "AI生成OK（明示必須）",
    },
    Platform.SELF_HOSTED: {
        "hosting": "Render/Railway/Vercel",
        "requirements": [
            "Dockerコンテナ or Pythonアプリ",
            "Stripe決済連携",
            "ドメイン名",
        ],
        "cost": "$7-25/月",
        "revenue_model": "月額サブスクリプション",
    },
}


class Distributor:
    """
    プラットフォーム配信システム

    生成されたデジタルアセットを各プラットフォームの形式に変換し、
    配信準備を整える。
    """

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path("nexus/data/v2/distribution")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tasks: list[DistributionTask] = []

    def prepare_distribution(self, asset: DigitalAsset) -> list[DistributionTask]:
        """アセットの配信タスクを作成する"""
        tasks = []
        for platform in asset.target_platforms:
            task = self._create_task(asset, platform)
            tasks.append(task)
            self.tasks.append(task)

        self._save_tasks(tasks)
        logger.info("Created %d distribution tasks for asset %s", len(tasks), asset.asset_id)
        return tasks

    def get_platform_guide(self, platform: Platform) -> dict[str, Any]:
        """プラットフォームのセットアップガイドを取得"""
        return PLATFORM_SPECS.get(platform, {"error": f"Unknown platform: {platform}"})

    def get_pending_tasks(self) -> list[DistributionTask]:
        """未完了の配信タスクを取得"""
        return [t for t in self.tasks if t.status in ("pending", "ready")]

    def update_task_status(self, asset_id: str, platform: Platform, status: str, url: str = "") -> DistributionTask | None:
        """配信タスクのステータスを更新"""
        for task in self.tasks:
            if task.asset_id == asset_id and task.platform == platform:
                task.status = status
                if url:
                    task.platform_url = url
                if status == "submitted":
                    task.submitted_at = datetime.now(timezone.utc).isoformat()
                self._save_tasks([task])
                return task
        return None

    def get_distribution_summary(self) -> dict[str, Any]:
        """配信状況のサマリー"""
        by_status: dict[str, int] = {}
        by_platform: dict[str, int] = {}

        for task in self.tasks:
            by_status[task.status] = by_status.get(task.status, 0) + 1
            plat = task.platform.value
            by_platform[plat] = by_platform.get(plat, 0) + 1

        return {
            "total_tasks": len(self.tasks),
            "by_status": by_status,
            "by_platform": by_platform,
            "live_count": by_status.get("live", 0),
        }

    def _create_task(self, asset: DigitalAsset, platform: Platform) -> DistributionTask:
        """個別の配信タスクを作成"""
        spec = PLATFORM_SPECS.get(platform, {})
        content = json.loads(asset.content) if asset.content else {}

        submission_data = self._build_submission_data(asset, platform, content, spec)

        return DistributionTask(
            asset_id=asset.asset_id,
            platform=platform,
            status="ready",
            submission_data=submission_data,
            notes=f"要件: {spec.get('requirements', [])}",
        )

    def _build_submission_data(
        self,
        asset: DigitalAsset,
        platform: Platform,
        content: dict,
        spec: dict,
    ) -> dict:
        """プラットフォーム固有の提出データを構築"""
        base = {
            "title": asset.title,
            "description": asset.description,
            "platform": platform.value,
            "requirements": spec.get("requirements", []),
            "fee": spec.get("fee", ""),
            "ai_policy": spec.get("ai_policy", ""),
        }

        if platform in (Platform.SPOTIFY, Platform.APPLE_MUSIC, Platform.YOUTUBE_MUSIC):
            base["distributor"] = "DistroKid"
            base["tracks"] = content.get("tracks", [])
            base["album_name"] = content.get("album_name", asset.title)
            base["artist_name"] = content.get("artist_name", "")

        elif platform == Platform.YOUTUBE:
            base["script"] = content.get("script", {})
            base["tags"] = content.get("tags", [])
            base["thumbnail_text"] = content.get("thumbnail_text", "")

        elif platform in (Platform.GUMROAD, Platform.LEMON_SQUEEZY):
            base["price"] = content.get("price_usd", 0)
            base["sales_page"] = content.get("sales_page", {})

        elif platform in (Platform.ADOBE_STOCK, Platform.POND5):
            base["assets"] = content.get("assets", [])
            base["ai_disclosure"] = content.get("ai_disclosure", "Created using generative AI tools")

        return base

    def _save_tasks(self, tasks: list[DistributionTask]) -> None:
        """配信タスクを保存"""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_file = self.data_dir / f"tasks_{ts}.json"
        data = [t.to_dict() for t in tasks]
        output_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
