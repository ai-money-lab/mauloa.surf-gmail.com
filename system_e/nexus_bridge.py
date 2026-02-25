"""NEXUS Bridge — System E ↔ NEXUS V2 の双方向連携ブリッジ.

System E (メタ知性) と NEXUS V2 (収益エンジン) を接続し、
メタ知性が収益戦略を最適化し、収益データがメタ知性を進化させる。

双方向フロー:
  System E → NEXUS V2:
    - 議論結果に基づく収益戦略の最適化提案
    - コンテンツ生成キューの優先度調整
    - 新チャネル/アセットタイプの提案

  NEXUS V2 → System E:
    - 収益メトリクスの提供（進化エンジン用）
    - ポートフォリオ状態の報告
    - エラーパターンの報告
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from system_e.client import ClaudeClient
from system_e.agents import AgentRunner, STRATEGIST, OPTIMIZER

logger = logging.getLogger("system_e.nexus_bridge")

JST = timezone(timedelta(hours=9))
BRIDGE_LOG_DIR = Path(__file__).parent / "data" / "bridge"
NEXUS_V2_DATA = Path(__file__).parent.parent / "nexus" / "data" / "v2"


class NexusBridge:
    """System E と NEXUS V2 を接続する双方向ブリッジ.

    System E のメタ知性エージェントが NEXUS V2 のデータを分析し、
    最適化提案を生成する。NEXUS V2 の実績データは
    System E の進化エンジンへのフィードバックに活用される。

    Args:
        claude_client: ClaudeClient インスタンス。
        nexus_data_dir: NEXUS V2 データディレクトリ。
    """

    def __init__(
        self,
        claude_client: Optional[ClaudeClient] = None,
        nexus_data_dir: Optional[Path] = None,
    ):
        self.claude = claude_client or ClaudeClient()
        self.strategist = AgentRunner(STRATEGIST, self.claude)
        self.optimizer = AgentRunner(OPTIMIZER, self.claude)
        self.nexus_data_dir = nexus_data_dir or NEXUS_V2_DATA
        BRIDGE_LOG_DIR.mkdir(parents=True, exist_ok=True)

    def collect_nexus_state(self) -> dict:
        """NEXUS V2 の現在状態を収集する.

        Returns:
            {
                "state": dict,          # NexusV2State
                "portfolio": dict,      # アセットポートフォリオ
                "cycle_history": list,  # サイクル履歴
                "latest_debate": dict,  # 最新の議論結果
                "creation_queue": list, # 現在の生成キュー
            }
        """
        result: dict = {"collected_at": datetime.now(JST).isoformat()}

        # 状態ファイル
        state_file = self.nexus_data_dir / "nexus_v2_state.json"
        if state_file.exists():
            try:
                result["state"] = json.loads(state_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                result["state"] = {}
        else:
            result["state"] = {}

        # サイクル履歴
        history_file = self.nexus_data_dir / "cycle_history.json"
        if history_file.exists():
            try:
                result["cycle_history"] = json.loads(
                    history_file.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError):
                result["cycle_history"] = []
        else:
            result["cycle_history"] = []

        # ポートフォリオ (content/*.json の数)
        content_dir = self.nexus_data_dir / "content"
        if content_dir.exists():
            asset_files = list(content_dir.glob("*.json"))
            result["portfolio"] = {
                "total_assets": len(asset_files),
                "asset_files": [f.name for f in asset_files[:20]],
            }
        else:
            result["portfolio"] = {"total_assets": 0, "asset_files": []}

        # 最新の議論結果
        debate_dir = self.nexus_data_dir / "debate"
        if debate_dir.exists():
            debate_files = sorted(
                debate_dir.glob("*.json"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            if debate_files:
                try:
                    result["latest_debate"] = json.loads(
                        debate_files[0].read_text(encoding="utf-8")
                    )
                except (json.JSONDecodeError, OSError):
                    result["latest_debate"] = {}
            else:
                result["latest_debate"] = {}
        else:
            result["latest_debate"] = {}

        # 生成キュー
        queue_file = self.nexus_data_dir / "creation_queue.json"
        if queue_file.exists():
            try:
                result["creation_queue"] = json.loads(
                    queue_file.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError):
                result["creation_queue"] = []
        else:
            result["creation_queue"] = []

        return result

    def analyze_revenue_performance(self, nexus_state: Optional[dict] = None) -> dict:
        """NEXUS V2 の収益パフォーマンスを戦略的に分析.

        Strategist エージェントが NEXUS V2 のデータを分析し、
        改善点と新たな機会を特定する。

        Args:
            nexus_state: NEXUS V2 の状態。None なら自動収集。

        Returns:
            Strategist の分析結果。
        """
        if nexus_state is None:
            nexus_state = self.collect_nexus_state()

        logger.info("[NexusBridge] Analyzing NEXUS V2 revenue performance")

        # データを圧縮 (トークン節約)
        summary = self._summarize_nexus_state(nexus_state)

        analysis = self.strategist.think(
            task=(
                "NEXUS V2（デジタルアセット量産型収益エンジン）の"
                "パフォーマンスデータを分析し、以下を報告してください:\n"
                "1. 現在の収益状況の評価\n"
                "2. 最もポテンシャルの高いチャネル\n"
                "3. 改善すべきボトルネック\n"
                "4. 次の3ヶ月で集中すべきアクション\n"
                "5. System E が介入すべきポイント"
            ),
            context=json.dumps(summary, ensure_ascii=False, indent=2),
        )

        self._save_bridge_log("revenue_analysis", analysis)
        return analysis

    def generate_optimization_plan(
        self,
        nexus_state: Optional[dict] = None,
        system_e_insights: Optional[dict] = None,
    ) -> dict:
        """System E のメタ知性で NEXUS V2 の最適化計画を生成.

        Args:
            nexus_state: NEXUS V2 の状態。
            system_e_insights: System E の議論/進化結果（あれば）。

        Returns:
            {
                "optimized_queue": list,
                "channel_priorities": list,
                "resource_allocation": dict,
                "action_items": list,
            }
        """
        if nexus_state is None:
            nexus_state = self.collect_nexus_state()

        logger.info("[NexusBridge] Generating optimization plan for NEXUS V2")

        context_parts = [
            f"## NEXUS V2 状態\n{json.dumps(self._summarize_nexus_state(nexus_state), ensure_ascii=False, indent=2)}",
        ]
        if system_e_insights:
            context_parts.append(
                f"\n## System E メタ知性の洞察\n{json.dumps(system_e_insights, ensure_ascii=False, indent=2)[:2000]}"
            )

        plan = self.optimizer.think(
            task=(
                "NEXUS V2 の最適化計画を策定してください。以下をJSON形式で出力:\n"
                "{\n"
                '  "optimized_queue": [\n'
                '    {"asset_type": "...", "theme": "...", "priority": 1-10, "reason": "..."}\n'
                "  ],\n"
                '  "channel_priorities": ["channel1", "channel2"],\n'
                '  "resource_allocation": {"channel": "percentage"},\n'
                '  "action_items": ["具体的なアクション1", "..."]\n'
                "}"
            ),
            context="\n".join(context_parts),
        )

        self._save_bridge_log("optimization_plan", plan)
        return plan

    def generate_nexus_feedback(self) -> dict:
        """NEXUS V2 → System E 方向のフィードバックメトリクスを生成.

        進化エンジンが利用可能な形式で NEXUS V2 の実績を整理する。
        """
        nexus_state = self.collect_nexus_state()
        state = nexus_state.get("state", {})
        history = nexus_state.get("cycle_history", [])

        # 基本メトリクス
        metrics = {
            "source": "nexus_bridge",
            "collected_at": datetime.now(JST).isoformat(),
            "nexus_cycles_completed": state.get("cycles_completed", 0),
            "nexus_total_assets": state.get("total_assets", 0),
            "nexus_total_distributed": state.get("total_distributed", 0),
            "nexus_estimated_revenue": state.get("estimated_monthly_revenue", 0),
            "nexus_active_channels": state.get("active_channels", []),
        }

        # エラー分析
        if history:
            error_count = sum(1 for c in history if c.get("errors"))
            metrics["nexus_error_rate"] = error_count / len(history)
            metrics["nexus_recent_errors"] = [
                e
                for c in history[-5:]
                for e in c.get("errors", [])
            ]
        else:
            metrics["nexus_error_rate"] = 0.0
            metrics["nexus_recent_errors"] = []

        # 収益トレンド
        if history:
            revenues = [c.get("estimated_monthly_revenue", 0) for c in history]
            metrics["nexus_revenue_history"] = revenues[-10:]
        else:
            metrics["nexus_revenue_history"] = []

        return metrics

    def run_bridge_cycle(self, system_e_insights: Optional[dict] = None) -> dict:
        """双方向ブリッジの完全サイクルを実行.

        1. NEXUS V2 の状態収集
        2. 収益パフォーマンス分析 (System E → NEXUS V2)
        3. 最適化計画生成 (System E → NEXUS V2)
        4. 進化用フィードバック生成 (NEXUS V2 → System E)

        Returns:
            {
                "nexus_state": dict,
                "revenue_analysis": dict,
                "optimization_plan": dict,
                "evolution_feedback": dict,
            }
        """
        logger.info("=== NEXUS BRIDGE CYCLE START ===")
        result: dict = {}

        # Step 1: Collect state
        try:
            logger.info("[Bridge 1/4] Collecting NEXUS V2 state")
            nexus_state = self.collect_nexus_state()
            result["nexus_state"] = {
                "cycles": nexus_state.get("state", {}).get("cycles_completed", 0),
                "assets": nexus_state.get("portfolio", {}).get("total_assets", 0),
                "queue_size": len(nexus_state.get("creation_queue", [])),
            }
        except Exception as e:
            logger.error("[Bridge 1/4] State collection failed: %s", e)
            result["nexus_state"] = {"error": str(e)}
            nexus_state = {}

        # Step 2: Revenue analysis
        try:
            logger.info("[Bridge 2/4] Analyzing revenue performance")
            result["revenue_analysis"] = self.analyze_revenue_performance(nexus_state)
        except Exception as e:
            logger.error("[Bridge 2/4] Revenue analysis failed: %s", e)
            result["revenue_analysis"] = {"error": str(e)}

        # Step 3: Optimization plan
        try:
            logger.info("[Bridge 3/4] Generating optimization plan")
            result["optimization_plan"] = self.generate_optimization_plan(
                nexus_state, system_e_insights,
            )
        except Exception as e:
            logger.error("[Bridge 3/4] Optimization plan failed: %s", e)
            result["optimization_plan"] = {"error": str(e)}

        # Step 4: Evolution feedback
        try:
            logger.info("[Bridge 4/4] Generating evolution feedback")
            result["evolution_feedback"] = self.generate_nexus_feedback()
        except Exception as e:
            logger.error("[Bridge 4/4] Feedback generation failed: %s", e)
            result["evolution_feedback"] = {"error": str(e)}

        self._save_bridge_log("bridge_cycle", result)
        logger.info("=== NEXUS BRIDGE CYCLE COMPLETE ===")
        return result

    def _summarize_nexus_state(self, nexus_state: dict) -> dict:
        """トークン節約のためNEXUS状態を要約する."""
        state = nexus_state.get("state", {})
        history = nexus_state.get("cycle_history", [])
        portfolio = nexus_state.get("portfolio", {})

        summary = {
            "cycles_completed": state.get("cycles_completed", 0),
            "total_assets": portfolio.get("total_assets", 0),
            "total_distributed": state.get("total_distributed", 0),
            "estimated_monthly_revenue": state.get("estimated_monthly_revenue", 0),
            "active_channels": state.get("active_channels", []),
        }

        # 直近5サイクルのサマリー
        if history:
            recent = history[-5:]
            summary["recent_cycles"] = [
                {
                    "cycle": c.get("cycle_number"),
                    "mode": c.get("mode"),
                    "assets": c.get("assets_created", 0),
                    "errors": len(c.get("errors", [])),
                    "revenue": c.get("estimated_monthly_revenue", 0),
                }
                for c in recent
            ]

        # 生成キューサマリー
        queue = nexus_state.get("creation_queue", [])
        if queue:
            summary["queue_summary"] = [
                {"type": q.get("asset_type"), "priority": q.get("priority")}
                for q in queue[:5]
            ]

        return summary

    def _save_bridge_log(self, action: str, data: dict) -> None:
        """ブリッジログを保存."""
        ts = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
        entry = {
            "timestamp": datetime.now(JST).isoformat(),
            "action": action,
            "data": data,
        }
        log_path = BRIDGE_LOG_DIR / f"bridge_{action}_{ts}.json"
        log_path.write_text(
            json.dumps(entry, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
