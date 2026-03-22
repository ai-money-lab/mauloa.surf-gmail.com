"""Run the full CITS trading pipeline for all tickers in the watchlist.

Usage:
    python -m cits.scripts.run_watchlist [--config cits/config.yml] [--date 2026-03-22]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("cits.scripts.run_watchlist")


def run_watchlist(config_path: str, date: str | None = None) -> list[dict]:
    """Run the trading pipeline for every ticker in the watchlist.

    Parameters
    ----------
    config_path:
        Path to the YAML configuration file.
    date:
        Analysis date (YYYY-MM-DD).  Defaults to today.

    Returns
    -------
    list[dict]
        Pipeline results for each ticker.
    """
    from cits.config_loader import load_config

    graph_config = load_config(config_path)
    run_date = date or datetime.now().strftime("%Y-%m-%d")

    watchlist = graph_config.get("watchlist", [])
    if not watchlist:
        logger.warning("Watchlist is empty in %s", config_path)
        return []

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error("ANTHROPIC_API_KEY is not set")
        sys.exit(1)

    from cits.core.graph.trading_graph import TradingGraph

    graph = TradingGraph(config=graph_config)

    results: list[dict] = []
    succeeded = 0
    failed = 0

    logger.info("=" * 60)
    logger.info("CITS Watchlist Run")
    logger.info("  Date: %s", run_date)
    logger.info("  Mode: %s", "paper" if graph_config.get("paper_mode", True) else "live")
    logger.info("  Tickers: %d", len(watchlist))
    logger.info("=" * 60)

    for ticker in watchlist:
        logger.info("--- Processing ticker: %s ---", ticker)
        try:
            result = graph.run(ticker=str(ticker), date=run_date)
            results.append(result)
            action = result.get("final_decision", {}).get("final_action", "N/A")
            approved = result.get("final_decision", {}).get("approved", "N/A")
            logger.info(
                "Ticker %s: action=%s approved=%s", ticker, action, approved
            )
            succeeded += 1
        except Exception:
            logger.exception("Failed to process ticker %s", ticker)
            results.append({"ticker": ticker, "error": True})
            failed += 1

    # Summary
    logger.info("=" * 60)
    logger.info("Watchlist Run Complete")
    logger.info("  Succeeded: %d / %d", succeeded, len(watchlist))
    logger.info("  Failed:    %d / %d", failed, len(watchlist))
    logger.info("=" * 60)

    # Save summary
    log_dir = graph_config.get("log_dir", "cits/logs")
    summary_dir = Path(log_dir) / "agent_decisions"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_file = summary_dir / f"watchlist_{run_date}.json"

    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    logger.info("Summary saved to %s", summary_file)

    return results


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run CITS trading pipeline for all watchlist tickers"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="cits/config.yml",
        help="Path to config.yml (default: cits/config.yml)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Analysis date YYYY-MM-DD (default: today)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    run_watchlist(config_path=args.config, date=args.date)


if __name__ == "__main__":
    main()
