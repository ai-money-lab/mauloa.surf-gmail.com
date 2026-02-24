"""
MARKET RESEARCHER — データ駆動の市場分析エンジン

旧OpportunityCrawlerとの違い:
- 旧: 「ランサーズ/ココナラで何を出品すべきか」を聞くだけ
- 新: 各チャネルの市場データに基づいて、最も効率的なアセット生成戦略を設計する

分析対象:
1. 音楽: どのジャンル/ムードが再生されやすいか
2. YouTube: どのニッチが成長中か
3. デジタル商品: どのカテゴリが売れているか
4. ストック素材: どのカテゴリに需要があるか
5. SaaS: どの業界にギャップがあるか
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus.common import call_api, parse_json
from nexus.v2.channels import RevenueChannel, AssetType, CHANNEL_CONFIGS

logger = logging.getLogger("nexus.v2.market_researcher")


@dataclass
class MarketInsight:
    """市場分析結果"""
    channel: RevenueChannel
    trending_themes: list[str]
    recommended_assets: list[dict[str, Any]]
    competition_analysis: str
    opportunity_score: float            # 0-10
    estimated_monthly_potential: int     # 円
    action_items: list[str]
    data_sources: list[str] = field(default_factory=list)
    analyzed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "channel": self.channel.value,
            "trending_themes": self.trending_themes,
            "recommended_assets": self.recommended_assets,
            "competition_analysis": self.competition_analysis,
            "opportunity_score": self.opportunity_score,
            "estimated_monthly_potential": self.estimated_monthly_potential,
            "action_items": self.action_items,
            "data_sources": self.data_sources,
            "analyzed_at": self.analyzed_at,
        }


@dataclass
class ResearchReport:
    """全チャネル横断の分析レポート"""
    insights: list[MarketInsight]
    priority_ranking: list[str]        # チャネルの優先順位
    immediate_actions: list[dict]       # 今すぐやるべきこと
    monthly_revenue_target: int
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "insights": [i.to_dict() for i in self.insights],
            "priority_ranking": self.priority_ranking,
            "immediate_actions": self.immediate_actions,
            "monthly_revenue_target": self.monthly_revenue_target,
            "created_at": self.created_at,
        }


RESEARCH_PROMPT = """あなたはデジタルコンテンツ市場のアナリストです。
以下のチャネルについて、実データに基づいた市場分析を行ってください。

分析するチャネル: {channel_name}
チャネル説明: {channel_description}

既存のアセット情報:
{existing_assets}

過去のパフォーマンスデータ:
{performance_data}

以下を分析してください:

1. **トレンド分析**: 今どのテーマ/ジャンルが伸びているか
2. **競合分析**: 参入障壁と差別化ポイント
3. **推奨アセット**: 具体的に何を作るべきか（テーマ、形式、ターゲット）
4. **収益見込み**: 現実的な月間収益見込み
5. **アクション**: 今すぐ実行すべきステップ

重要: 希望的観測ではなく、市場の現実に基づいた分析をすること。
「AIだから何でもできる」ではなく「AIで実際に何が稼げるか」を分析すること。

出力（JSON）:
- "trending_themes": ["トレンド1", "トレンド2", ...],
- "recommended_assets": [
    {{
      "asset_type": "music_track/video_script/ebook/template/tool/prompt_pack/stock_image/stock_video/api_service",
      "theme": "具体的なテーマ",
      "title_idea": "タイトル案",
      "reason": "なぜこれが売れるか",
      "estimated_monthly_revenue": 円,
      "priority": 1-10
    }}
  ],
- "competition_analysis": "競合状況の詳細分析",
- "opportunity_score": 0-10の機会スコア,
- "estimated_monthly_potential": 月額収益見込み（円）,
- "action_items": ["アクション1", "アクション2", ...],
- "risks": ["リスク1", "リスク2", ...],
- "data_sources": ["参考にした情報源"]"""


STRATEGY_PROMPT = """あなたはデジタルコンテンツ事業の戦略コンサルタントです。
以下の全チャネルの分析結果から、最適な収益化戦略を設計してください。

分析結果:
{all_insights}

既存ポートフォリオ:
{portfolio}

制約:
- Claude API月額予算: ¥50,000
- 初期投資: 最小限（¥10,000以下）
- 目標: 月間¥100,000の収益

以下を決定してください:

1. **チャネル優先順位**: どのチャネルから攻めるか
2. **即時アクション**: 今日から始められること
3. **週次計画**: 1週間の生成計画
4. **月次目標**: 各チャネルの月次KPI

出力（JSON）:
- "priority_ranking": ["channel1", "channel2", ...],
- "immediate_actions": [
    {{"action": "何をするか", "channel": "チャネル", "expected_output": "期待する成果"}}
  ],
- "weekly_plan": {{
    "music_tracks": 週あたり生成数,
    "videos": 週あたり生成数,
    "digital_products": 週あたり生成数,
    "stock_assets": 週あたり生成数
  }},
- "monthly_kpi": {{
    "total_assets": 月間生成目標,
    "revenue_target": 月間収益目標（円）,
    "by_channel": {{"channel": {{"assets": 数, "revenue": 円}}}}
  }},
- "reasoning": "この戦略を選んだ理由"
"""


class MarketResearcher:
    """
    データ駆動の市場分析エンジン

    各チャネルの市場状況を分析し、
    最も効率的なアセット生成戦略を導出する。
    """

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path("nexus/data/v2/research")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.insights: list[MarketInsight] = []

    def research_channel(
        self,
        channel: RevenueChannel,
        existing_assets: list[dict] | None = None,
        performance_data: dict | None = None,
    ) -> MarketInsight:
        """特定チャネルの市場分析"""
        config = CHANNEL_CONFIGS.get(channel)
        if not config:
            raise ValueError(f"Unknown channel: {channel}")

        prompt = RESEARCH_PROMPT.format(
            channel_name=channel.value,
            channel_description=config.description,
            existing_assets=json.dumps(existing_assets or [], ensure_ascii=False, indent=2),
            performance_data=json.dumps(performance_data or {}, ensure_ascii=False, indent=2),
        )

        logger.info("Researching channel: %s", channel.value)
        raw_text = call_api(
            system=prompt,
            messages=[{"role": "user", "content": f"チャネル「{channel.value}」の市場分析を実行してください。"}],
            max_tokens=4096,
        )

        parsed = parse_json(raw_text)
        insight = MarketInsight(
            channel=channel,
            trending_themes=parsed.get("trending_themes", []),
            recommended_assets=parsed.get("recommended_assets", []),
            competition_analysis=parsed.get("competition_analysis", ""),
            opportunity_score=parsed.get("opportunity_score", 5.0),
            estimated_monthly_potential=parsed.get("estimated_monthly_potential", 0),
            action_items=parsed.get("action_items", []),
            data_sources=parsed.get("data_sources", []),
        )

        self.insights.append(insight)
        self._save_insight(insight)
        return insight

    def research_all_channels(self) -> ResearchReport:
        """全チャネルを分析して統合レポートを生成"""
        insights = []
        for channel in RevenueChannel:
            insight = self.research_channel(channel)
            insights.append(insight)

        report = self._synthesize_strategy(insights)
        self._save_report(report)
        return report

    def get_creation_queue(self, report: ResearchReport | None = None) -> list[dict[str, Any]]:
        """分析結果からアセット生成キューを作成"""
        if report is None:
            if not self.insights:
                return []
            report = self._synthesize_strategy(self.insights)

        queue = []
        for action in report.immediate_actions:
            for insight in report.insights:
                if insight.channel.value == action.get("channel"):
                    for rec in insight.recommended_assets[:3]:
                        queue.append({
                            "asset_type": rec.get("asset_type", "template"),
                            "theme": rec.get("theme", ""),
                            "context": insight.competition_analysis,
                            "priority": rec.get("priority", 5),
                            "estimated_revenue": rec.get("estimated_monthly_revenue", 0),
                        })

        # 優先度でソート
        queue.sort(key=lambda x: x.get("priority", 5), reverse=True)
        return queue

    def _synthesize_strategy(self, insights: list[MarketInsight]) -> ResearchReport:
        """全チャネルの分析結果から戦略を統合"""
        all_insights_text = json.dumps(
            [i.to_dict() for i in insights],
            ensure_ascii=False,
            indent=2,
        )

        prompt = STRATEGY_PROMPT.format(
            all_insights=all_insights_text,
            portfolio="（新規開始）",
        )

        logger.info("Synthesizing strategy from %d channel insights", len(insights))
        raw_text = call_api(
            system=prompt,
            messages=[{"role": "user", "content": "全チャネルの分析結果から最適な収益化戦略を設計してください。"}],
            max_tokens=4096,
        )

        parsed = parse_json(raw_text)

        immediate_actions = parsed.get("immediate_actions", [])
        priority = parsed.get("priority_ranking", [c.value for c in RevenueChannel])

        return ResearchReport(
            insights=insights,
            priority_ranking=priority,
            immediate_actions=immediate_actions,
            monthly_revenue_target=parsed.get("monthly_kpi", {}).get("revenue_target", 100000),
        )

    def _save_insight(self, insight: MarketInsight) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_file = self.data_dir / f"insight_{insight.channel.value}_{ts}.json"
        output_file.write_text(
            json.dumps(insight.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_report(self, report: ResearchReport) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_file = self.data_dir / f"report_{ts}.json"
        output_file.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
