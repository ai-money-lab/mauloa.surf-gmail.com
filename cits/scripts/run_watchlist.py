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

import yaml

logger = logging.getLogger("cits.scripts.run_watchlist")


def load_config(config_path: str) -> dict:
    """Load and return the YAML configuration file."""
    path = Path(config_path)
    if not path.exists():
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


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
    config = load_config(config_path)
    run_date = date or datetime.now().strftime("%Y-%m-%d")

    watchlist = config.get("trading", {}).get("watchlist", [])
    if not watchlist:
        logger.warning("Watchlist is empty in %s", config_path)
        return []

    llm_config = config.get("llm", {})
    trading_config = config.get("trading", {})

    graph_config = {
        "llm_provider": llm_config.get("provider", "anthropic"),
        "deep_think_llm": llm_config.get("deep_think", "claude-opus-4-6"),
        "quick_think_llm": llm_config.get("quick_think", "claude-sonnet-4-20250514"),
        "analyst_temperature": llm_config.get("analyst_temperature", 0.3),
        "debate_temperature": llm_config.get("debate_temperature", 0.4),
        "trader_temperature": llm_config.get("trader_temperature", 0.2),
        "max_debate_rounds": trading_config.get("max_debate_rounds", 2),
        "mode": trading_config.get("mode", "paper"),
        "paper_mode": trading_config.get("mode", "paper") == "paper",
    }

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
    logger.info("  Mode: %s", trading_config.get("mode", "paper"))
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
    log_dir = config.get("logging", {}).get("log_dir", "cits/logs")
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
