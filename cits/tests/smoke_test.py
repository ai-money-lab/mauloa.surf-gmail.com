#!/usr/bin/env python3
"""
CITS スモークテスト — 全モジュール・全クラスの自動検証

目的:
  コードを変更するたびに実行し、import不能・クラス消失・シグネチャ不整合を即座に検出する。
  「読んで確認した」ではなく「実行して確認した」を保証する。

使い方:
  python cits/tests/smoke_test.py
"""

import importlib
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path

# プロジェクトルートをsys.pathに追加（PYTHONPATHに依存しない）
_project_root = str(Path(__file__).resolve().parents[2])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


@dataclass
class TestResult:
    name: str
    passed: bool
    error: str = ""


# ============================================================
# 1. 全モジュールのimport検証
# ============================================================
MODULES = [
    # Core
    "cits",
    "cits.main",
    "cits.config_loader",
    "cits.core",
    "cits.core.context_builder",
    # Agents
    "cits.core.agents",
    "cits.core.agents.base_agent",
    "cits.core.agents.fundamental",
    "cits.core.agents.sentiment",
    "cits.core.agents.news",
    "cits.core.agents.technical",
    "cits.core.agents.trader",
    "cits.core.agents.risk_manager",
    "cits.core.agents.fund_manager",
    "cits.core.agents.bull_researcher",
    "cits.core.agents.bear_researcher",
    # Debate
    "cits.core.debate",
    "cits.core.debate.debate_engine",
    # Graph
    "cits.core.graph",
    "cits.core.graph.trading_graph",
    # Japan
    "cits.japan",
    "cits.japan.data",
    "cits.japan.data.yfinance_jp",
    "cits.japan.data.jquants_api",
    "cits.japan.data.jpx_flows",
    "cits.japan.data.jpx_shorts",
    "cits.japan.data.jpx_margin",
    "cits.japan.data.edinet_api",
    "cits.japan.broker",
    "cits.japan.broker.kabu_api",
    "cits.japan.broker.tachibana_api",
    "cits.japan.broker.software_oco",
    "cits.japan.voice_tracker",
    "cits.japan.voice_tracker.boj_scorer",
    "cits.japan.voice_tracker.fomc_scorer",
    "cits.japan.voice_tracker.trump_tracker",
    # Risk
    "cits.risk",
    "cits.risk.circuit_breaker",
    "cits.risk.crash_detector",
    "cits.risk.position_sizer",
    "cits.risk.win_rate_engine",
    # Portfolio
    "cits.portfolio",
    "cits.portfolio.paper_portfolio",
    "cits.portfolio.portfolio_manager",
    # Execution
    "cits.execution",
    "cits.execution.bridge",
    # Scripts
    "cits.scripts",
    "cits.scripts.weekly_report",
    "cits.scripts.run_watchlist",
]

# ============================================================
# 2. クラスの存在検証 — (モジュール, クラス名) のペア
# ============================================================
CLASSES = [
    # config_loaderは関数ベース（load_config）。クラスなし。
    # ("cits.config_loader", "ConfigLoader"),
    ("cits.core.context_builder", "ContextBuilder"),
    ("cits.core.agents.base_agent", "BaseAgent"),
    ("cits.core.agents.fundamental", "FundamentalAnalyst"),
    ("cits.core.agents.sentiment", "SentimentAnalyst"),
    ("cits.core.agents.news", "NewsAnalyst"),
    ("cits.core.agents.technical", "TechnicalAnalyst"),
    ("cits.core.agents.trader", "Trader"),
    ("cits.core.agents.risk_manager", "RiskManager"),
    ("cits.core.agents.fund_manager", "FundManager"),
    ("cits.core.agents.bull_researcher", "BullResearcher"),
    ("cits.core.agents.bear_researcher", "BearResearcher"),
    ("cits.core.debate.debate_engine", "DebateEngine"),
    ("cits.core.graph.trading_graph", "TradingGraph"),
    ("cits.japan.data.yfinance_jp", "JapanStockData"),
    ("cits.japan.data.jquants_api", "JQuantsClient"),
    ("cits.japan.data.jpx_flows", "JPXFlowTracker"),
    ("cits.japan.data.jpx_shorts", "JPXShortTracker"),
    ("cits.japan.data.jpx_margin", "JPXMarginTracker"),
    ("cits.japan.data.edinet_api", "EdinetClient"),
    ("cits.japan.broker.kabu_api", "KabuStationAPI"),
    ("cits.japan.broker.tachibana_api", "TachibanaAPI"),
    ("cits.japan.broker.software_oco", "SoftwareOCO"),
    ("cits.japan.voice_tracker.boj_scorer", "BOJScorer"),
    ("cits.japan.voice_tracker.fomc_scorer", "FOMCScorer"),
    ("cits.japan.voice_tracker.trump_tracker", "TrumpTracker"),
    ("cits.risk.circuit_breaker", "CircuitBreaker"),
    ("cits.risk.crash_detector", "CrashDetector"),
    ("cits.risk.position_sizer", "PositionSizer"),
    ("cits.risk.win_rate_engine", "WinRateEngine"),
    ("cits.portfolio.paper_portfolio", "PaperPortfolio"),
    ("cits.portfolio.portfolio_manager", "PortfolioManager"),
    ("cits.execution.bridge", "ExecutionBridge"),
]

# ============================================================
# 3. メソッドの存在検証 — (モジュール, クラス名, メソッド名) のトリプル
#    ※主要な公開メソッドのみ。必要に応じて追加すること。
# ============================================================
METHODS: list[tuple[str, str, str]] = [
    # 追加例:
    # ("cits.core.context_builder", "ContextBuilder", "build"),
]


def run_tests() -> list[TestResult]:
    results: list[TestResult] = []

    # --- Module imports ---
    print("=" * 60)
    print("Phase 1: Module Import 検証")
    print("=" * 60)
    for mod_name in MODULES:
        try:
            importlib.import_module(mod_name)
            results.append(TestResult(f"import {mod_name}", True))
            print(f"  ✅ {mod_name}")
        except Exception as e:
            results.append(TestResult(f"import {mod_name}", False, str(e)))
            print(f"  ❌ {mod_name}: {e}")

    # --- Class existence ---
    print()
    print("=" * 60)
    print("Phase 2: Class 存在検証")
    print("=" * 60)
    for mod_name, cls_name in CLASSES:
        test_name = f"{mod_name}.{cls_name}"
        try:
            mod = importlib.import_module(mod_name)
            cls = getattr(mod, cls_name, None)
            if cls is None:
                results.append(TestResult(test_name, False, f"Class '{cls_name}' not found in {mod_name}"))
                print(f"  ❌ {test_name}: クラスが存在しない")
            elif not inspect.isclass(cls):
                results.append(TestResult(test_name, False, f"'{cls_name}' is not a class"))
                print(f"  ❌ {test_name}: クラスではない")
            else:
                results.append(TestResult(test_name, True))
                print(f"  ✅ {test_name}")
        except Exception as e:
            results.append(TestResult(test_name, False, str(e)))
            print(f"  ❌ {test_name}: {e}")

    # --- Method existence & signature ---
    if METHODS:
        print()
        print("=" * 60)
        print("Phase 3: Method シグネチャ検証")
        print("=" * 60)
        for mod_name, cls_name, method_name in METHODS:
            test_name = f"{mod_name}.{cls_name}.{method_name}"
            try:
                mod = importlib.import_module(mod_name)
                cls = getattr(mod, cls_name)
                method = getattr(cls, method_name, None)
                if method is None:
                    results.append(TestResult(test_name, False, f"Method '{method_name}' not found"))
                    print(f"  ❌ {test_name}: メソッドが存在しない")
                else:
                    sig = inspect.signature(method)
                    results.append(TestResult(test_name, True))
                    print(f"  ✅ {test_name}{sig}")
            except Exception as e:
                results.append(TestResult(test_name, False, str(e)))
                print(f"  ❌ {test_name}: {e}")

    return results


def main() -> int:
    print()
    print("🔍 CITS スモークテスト開始")
    print()

    results = run_tests()

    # --- Summary ---
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)

    print()
    print("=" * 60)
    print(f"結果: {passed}/{total} パス, {failed} 失敗")
    print("=" * 60)

    if failed > 0:
        print()
        print("❌ 失敗一覧:")
        for r in results:
            if not r.passed:
                print(f"  - {r.name}: {r.error}")
        print()
        print("⛔ スモークテスト失敗 — 修正してから再実行してください")
        return 1
    else:
        print()
        print("✅ 全テストパス — 問題なし")
        return 0


if __name__ == "__main__":
    sys.exit(main())
