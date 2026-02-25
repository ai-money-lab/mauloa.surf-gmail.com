"""Performance Tracker — System E の自己分析エンジン.

オーケストレーターログとNEXUS V2の実行履歴を解析し、
トレンド・成功率・ボトルネックを数値化する。
進化エンジンにフィードバックすることで、データ駆動型の自己改善を実現。

機能:
  - オーケストレーターJSONLログの解析
  - アクション別成功率の算出
  - 時系列トレンド分析
  - コード生成パイプラインの品質メトリクス
  - NEXUS V2サイクル履歴の統合分析
  - 進化エンジン用メトリクスの自動生成
"""

import json
import logging
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("system_e.performance_tracker")

JST = timezone(timedelta(hours=9))
ORCHESTRATOR_LOG = Path(__file__).parent / "data" / "orchestrator_log.jsonl"
NEXUS_V2_DATA = Path(__file__).parent.parent / "nexus" / "data" / "v2"
TRACKER_DIR = Path(__file__).parent / "data" / "performance"


class PerformanceTracker:
    """System E の全活動をトラッキングし分析する.

    オーケストレーターログ (JSONL) とNEXUS V2の実行結果を読み取り、
    成功率・頻度・トレンドなどのメトリクスを算出する。

    Args:
        log_path: オーケストレーターログのパス。
        nexus_data_dir: NEXUS V2データディレクトリ。
    """

    def __init__(
        self,
        log_path: Optional[Path] = None,
        nexus_data_dir: Optional[Path] = None,
    ):
        self.log_path = log_path or ORCHESTRATOR_LOG
        self.nexus_data_dir = nexus_data_dir or NEXUS_V2_DATA
        TRACKER_DIR.mkdir(parents=True, exist_ok=True)

    def load_orchestrator_log(self) -> list[dict]:
        """オーケストレーターのJSONLログを全行読み込む."""
        if not self.log_path.exists():
            logger.info("No orchestrator log found at %s", self.log_path)
            return []

        entries = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                logger.debug("Skipping malformed log line")
        return entries

    def load_nexus_cycle_history(self) -> list[dict]:
        """NEXUS V2のサイクル履歴を読み込む."""
        history_file = self.nexus_data_dir / "cycle_history.json"
        if not history_file.exists():
            return []
        try:
            return json.loads(history_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load NEXUS V2 history: %s", e)
            return []

    def load_nexus_run_results(self) -> list[dict]:
        """NEXUS V2の実行結果ファイルを読み込む."""
        runs_dir = self.nexus_data_dir / "runs"
        if not runs_dir.exists():
            return []

        results = []
        for f in sorted(runs_dir.glob("run_*.json")):
            try:
                results.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
        return results

    def compute_action_stats(self, entries: Optional[list[dict]] = None) -> dict:
        """アクション別の統計を算出する.

        Returns:
            {
                "total_actions": int,
                "by_action": {
                    "action_name": {
                        "count": int,
                        "success_count": int,
                        "failure_count": int,
                        "success_rate": float,
                        "last_run": str,
                    }
                }
            }
        """
        if entries is None:
            entries = self.load_orchestrator_log()

        stats: dict[str, dict] = {}
        for entry in entries:
            action = entry.get("action", "unknown")
            details = entry.get("details", {})
            timestamp = entry.get("timestamp", "")

            if action not in stats:
                stats[action] = {
                    "count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "last_run": "",
                }

            stats[action]["count"] += 1
            stats[action]["last_run"] = timestamp

            # 成功/失敗の判定
            has_error = "error" in details
            validation_passed = details.get("validation_passed")
            deploy_success = details.get("deploy_success")

            if has_error:
                stats[action]["failure_count"] += 1
            elif validation_passed is False or deploy_success is False:
                stats[action]["failure_count"] += 1
            else:
                stats[action]["success_count"] += 1

        # 成功率を計算
        for action_stats in stats.values():
            total = action_stats["count"]
            action_stats["success_rate"] = (
                action_stats["success_count"] / total if total > 0 else 0.0
            )

        return {
            "total_actions": len(entries),
            "by_action": stats,
        }

    def compute_codegen_metrics(self, entries: Optional[list[dict]] = None) -> dict:
        """コード生成パイプラインの品質メトリクスを算出.

        Returns:
            {
                "total_generations": int,
                "validation_pass_rate": float,
                "deploy_success_rate": float,
                "modules_generated": list[str],
            }
        """
        if entries is None:
            entries = self.load_orchestrator_log()

        codegen_entries = [
            e for e in entries
            if e.get("action") in ("codegen", "evo_codegen")
        ]

        if not codegen_entries:
            return {
                "total_generations": 0,
                "validation_pass_rate": 0.0,
                "deploy_success_rate": 0.0,
                "modules_generated": [],
            }

        total = len(codegen_entries)
        validation_passed = sum(
            1 for e in codegen_entries
            if e.get("details", {}).get("validation_passed") is True
        )
        deploy_success = sum(
            1 for e in codegen_entries
            if e.get("details", {}).get("deploy_success") is True
        )
        modules = [
            e.get("details", {}).get("module")
            for e in codegen_entries
            if e.get("details", {}).get("module")
        ]

        return {
            "total_generations": total,
            "validation_pass_rate": validation_passed / total if total > 0 else 0.0,
            "deploy_success_rate": deploy_success / total if total > 0 else 0.0,
            "modules_generated": modules,
        }

    def compute_time_trends(
        self,
        entries: Optional[list[dict]] = None,
        window_days: int = 7,
    ) -> dict:
        """時系列のアクティビティトレンドを算出.

        Args:
            entries: ログエントリ。
            window_days: 分析ウインドウ（日数）。

        Returns:
            {
                "window_days": int,
                "daily_counts": {"YYYY-MM-DD": int},
                "action_frequency": {"action": int},
                "trend": "increasing" | "decreasing" | "stable",
            }
        """
        if entries is None:
            entries = self.load_orchestrator_log()

        now = datetime.now(JST)
        cutoff = now - timedelta(days=window_days)
        cutoff_str = cutoff.isoformat()

        recent = [
            e for e in entries
            if e.get("timestamp", "") >= cutoff_str
        ]

        daily: Counter = Counter()
        action_freq: Counter = Counter()
        for entry in recent:
            ts = entry.get("timestamp", "")
            date_str = ts[:10] if len(ts) >= 10 else "unknown"
            daily[date_str] += 1
            action_freq[entry.get("action", "unknown")] += 1

        # トレンド判定 (前半 vs 後半)
        trend = "stable"
        if len(daily) >= 2:
            sorted_dates = sorted(daily.keys())
            mid = len(sorted_dates) // 2
            first_half = sum(daily[d] for d in sorted_dates[:mid])
            second_half = sum(daily[d] for d in sorted_dates[mid:])
            if second_half > first_half * 1.3:
                trend = "increasing"
            elif second_half < first_half * 0.7:
                trend = "decreasing"

        return {
            "window_days": window_days,
            "daily_counts": dict(sorted(daily.items())),
            "action_frequency": dict(action_freq.most_common()),
            "trend": trend,
        }

    def compute_nexus_metrics(self) -> dict:
        """NEXUS V2のパフォーマンスメトリクスを算出.

        Returns:
            {
                "total_cycles": int,
                "total_assets": int,
                "total_distributed": int,
                "total_debates": int,
                "error_rate": float,
                "revenue_trend": list[int],
                "mode_distribution": {"mode": int},
            }
        """
        history = self.load_nexus_cycle_history()

        if not history:
            return {
                "total_cycles": 0,
                "total_assets": 0,
                "total_distributed": 0,
                "total_debates": 0,
                "error_rate": 0.0,
                "revenue_trend": [],
                "mode_distribution": {},
            }

        total_cycles = len(history)
        total_assets = sum(c.get("assets_created", 0) for c in history)
        total_distributed = sum(c.get("assets_distributed", 0) for c in history)
        total_debates = sum(c.get("debates_held", 0) for c in history)
        error_cycles = sum(1 for c in history if c.get("errors"))
        revenue_trend = [c.get("estimated_monthly_revenue", 0) for c in history]

        mode_dist: Counter = Counter()
        for c in history:
            mode_dist[c.get("mode", "unknown")] += 1

        return {
            "total_cycles": total_cycles,
            "total_assets": total_assets,
            "total_distributed": total_distributed,
            "total_debates": total_debates,
            "error_rate": error_cycles / total_cycles if total_cycles > 0 else 0.0,
            "revenue_trend": revenue_trend,
            "mode_distribution": dict(mode_dist),
        }

    def generate_full_report(self) -> dict:
        """全メトリクスを統合したパフォーマンスレポートを生成.

        Returns:
            {
                "generated_at": str,
                "system_e": {action_stats, codegen_metrics, time_trends},
                "nexus_v2": {nexus_metrics},
                "health_score": float (0-100),
                "recommendations": list[str],
            }
        """
        entries = self.load_orchestrator_log()
        action_stats = self.compute_action_stats(entries)
        codegen_metrics = self.compute_codegen_metrics(entries)
        time_trends = self.compute_time_trends(entries)
        nexus_metrics = self.compute_nexus_metrics()

        health_score = self._calculate_health_score(
            action_stats, codegen_metrics, time_trends, nexus_metrics,
        )
        recommendations = self._generate_recommendations(
            action_stats, codegen_metrics, time_trends, nexus_metrics,
        )

        report = {
            "generated_at": datetime.now(JST).isoformat(),
            "system_e": {
                "action_stats": action_stats,
                "codegen_metrics": codegen_metrics,
                "time_trends": time_trends,
            },
            "nexus_v2": nexus_metrics,
            "health_score": health_score,
            "recommendations": recommendations,
        }

        # レポートを保存
        ts = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
        report_path = TRACKER_DIR / f"report_{ts}.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Performance report saved: %s", report_path)

        return report

    def generate_evolution_metrics(self) -> dict:
        """進化エンジン用のメトリクスを自動生成.

        EvolutionEngine.evolve_strategy() に渡すための
        データ駆動型メトリクスを構築する。
        """
        entries = self.load_orchestrator_log()
        action_stats = self.compute_action_stats(entries)
        codegen_metrics = self.compute_codegen_metrics(entries)
        time_trends = self.compute_time_trends(entries)
        nexus_metrics = self.compute_nexus_metrics()

        return {
            "source": "performance_tracker",
            "collected_at": datetime.now(JST).isoformat(),
            "system_e_total_actions": action_stats["total_actions"],
            "system_e_action_success_rates": {
                action: stats["success_rate"]
                for action, stats in action_stats["by_action"].items()
            },
            "codegen_pass_rate": codegen_metrics["validation_pass_rate"],
            "codegen_deploy_rate": codegen_metrics["deploy_success_rate"],
            "activity_trend": time_trends["trend"],
            "nexus_total_assets": nexus_metrics["total_assets"],
            "nexus_error_rate": nexus_metrics["error_rate"],
            "nexus_revenue_trend": nexus_metrics["revenue_trend"][-5:]
            if nexus_metrics["revenue_trend"]
            else [],
        }

    def _calculate_health_score(
        self,
        action_stats: dict,
        codegen_metrics: dict,
        time_trends: dict,
        nexus_metrics: dict,
    ) -> float:
        """0-100のヘルススコアを算出.

        加重平均:
          - System E 全体成功率: 30%
          - コード生成品質: 25%
          - アクティビティ: 20%
          - NEXUS V2: 25%
        """
        scores = []

        # System E 全体成功率 (30%)
        by_action = action_stats.get("by_action", {})
        if by_action:
            avg_success = sum(
                s["success_rate"] for s in by_action.values()
            ) / len(by_action)
            scores.append(avg_success * 100 * 0.30)
        else:
            scores.append(50.0 * 0.30)  # データなしは50点

        # コード生成品質 (25%)
        if codegen_metrics["total_generations"] > 0:
            codegen_score = (
                codegen_metrics["validation_pass_rate"] * 0.5
                + codegen_metrics["deploy_success_rate"] * 0.5
            ) * 100
            scores.append(codegen_score * 0.25)
        else:
            scores.append(50.0 * 0.25)

        # アクティビティ (20%)
        trend = time_trends.get("trend", "stable")
        trend_score = {"increasing": 90, "stable": 70, "decreasing": 40}.get(trend, 50)
        total = action_stats.get("total_actions", 0)
        activity_score = min(trend_score + min(total, 50), 100)
        scores.append(activity_score * 0.20)

        # NEXUS V2 (25%)
        if nexus_metrics["total_cycles"] > 0:
            nexus_score = (1.0 - nexus_metrics["error_rate"]) * 100
            if nexus_metrics["total_assets"] > 0:
                nexus_score = min(nexus_score + 10, 100)
            scores.append(nexus_score * 0.25)
        else:
            scores.append(50.0 * 0.25)

        return round(sum(scores), 1)

    def _generate_recommendations(
        self,
        action_stats: dict,
        codegen_metrics: dict,
        time_trends: dict,
        nexus_metrics: dict,
    ) -> list[str]:
        """データに基づく改善推奨を生成."""
        recs = []

        # 成功率の低いアクション
        for action, stats in action_stats.get("by_action", {}).items():
            if stats["count"] >= 3 and stats["success_rate"] < 0.7:
                recs.append(
                    f"{action}の成功率が{stats['success_rate']:.0%}と低い。"
                    f"エラーパターンの調査を推奨。"
                )

        # コード生成パイプライン
        if codegen_metrics["total_generations"] > 0:
            if codegen_metrics["validation_pass_rate"] < 0.8:
                recs.append(
                    "コード生成の検証通過率が低い。"
                    "プロンプト改善またはバリデーションルールの調整を推奨。"
                )
            if codegen_metrics["deploy_success_rate"] < 0.7:
                recs.append(
                    "デプロイ成功率が低い。デプロイプロセスの確認を推奨。"
                )

        # アクティビティ
        if time_trends.get("trend") == "decreasing":
            recs.append(
                "アクティビティが減少傾向。スケジュール設定の見直しを推奨。"
            )

        # NEXUS V2
        if nexus_metrics["total_cycles"] > 0 and nexus_metrics["error_rate"] > 0.3:
            recs.append(
                f"NEXUS V2のエラー率が{nexus_metrics['error_rate']:.0%}。"
                f"APIキー・ネットワーク接続の確認を推奨。"
            )

        if not recs:
            recs.append("特に問題は検出されていません。現在の運用を継続してください。")

        return recs
