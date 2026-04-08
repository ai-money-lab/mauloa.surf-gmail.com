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
from pathlib import Path

# .envファイルの自動読み込み
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenvがなくても環境変数で直接設定可能

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

    from cits.config_loader import load_config
    from cits.core.graph.trading_graph import TradingGraph

    config = load_config()
    # CLI args override config file
    config["paper_mode"] = args.mode == "paper"

    graph = TradingGraph(config=config)
    result = graph.run(ticker=args.ticker, date=date)

    # Output result
    logger.info("=" * 60)
    logger.info("パイプライン完了")
    logger.info(f"  最終判断: {result.get('final_decision', {}).get('final_action', 'N/A')}")
    logger.info(f"  承認: {result.get('final_decision', {}).get('approved', 'N/A')}")
    logger.info("=" * 60)

    # Save full result
    output_dir = os.path.join(os.path.dirname(__file__), "logs", "agent_decisions")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{args.ticker}_{date}.json")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"詳細結果: {output_file}")

    # --- Execution bridge ---
    final_decision = result.get("final_decision", {})
    approved = final_decision.get("approved", False)

    if approved:
        try:
            from cits.execution.bridge import ExecutionBridge

            broker = None
            if args.mode == "live":
                from cits.japan.broker.kabu_api import KabuStationAPI
                broker = KabuStationAPI()

            bridge = ExecutionBridge(broker=broker, mode=args.mode)
            exec_result = bridge.execute(result)

            logger.info("=" * 60)
            logger.info("執行結果:")
            logger.info(f"  ステータス: {exec_result.get('status', 'N/A')}")
            logger.info(f"  注文ID: {exec_result.get('order_id', 'N/A')}")
            logger.info(f"  約定価格: {exec_result.get('fill_price', 'N/A')}")
            logger.info(f"  数量: {exec_result.get('size', 'N/A')}")
            logger.info(f"  OCO: {exec_result.get('oco_status', 'N/A')}")
            logger.info("=" * 60)

            result["execution"] = exec_result

            # Portfolio summary
            summary = bridge.portfolio.get_portfolio_summary()
            logger.info("ポートフォリオ概要:")
            logger.info(f"  総資産: ¥{summary['total_equity']:,.0f}")
            logger.info(f"  現金: ¥{summary['cash']:,.0f}")
            logger.info(f"  ポジション数: {summary['positions_count']}")
            logger.info(f"  含み損益: ¥{summary['unrealized_pnl']:,.0f}")

            result["portfolio_summary"] = summary

        except Exception as e:
            logger.error(f"執行エラー: {e}")
            result["execution"] = {"status": "error", "message": str(e)}
    else:
        logger.info("最終判断: 未承認 — 執行なし")

    # Paper trade recording (legacy)
    if args.mode == "paper" and approved:
        _record_paper_trade(args.ticker, date, result)

    return result


def _record_paper_trade(ticker: str, date: str, result: dict):
    """ペーパートレード結果をSQLiteに記録"""
    try:
        from cits.risk.win_rate_engine import WinRateEngine

        engine = WinRateEngine()
        decision = result.get("final_decision", {})
        action = decision.get("final_action", decision.get("action", "hold"))
        size = int(decision.get("final_size", decision.get("size", 0)))
        entry = float(decision.get("entry_price", 0))
        engine.record_trade(
            {
                "symbol": ticker,
                "side": action if action in ("buy", "sell") else "hold",
                "qty": size if size > 0 else 100,
                "entry_price": entry,
                "exit_price": entry,  # paper trade — no exit yet
                "pnl": 0.0,
                "strategy": "cits_pipeline",
                "timestamp": date,
            }
        )
        logger.info("ペーパートレード記録完了")
    except Exception as e:
        logger.warning(f"ペーパートレード記録失敗: {e}")


if __name__ == "__main__":
    main()
