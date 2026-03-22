"""CITS Main Entry Point

Usage:
    python -m cits.main --mode paper --ticker 7203
    python -m cits.main --mode paper --ticker 7203 --date 2026-03-22
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "logs", "cits.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("cits.main")


def main():
    parser = argparse.ArgumentParser(description="CITS - Claude Intelligence Trading System")
    parser.add_argument("--ticker", type=str, required=True, help="銘柄コード (例: 7203)")
    parser.add_argument("--date", type=str, default=None, help="分析日 (YYYY-MM-DD, デフォルト: 今日)")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["paper", "live"],
        default="paper",
        help="取引モード (paper=ペーパートレード, live=実弾)",
    )
    parser.add_argument("--verbose", action="store_true", help="詳細ログ出力")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    date = args.date or datetime.now().strftime("%Y-%m-%d")

    logger.info("=" * 60)
    logger.info("CITS - Claude Intelligence Trading System")
    logger.info(f"  銘柄: {args.ticker}")
    logger.info(f"  日付: {date}")
    logger.info(f"  モード: {args.mode}")
    logger.info("=" * 60)

    if args.mode == "live":
        logger.warning("⚠ 実弾モード - 実際の注文が執行されます")
        confirm = input("続行しますか？ (yes/no): ")
        if confirm.lower() != "yes":
            logger.info("中止しました")
            return

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error("ANTHROPIC_API_KEY が設定されていません")
        sys.exit(1)

    from cits.core.graph.trading_graph import TradingGraph

    config = {
        "llm_provider": "anthropic",
        "deep_think_llm": "claude-opus-4-6",
        "quick_think_llm": "claude-sonnet-4-20250514",
        "max_debate_rounds": 2,
        "mode": args.mode,
    }

    graph = TradingGraph(config=config)
    result = graph.run(ticker=args.ticker, date=date)

    # Output result
    logger.info("=" * 60)
    logger.info("パイプライン完了")
    logger.info(f"  最終判断: {result.get('final_decision', {}).get('action', 'N/A')}")
    logger.info(f"  承認: {result.get('final_decision', {}).get('approved', 'N/A')}")
    logger.info("=" * 60)

    # Save full result
    output_dir = os.path.join(os.path.dirname(__file__), "logs", "agent_decisions")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{args.ticker}_{date}.json")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"詳細結果: {output_file}")

    # Paper trade recording
    if args.mode == "paper" and result.get("final_decision", {}).get("approved"):
        _record_paper_trade(args.ticker, date, result)

    return result


def _record_paper_trade(ticker: str, date: str, result: dict):
    """ペーパートレード結果をSQLiteに記録"""
    try:
        from cits.risk.win_rate_engine import WinRateEngine

        engine = WinRateEngine()
        decision = result.get("final_decision", {})
        engine.record_trade(
            {
                "ticker": ticker,
                "date": date,
                "action": decision.get("action", "hold"),
                "size": decision.get("final_size", 0),
                "reasoning": decision.get("reasoning", ""),
                "mode": "paper",
            }
        )
        logger.info("ペーパートレード記録完了")
    except Exception as e:
        logger.warning(f"ペーパートレード記録失敗: {e}")


if __name__ == "__main__":
    main()
