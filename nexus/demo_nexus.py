#!/usr/bin/env python3
"""
NEXUS デモスクリプト — 全自律ループの動作サンプル

使い方:
  ANTHROPIC_API_KEY=xxx python -m nexus.demo_nexus [mode]

モード:
  crawl      - 収益機会を発見
  trial      - 機会をTRY（商品生成→評価）
  autonomous - 完全自律ループ（CRAWL→TRY→DEBATE→EVOLVE）
  stats      - 現在の統計表示
"""

from __future__ import annotations

import json
import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("nexus.demo")


def run_crawl_demo():
    """Step 1: 収益機会を発見する."""
    from nexus.orchestrator.nexus_core import NexusOrchestrator

    print("\n" + "=" * 60)
    print("  NEXUS DEMO — CRAWL MODE (収益機会探索)")
    print("=" * 60)

    data_dir = Path("nexus/data")
    orchestrator = NexusOrchestrator(data_dir=data_dir)
    result = orchestrator.run(mode="crawl")

    print(f"\n{'─' * 40}")
    print(f"  発見した機会: {result['opportunities_found']}件")
    print(f"{'─' * 40}")

    for opp in result.get("top_opportunities", []):
        print(f"\n  ■ {opp['title']}")
        print(f"    種別: {opp['opportunity_type']}")
        print(f"    想定月収: {opp['estimated_revenue']:,}円")
        print(f"    実現性: {opp['feasibility']}")
        print(f"    確度: {opp['confidence']:.0%}")
        if opp.get("platform"):
            print(f"    プラットフォーム: {opp['platform']}")

    print(f"\n  状態: {json.dumps(result.get('state', {}), ensure_ascii=False, indent=2)}")
    return result


def run_trial_demo():
    """Step 2: 発見した機会を実際にTRYする."""
    from nexus.orchestrator.nexus_core import NexusOrchestrator

    print("\n" + "=" * 60)
    print("  NEXUS DEMO — TRIAL MODE (実際にTRY)")
    print("=" * 60)

    data_dir = Path("nexus/data")
    orchestrator = NexusOrchestrator(data_dir=data_dir)
    result = orchestrator.run(mode="trial")

    trials = result.get("trials", [])
    stats = result.get("stats", {})

    print(f"\n{'─' * 40}")
    print(f"  Trial結果: {len(trials)}件実行")
    print(f"  成功率: {stats.get('success_rate', 0):.0%}")
    print(f"{'─' * 40}")

    for trial in trials:
        emoji = "✓" if trial["result"] == "success" else "✗" if trial["result"] == "failure" else "△"
        print(f"\n  {emoji} {trial['opportunity_title']}")
        print(f"    結果: {trial['result']}")
        if trial.get("evaluation"):
            score = trial["evaluation"].get("total_score", "?")
            print(f"    スコア: {score}/50")
        if trial.get("product_id"):
            print(f"    生成商品ID: {trial['product_id']}")
        if trial.get("lessons"):
            print(f"    学び: {', '.join(trial['lessons'][:3])}")

    return result


def run_autonomous_demo():
    """Step 3: 完全自律ループ."""
    from nexus.orchestrator.nexus_core import NexusOrchestrator

    print("\n" + "=" * 60)
    print("  NEXUS DEMO — AUTONOMOUS MODE (完全自律ループ)")
    print("  CRAWL → TRY → DEBATE → EVOLVE")
    print("=" * 60)

    data_dir = Path("nexus/data")
    orchestrator = NexusOrchestrator(data_dir=data_dir)
    result = orchestrator.run(mode="autonomous", num_cycles=1)

    state = result.get("state", {})
    loops = result.get("loops", [])

    print(f"\n{'─' * 40}")
    print(f"  完了ループ: {len(loops)}")
    print(f"{'─' * 40}")

    for i, loop in enumerate(loops):
        print(f"\n  === ループ {i + 1} ===")

        # Crawl結果
        crawl = loop.get("crawl", {})
        print(f"  [CRAWL] 発見: {crawl.get('opportunities_found', 0)}件")

        # Trial結果
        trials = loop.get("trials", [])
        successes = [t for t in trials if t.get("result") == "success"]
        failures = [t for t in trials if t.get("result") != "success"]
        print(f"  [TRIAL] 実行: {len(trials)}, 成功: {len(successes)}, 失敗: {len(failures)}")

        # Debate結果
        debates = loop.get("debates", [])
        print(f"  [DEBATE] 議論: {len(debates)}件")
        for d in debates[:2]:
            print(f"    → {d.get('consensus', '?')[:50]}...")

        # Evolve結果
        evolve = loop.get("evolve", {})
        gen = evolve.get("generation", {})
        print(f"  [EVOLVE] 世代: {gen.get('gen_number', '?')}, パターン: {gen.get('patterns_count', 0)}")

    print(f"\n{'─' * 40}")
    print("  最終状態:")
    print(f"    サイクル完了: {state.get('cycles_completed', 0)}")
    print(f"    Trial実行: {state.get('trials_run', 0)}")
    print(f"    Trial成功: {state.get('trials_succeeded', 0)}")
    print(f"    発見パターン: {state.get('patterns_discovered', 0)}")
    print(f"    推定収益: {state.get('total_revenue_potential', 0):,.0f}円")
    print(f"{'─' * 40}")
    return result


def run_stats_demo():
    """現在の統計を表示."""
    from nexus.evolution.evolver import Evolver

    print("\n" + "=" * 60)
    print("  NEXUS DEMO — STATS (現在の統計)")
    print("=" * 60)

    data_dir = Path("nexus/data")
    evolver = Evolver(data_dir=data_dir / "evolution")
    stats = evolver.get_evolution_stats()

    print("\n  進化統計:")
    print(f"    現在の世代: {stats['current_generation']}")
    print(f"    発見パターン: {stats['total_patterns']}")
    print(f"    複製数: {stats['total_replications']}")

    if evolver.patterns:
        print("\n  成功パターン:")
        for p in evolver.get_top_patterns(limit=5):
            print(f"    ■ {p.title} — {p.revenue:,}円 (複製:{p.replication_count})")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "crawl"

    modes = {
        "crawl": run_crawl_demo,
        "trial": run_trial_demo,
        "autonomous": run_autonomous_demo,
        "stats": run_stats_demo,
    }

    if mode not in modes:
        print(f"Unknown mode: {mode}")
        print(f"Available: {', '.join(modes.keys())}")
        sys.exit(1)

    try:
        modes[mode]()
        print("\n  NEXUS demo completed successfully.\n")
    except Exception as e:
        logger.error("Demo failed: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
