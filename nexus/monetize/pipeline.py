"""
MONETIZE — 収益生成パイプライン

具体的な収益化チャネルと実行ロジック。
ALPHAの成果物を実際の収益に変換する。

収益チャネル:
1. フリーランス案件 — 提案書生成・自動応募
2. デジタルプロダクト — テンプレート・ツール・API
3. コンテンツ収益 — 技術記事・チュートリアル
4. コンサルティング — AI導入提案
5. 自動化サービス — 反復タスクの自動化提供
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from anthropic import Anthropic

from nexus.alpha.engine import AlphaOutput, AlphaTask, TaskType

logger = logging.getLogger("nexus.monetize")


class Channel(str, Enum):
    """収益化チャネル"""
    FREELANCE = "freelance"
    DIGITAL_PRODUCT = "digital_product"
    CONTENT = "content"
    CONSULTING = "consulting"
    AUTOMATION = "automation"


class DealStatus(str, Enum):
    """案件ステータス"""
    IDENTIFIED = "identified"    # 発見
    PROPOSED = "proposed"        # 提案済み
    NEGOTIATING = "negotiating"  # 交渉中
    ACCEPTED = "accepted"        # 受注
    IN_PROGRESS = "in_progress"  # 進行中
    DELIVERED = "delivered"      # 納品
    PAID = "paid"                # 入金完了
    CLOSED = "closed"            # 完了


@dataclass
class Deal:
    """収益案件"""
    title: str
    channel: Channel
    status: DealStatus
    estimated_revenue: float
    actual_revenue: float = 0.0
    description: str = ""
    deliverables: list[str] = field(default_factory=list)
    alpha_output_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    deal_id: str = ""

    def __post_init__(self):
        if not self.deal_id:
            import hashlib
            raw = f"{self.title}{self.channel}{self.created_at}"
            self.deal_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "deal_id": self.deal_id,
            "title": self.title,
            "channel": self.channel.value,
            "status": self.status.value,
            "estimated_revenue": self.estimated_revenue,
            "actual_revenue": self.actual_revenue,
            "description": self.description,
            "deliverables": self.deliverables,
            "alpha_output_ids": self.alpha_output_ids,
            "created_at": self.created_at,
        }


@dataclass
class RevenueReport:
    """収益レポート"""
    period: str
    total_estimated: float = 0.0
    total_actual: float = 0.0
    deals_by_channel: dict[str, int] = field(default_factory=dict)
    deals_by_status: dict[str, int] = field(default_factory=dict)
    top_deals: list[dict] = field(default_factory=list)
    pipeline_health: float = 0.0  # 0-1


class MonetizePipeline:
    """
    収益化パイプライン

    ALPHAの成果物をDealに変換し、収益化プロセスを管理する。
    """

    PROPOSAL_PROMPT = """あなたは収益化の専門家です。

以下のAI成果物を、具体的な収益案件に変換してください。

出力ルール（JSON形式）:
- "deals": 収益案件のリスト
  - 各案件: {
      "title": "案件名",
      "channel": "freelance/digital_product/content/consulting/automation",
      "estimated_revenue": 数値（円）,
      "description": "具体的な内容",
      "deliverables": ["成果物1", "成果物2"],
      "action_plan": ["ステップ1", "ステップ2"]
    }
- "immediate_actions": すぐに実行すべきアクション（リスト）
- "revenue_timeline": 収益化までのタイムライン"""

    def __init__(self, data_dir: Path | None = None):
        self.client = Anthropic()
        self.data_dir = data_dir or Path("nexus/data/monetize")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.deals: list[Deal] = []
        self._load_deals()

    def convert_to_deals(self, alpha_outputs: list[AlphaOutput]) -> list[Deal]:
        """ALPHA成果物をDealに変換する"""
        outputs_text = "\n\n---\n\n".join(
            f"[{o.output_id}] タイプ: {o.task_type.value}\n品質: {o.quality.value}\n"
            f"収益ポテンシャル: {o.revenue_potential}\n内容: {o.content[:500]}"
            for o in alpha_outputs
        )

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=self.PROPOSAL_PROMPT,
            messages=[{"role": "user", "content": f"AI成果物:\n{outputs_text}"}],
        )

        deals = self._parse_deals(response.content[0].text, alpha_outputs)
        self.deals.extend(deals)
        self._save_deals()
        return deals

    def update_deal_status(self, deal_id: str, new_status: DealStatus, actual_revenue: float | None = None) -> Deal | None:
        """案件ステータスを更新"""
        for deal in self.deals:
            if deal.deal_id == deal_id:
                deal.status = new_status
                if actual_revenue is not None:
                    deal.actual_revenue = actual_revenue
                self._save_deals()
                return deal
        return None

    def generate_proposal(self, deal: Deal) -> str:
        """案件の提案書を生成"""
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system="あなたはプロのビジネスライターです。説得力のある提案書を書いてください。",
            messages=[{
                "role": "user",
                "content": (
                    f"以下の案件に対する提案書を作成してください:\n\n"
                    f"案件名: {deal.title}\n"
                    f"チャネル: {deal.channel.value}\n"
                    f"内容: {deal.description}\n"
                    f"成果物: {', '.join(deal.deliverables)}\n"
                    f"想定金額: {deal.estimated_revenue}円"
                ),
            }],
        )
        return response.content[0].text

    def generate_alpha_tasks_for_deal(self, deal: Deal) -> list[AlphaTask]:
        """Deal実行に必要なALPHAタスクを生成"""
        tasks = []
        for i, deliverable in enumerate(deal.deliverables):
            task_type = self._channel_to_task_type(deal.channel)
            tasks.append(AlphaTask(
                task_type=task_type,
                instruction=(
                    f"案件「{deal.title}」の成果物を作成してください。\n\n"
                    f"成果物: {deliverable}\n"
                    f"案件概要: {deal.description}\n\n"
                    f"クライアントに納品可能な品質で生成してください。"
                ),
                context={"deal_id": deal.deal_id, "deliverable_index": i},
                priority=8,
                source="monetize",
            ))
        return tasks

    def get_revenue_report(self, period: str = "all") -> RevenueReport:
        """収益レポートを生成"""
        report = RevenueReport(period=period)

        for deal in self.deals:
            report.total_estimated += deal.estimated_revenue
            report.total_actual += deal.actual_revenue

            ch = deal.channel.value
            report.deals_by_channel[ch] = report.deals_by_channel.get(ch, 0) + 1

            st = deal.status.value
            report.deals_by_status[st] = report.deals_by_status.get(st, 0) + 1

        # パイプライン健全性: 進行中案件の割合
        active_statuses = {DealStatus.PROPOSED, DealStatus.NEGOTIATING, DealStatus.ACCEPTED, DealStatus.IN_PROGRESS}
        active_count = sum(1 for d in self.deals if d.status in active_statuses)
        report.pipeline_health = active_count / max(len(self.deals), 1)

        # トップ案件
        top = sorted(self.deals, key=lambda d: d.estimated_revenue, reverse=True)[:5]
        report.top_deals = [d.to_dict() for d in top]

        return report

    def _parse_deals(self, raw_text: str, alpha_outputs: list[AlphaOutput]) -> list[Deal]:
        """Claude応答をDealリストにパース"""
        try:
            json_start = raw_text.find("{")
            json_end = raw_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(raw_text[json_start:json_end])
            else:
                parsed = {}
        except json.JSONDecodeError:
            parsed = {}

        deals = []
        output_ids = [o.output_id for o in alpha_outputs]

        for d in parsed.get("deals", []):
            try:
                channel = Channel(d.get("channel", "freelance"))
            except ValueError:
                channel = Channel.FREELANCE

            deals.append(Deal(
                title=d.get("title", "Unknown Deal"),
                channel=channel,
                status=DealStatus.IDENTIFIED,
                estimated_revenue=d.get("estimated_revenue", 0),
                description=d.get("description", ""),
                deliverables=d.get("deliverables", []),
                alpha_output_ids=output_ids,
            ))

        return deals

    def _channel_to_task_type(self, channel: Channel) -> TaskType:
        """チャネルからタスク種別を推定"""
        mapping = {
            Channel.FREELANCE: TaskType.SERVICE,
            Channel.DIGITAL_PRODUCT: TaskType.CODE,
            Channel.CONTENT: TaskType.CONTENT,
            Channel.CONSULTING: TaskType.STRATEGY,
            Channel.AUTOMATION: TaskType.CODE,
        }
        return mapping.get(channel, TaskType.SERVICE)

    def _save_deals(self) -> None:
        """全Dealをファイルに保存"""
        deals_file = self.data_dir / "deals.json"
        data = [d.to_dict() for d in self.deals]
        deals_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_deals(self) -> None:
        """ファイルからDealを読み込み"""
        deals_file = self.data_dir / "deals.json"
        if not deals_file.exists():
            return

        try:
            data = json.loads(deals_file.read_text(encoding="utf-8"))
            for d in data:
                self.deals.append(Deal(
                    title=d["title"],
                    channel=Channel(d["channel"]),
                    status=DealStatus(d["status"]),
                    estimated_revenue=d["estimated_revenue"],
                    actual_revenue=d.get("actual_revenue", 0),
                    description=d.get("description", ""),
                    deliverables=d.get("deliverables", []),
                    alpha_output_ids=d.get("alpha_output_ids", []),
                    created_at=d.get("created_at", ""),
                    deal_id=d.get("deal_id", ""),
                ))
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to load deals from file")
