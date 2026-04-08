"""CITS ペーパートレード一括実行

全ウォッチリストETFに対してフルAIパイプラインをペーパーモードで実行する。

Usage:
    python -m cits.scripts.run_paper_all
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("cits.run_paper_all")

# CIS式成功方程式で選定された9 ETF
WATCHLIST = [
    ("2644", "GX半導体ETF"),
    ("1540", "金ETF"),
    ("1570", "日経レバレッジ2倍"),
    ("1489", "日経高配当50"),
    ("1321", "日経225 ETF"),
    ("1357", "日経ダブルインバース"),
    ("1343", "REIT ETF"),
    ("1306", "TOPIX ETF"),
    ("2558", "S&P500 ETF"),
]


def main():
    from cits.config_loader import load_config
    from cits.core.graph.trading_graph import TradingGraph

    date_str = datetime.now().strftime("%Y-%m-%d")
    config = load_config()
    config["paper_mode"] = True

    logger.info("=" * 60)
    logger.info("CITS ペーパートレード一括実行")
    logger.info(f"  日付: {date_str}")
    logger.info(f"  銘柄数: {len(WATCHLIST)}")
    logger.info("=" * 60)

    results = []
    for ticker, name in WATCHLIST:
        logger.info(f"\n{'─' * 40}")
        logger.info(f"分析開始: {ticker} ({name})")
        logger.info(f"{'─' * 40}")

        try:
            graph = TradingGraph(config=config)
            result = graph.run(ticker=ticker, date=date_str)

            decision = result.get("final_decision", {})
            action = decision.get("final_action", "N/A")
            approved = decision.get("approved", False)

            results.append({
                "ticker": ticker,
                "name": name,
                "action": action,
                "approved": approved,
            })

            logger.info(f"  → {ticker} ({name}): {action} (承認: {approved})")

        except Exception as e:
            logger.error(f"  → {ticker} ({name}): エラー - {e}")
            results.append({
                "ticker": ticker,
                "name": name,
                "action": "error",
                "approved": False,
            })

    # サマリー
    logger.info(f"\n{'=' * 60}")
    logger.info("ペーパートレード結果サマリー")
    logger.info(f"{'=' * 60}")
    for r in results:
        status = "✅" if r["approved"] else "⏸"
        logger.info(f"  {status} {r['ticker']} ({r['name']}): {r['action']}")

    buys = [r for r in results if r["action"] == "buy" and r["approved"]]
    sells = [r for r in results if r["action"] == "sell" and r["approved"]]
    holds = [r for r in results if r["action"] == "hold"]

    logger.info(f"\n  買いシグナル: {len(buys)}銘柄")
    logger.info(f"  売りシグナル: {len(sells)}銘柄")
    logger.info(f"  様子見: {len(holds)}銘柄")
    logger.info(f"{'=' * 60}")


if __name__ == "__main__":
    main()
