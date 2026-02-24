#!/usr/bin/env python3
"""
NEXUS V2 自律実行スクリプト

Claude CodeがClaude Codeを動かす仕組み。
このスクリプトはGitHub Actionsまたはcronから定期実行される。

実行モード:
  python -m nexus.v2.run daily      # 毎日: 市場分析 + アセット生成 + 配信準備
  python -m nexus.v2.run weekly     # 毎週: 全チャネル戦略議論 + 最適化
  python -m nexus.v2.run create     # アセット生成のみ
  python -m nexus.v2.run status     # 状態確認（API呼び出しなし）

各モードの動作:
- daily: 上位2チャネルの市場分析 → 3アセット生成 → 配信タスク作成
- weekly: 全5チャネル分析 → 4専門家議論 → 次週の生成計画策定
- create: 市場分析結果に基づきアセットを5個生成
- status: ポートフォリオと配信状況をJSON出力
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from nexus.v2.orchestrator import NexusV2Orchestrator

logger = logging.getLogger("nexus.v2.run")

# ─── 実行結果をファイルに記録 ───

RESULTS_DIR = Path("nexus/data/v2/runs")


def save_run_result(mode: str, results: list[dict]) -> Path:
    """実行結果をJSONファイルに保存"""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_file = RESULTS_DIR / f"run_{mode}_{ts}.json"
    data = {
        "mode": mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_file


def run_daily(orchestrator: NexusV2Orchestrator) -> list[dict]:
    """日次実行: 分析 → 生成 → 配信"""
    logger.info("=== NEXUS V2 Daily Run ===")
    all_results = []

    # Step 1: 上位チャネルの市場分析
    logger.info("Step 1: Market Research (top channels)")
    research_results = orchestrator.run(mode="research")
    all_results.extend([r.to_dict() for r in research_results])

    # Step 2: アセット生成（市場分析結果に基づく）
    logger.info("Step 2: Content Creation")
    create_results = orchestrator.run(mode="create")
    all_results.extend([r.to_dict() for r in create_results])

    return all_results


def run_weekly(orchestrator: NexusV2Orchestrator) -> list[dict]:
    """週次実行: 全チャネル分析 → 議論 → 計画策定"""
    logger.info("=== NEXUS V2 Weekly Run ===")
    all_results = []

    # Step 1: 全チャネル市場分析
    logger.info("Step 1: Full Market Research")
    research_results = orchestrator.run(mode="research")
    all_results.extend([r.to_dict() for r in research_results])

    # Step 2: 戦略議論
    logger.info("Step 2: Strategy Debate")
    debate_results = orchestrator.run(mode="debate", focus="週次レビュー: 全チャネルの最適化と来週の生成計画")
    all_results.extend([r.to_dict() for r in debate_results])

    # Step 3: 議論結果に基づくアセット生成
    logger.info("Step 3: Content Creation (debate-informed)")
    create_results = orchestrator.run(mode="create")
    all_results.extend([r.to_dict() for r in create_results])

    return all_results


def run_create(orchestrator: NexusV2Orchestrator) -> list[dict]:
    """生成のみ"""
    logger.info("=== NEXUS V2 Create Run ===")
    results = orchestrator.run(mode="create")
    return [r.to_dict() for r in results]


def run_status(orchestrator: NexusV2Orchestrator) -> list[dict]:
    """状態確認のみ（API呼び出しなし）"""
    logger.info("=== NEXUS V2 Status Check ===")
    results = orchestrator.run(mode="status")
    return [r.to_dict() for r in results]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    orchestrator = NexusV2Orchestrator()

    runners = {
        "daily": run_daily,
        "weekly": run_weekly,
        "create": run_create,
        "status": run_status,
    }

    runner = runners.get(mode)
    if not runner:
        print(f"Unknown mode: {mode}")
        print(f"Available modes: {', '.join(runners.keys())}")
        sys.exit(1)

    results = runner(orchestrator)

    # 結果をファイルに保存
    output_file = save_run_result(mode, results)

    # サマリー出力
    print("\n" + "=" * 60)
    print(f"NEXUS V2 — {mode} 完了")
    print("=" * 60)

    total_assets = sum(r.get("assets_created", 0) for r in results)
    total_distributed = sum(r.get("assets_distributed", 0) for r in results)
    total_debates = sum(r.get("debates_held", 0) for r in results)
    est_revenue = max((r.get("estimated_monthly_revenue", 0) for r in results), default=0)

    print(f"  生成アセット: {total_assets}")
    print(f"  配信タスク: {total_distributed}")
    print(f"  議論: {total_debates}")
    print(f"  推定月間収益: ¥{est_revenue:,}")
    print(f"  結果ファイル: {output_file}")
    print(f"  システム状態: {orchestrator.state.to_dict()}")

    # エラーがあればexit code 1
    errors = [e for r in results for e in r.get("errors", [])]
    if errors:
        print(f"\n  エラー ({len(errors)}件):")
        for e in errors:
            print(f"    ! {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
