"""
NEXUS V2 ORCHESTRATOR — デジタルアセット量産型収益ループ

旧オーケストレータとの違い:
- 旧: CRAWL(案件探し) → TRY(出品) → DEBATE(改善) → EVOLVE(進化)
       → ココナラ/ランサーズに出品するための仕組み
- 新: RESEARCH → CREATE → DISTRIBUTE → ANALYZE → OPTIMIZE
       → デジタルアセットを量産して複数プラットフォームに配信する仕組み

実行モード:
1. research  — 市場分析のみ
2. create    — アセット生成のみ
3. full      — RESEARCH→CREATE→DISTRIBUTE の全サイクル
4. debate    — 収益戦略の議論
5. status    — ポートフォリオ状況確認
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus.v2.channels import RevenueChannel, AssetType, CHANNEL_CONFIGS
from nexus.v2.content_creator import ContentCreator
from nexus.v2.distributor import Distributor
from nexus.v2.market_researcher import MarketResearcher
from nexus.v2.revenue_debate import RevenueDebate

logger = logging.getLogger("nexus.v2.orchestrator")


@dataclass
class CycleResult:
    """1サイクルの結果"""
    cycle_number: int
    mode: str
    assets_created: int = 0
    assets_distributed: int = 0
    debates_held: int = 0
    estimated_monthly_revenue: int = 0
    actions_taken: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "cycle_number": self.cycle_number,
            "mode": self.mode,
            "assets_created": self.assets_created,
            "assets_distributed": self.assets_distributed,
            "debates_held": self.debates_held,
            "estimated_monthly_revenue": self.estimated_monthly_revenue,
            "actions_taken": self.actions_taken,
            "errors": self.errors,
            "timestamp": self.timestamp,
        }


@dataclass
class NexusV2State:
    """NEXUS V2のシステム状態"""
    cycles_completed: int = 0
    total_assets: int = 0
    total_distributed: int = 0
    total_debates: int = 0
    estimated_monthly_revenue: int = 0
    active_channels: list[str] = field(default_factory=list)
    last_cycle: str = ""

    def to_dict(self) -> dict:
        return {
            "cycles_completed": self.cycles_completed,
            "total_assets": self.total_assets,
            "total_distributed": self.total_distributed,
            "total_debates": self.total_debates,
            "estimated_monthly_revenue": self.estimated_monthly_revenue,
            "active_channels": self.active_channels,
            "last_cycle": self.last_cycle,
        }


class NexusV2Orchestrator:
    """
    NEXUS V2 オーケストレータ

    デジタルアセット量産 → 配信 → 分析 → 最適化の
    自律ループを管理する。
    """

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path("nexus/data/v2")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.researcher = MarketResearcher(self.data_dir / "research")
        self.creator = ContentCreator(self.data_dir / "content")
        self.distributor = Distributor(self.data_dir / "distribution")
        self.debate = RevenueDebate(self.data_dir / "debate")
        self.state = NexusV2State()
        self.cycle_history: list[CycleResult] = []

    def run(self, mode: str = "full", num_cycles: int = 1, focus: str = "") -> list[CycleResult]:
        """メインエントリーポイント"""
        logger.info("NEXUS V2 starting (mode=%s, cycles=%d)", mode, num_cycles)
        results = []

        for i in range(num_cycles):
            cycle_num = self.state.cycles_completed + 1
            logger.info("=== Cycle %d (mode=%s) ===", cycle_num, mode)

            if mode == "research":
                result = self._cycle_research(cycle_num, focus)
            elif mode == "create":
                result = self._cycle_create(cycle_num, focus)
            elif mode == "full":
                result = self._cycle_full(cycle_num, focus)
            elif mode == "debate":
                result = self._cycle_debate(cycle_num, focus)
            elif mode == "status":
                result = self._cycle_status(cycle_num)
            else:
                logger.error("Unknown mode: %s", mode)
                result = CycleResult(cycle_number=cycle_num, mode=mode, errors=[f"Unknown mode: {mode}"])

            results.append(result)
            self.cycle_history.append(result)
            self._update_state(result)
            self._save_state()

        return results

    def _cycle_research(self, cycle_num: int, focus: str) -> CycleResult:
        """市場分析サイクル"""
        result = CycleResult(cycle_number=cycle_num, mode="research")

        try:
            if focus:
                # 特定チャネルのみ分析
                channel = RevenueChannel(focus)
                insight = self.researcher.research_channel(channel)
                result.actions_taken.append(f"Researched {channel.value}: score={insight.opportunity_score}")
            else:
                # 全チャネル分析
                report = self.researcher.research_all_channels()
                result.actions_taken.append(f"Full market research: {len(report.insights)} channels analyzed")
                result.actions_taken.append(f"Priority: {report.priority_ranking}")
                result.estimated_monthly_revenue = report.monthly_revenue_target

        except Exception as e:
            logger.error("Research failed: %s", e)
            result.errors.append(str(e))

        return result

    def _cycle_create(self, cycle_num: int, focus: str) -> CycleResult:
        """アセット生成サイクル"""
        result = CycleResult(cycle_number=cycle_num, mode="create")

        try:
            # 市場分析結果から生成キューを作成
            queue = self.researcher.get_creation_queue()

            if not queue:
                # キューが空なら、デフォルトの生成プランを使用
                queue = self._default_creation_queue(focus)

            for spec in queue[:5]:  # 1サイクル最大5アセット
                try:
                    asset_type = AssetType(spec["asset_type"])
                    theme = spec["theme"]
                    context = spec.get("context", "")

                    # 生成前に簡易評価
                    evaluation = self.debate.quick_evaluate(spec)
                    if not evaluation.get("should_create", True):
                        logger.info("Skipping asset (low confidence): %s", theme)
                        result.actions_taken.append(f"Skipped: {theme} (confidence too low)")
                        continue

                    asset = self.creator.create(asset_type, theme, context)
                    result.assets_created += 1
                    result.actions_taken.append(f"Created: {asset.title} ({asset_type.value})")

                    # 配信タスクも作成
                    tasks = self.distributor.prepare_distribution(asset)
                    result.assets_distributed += len(tasks)
                    result.actions_taken.append(f"Distribution tasks: {len(tasks)} platforms")

                except Exception as e:
                    logger.error("Asset creation failed: %s", e)
                    result.errors.append(f"Creation error: {e}")

        except Exception as e:
            logger.error("Create cycle failed: %s", e)
            result.errors.append(str(e))

        return result

    def _cycle_full(self, cycle_num: int, focus: str) -> CycleResult:
        """フルサイクル: RESEARCH → DEBATE → CREATE → DISTRIBUTE"""
        result = CycleResult(cycle_number=cycle_num, mode="full")

        try:
            # Step 1: RESEARCH
            logger.info("Step 1/4: Market Research")
            report = self.researcher.research_all_channels()
            result.actions_taken.append(f"Research: {len(report.insights)} channels")

            # Step 2: DEBATE
            logger.info("Step 2/4: Strategy Debate")
            debate_topic = "5チャネル収益化戦略の最適化"
            debate_context = json.dumps(report.to_dict(), ensure_ascii=False)[:3000]
            debate_result = self.debate.debate(debate_topic, debate_context)
            result.debates_held += 1
            result.estimated_monthly_revenue = debate_result.estimated_monthly_revenue
            result.actions_taken.append(f"Debate: estimated ¥{debate_result.estimated_monthly_revenue}/月")

            # Step 3: CREATE (議論結果に基づいて生成)
            logger.info("Step 3/4: Content Creation")
            for priority_asset in debate_result.priority_assets[:5]:
                try:
                    asset_type_str = priority_asset.get("asset_type", "template")
                    asset_type = AssetType(asset_type_str)
                    theme = priority_asset.get("theme", "")
                    reason = priority_asset.get("reason", "")

                    asset = self.creator.create(asset_type, theme, reason)
                    result.assets_created += 1
                    result.actions_taken.append(f"Created: {asset.title}")

                    # Step 4: DISTRIBUTE
                    tasks = self.distributor.prepare_distribution(asset)
                    result.assets_distributed += len(tasks)

                except Exception as e:
                    logger.error("Asset creation/distribution failed: %s", e)
                    result.errors.append(str(e))

            logger.info("Step 4/4: Distribution complete")

        except Exception as e:
            logger.error("Full cycle failed: %s", e)
            result.errors.append(str(e))

        return result

    def _cycle_debate(self, cycle_num: int, focus: str) -> CycleResult:
        """議論サイクル"""
        result = CycleResult(cycle_number=cycle_num, mode="debate")

        try:
            topic = focus or "デジタルアセット量産による収益化戦略"
            context = ""

            # 既存ポートフォリオがあればコンテキストに含める
            portfolio = self.creator.get_portfolio()
            if portfolio["total_assets"] > 0:
                context = json.dumps(portfolio, ensure_ascii=False)

            debate_result = self.debate.debate(topic, context)
            result.debates_held += 1
            result.estimated_monthly_revenue = debate_result.estimated_monthly_revenue
            result.actions_taken.append(f"Debate completed: {debate_result.consensus[:100]}")
            result.actions_taken.extend([f"Action: {a.get('action', '')}" for a in debate_result.action_plan])

        except Exception as e:
            logger.error("Debate cycle failed: %s", e)
            result.errors.append(str(e))

        return result

    def _cycle_status(self, cycle_num: int) -> CycleResult:
        """状態確認サイクル（API呼び出しなし）"""
        result = CycleResult(cycle_number=cycle_num, mode="status")

        portfolio = self.creator.get_portfolio()
        dist_summary = self.distributor.get_distribution_summary()

        result.assets_created = portfolio["total_assets"]
        result.assets_distributed = dist_summary.get("live_count", 0)
        result.estimated_monthly_revenue = int(portfolio["total_monthly_revenue"])
        result.actions_taken.append(f"Portfolio: {portfolio['total_assets']} assets")
        result.actions_taken.append(f"Channels: {portfolio['channels_active']}")
        result.actions_taken.append(f"Distribution: {dist_summary}")
        result.actions_taken.append(f"State: {self.state.to_dict()}")

        return result

    def _default_creation_queue(self, focus: str) -> list[dict[str, Any]]:
        """デフォルトの生成キュー（市場分析なしの場合）"""
        defaults = [
            {
                "asset_type": "music_track",
                "theme": "Lo-fi hip hop beats for studying and relaxation",
                "priority": 10,
            },
            {
                "asset_type": "video_script",
                "theme": "不動産投資初心者が知るべき5つの真実",
                "priority": 9,
            },
            {
                "asset_type": "template",
                "theme": "不動産投資収支計算Notionテンプレート",
                "priority": 8,
            },
            {
                "asset_type": "stock_image",
                "theme": "Modern real estate and architecture concepts",
                "priority": 7,
            },
            {
                "asset_type": "prompt_pack",
                "theme": "不動産業務効率化AIプロンプト50選",
                "priority": 6,
            },
        ]

        if focus:
            # フォーカスがあればそのチャネルのみ
            channel_to_type = {
                "streaming": "music_track",
                "video": "video_script",
                "digital_product": "template",
                "stock_content": "stock_image",
                "micro_saas": "api_service",
            }
            target_type = channel_to_type.get(focus, "")
            if target_type:
                defaults = [d for d in defaults if d["asset_type"] == target_type]

        return defaults

    def _update_state(self, result: CycleResult) -> None:
        """システム状態を更新"""
        self.state.cycles_completed += 1
        self.state.total_assets += result.assets_created
        self.state.total_distributed += result.assets_distributed
        self.state.total_debates += result.debates_held
        self.state.estimated_monthly_revenue = result.estimated_monthly_revenue
        self.state.last_cycle = result.timestamp

        # アクティブチャネルを更新
        portfolio = self.creator.get_portfolio()
        self.state.active_channels = portfolio.get("channels_active", [])

    def _save_state(self) -> None:
        """状態をファイルに保存"""
        state_file = self.data_dir / "nexus_v2_state.json"
        state_file.write_text(
            json.dumps(self.state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # サイクル履歴も保存
        history_file = self.data_dir / "cycle_history.json"
        data = [c.to_dict() for c in self.cycle_history]
        history_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def main():
    """CLI エントリーポイント"""
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    focus = sys.argv[2] if len(sys.argv) > 2 else ""
    cycles = int(sys.argv[3]) if len(sys.argv) > 3 else 1

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    orchestrator = NexusV2Orchestrator()
    results = orchestrator.run(mode=mode, num_cycles=cycles, focus=focus)

    print("\n" + "=" * 60)
    print("NEXUS V2 — 実行結果")
    print("=" * 60)

    for r in results:
        print(f"\nCycle {r.cycle_number} ({r.mode}):")
        print(f"  Assets created: {r.assets_created}")
        print(f"  Distribution tasks: {r.assets_distributed}")
        print(f"  Debates: {r.debates_held}")
        print(f"  Est. monthly revenue: ¥{r.estimated_monthly_revenue:,}")
        if r.actions_taken:
            print("  Actions:")
            for a in r.actions_taken:
                print(f"    - {a}")
        if r.errors:
            print("  Errors:")
            for e in r.errors:
                print(f"    ! {e}")

    print(f"\nState: {orchestrator.state.to_dict()}")


if __name__ == "__main__":
    main()
