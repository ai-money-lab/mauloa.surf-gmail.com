"""TradingGraph – full 5-stage CITS trading pipeline orchestrator.

Stages
------
I.   Analyst team (Fundamental, Sentiment, News, Technical) – run in parallel
II.  Research team: Bull & Bear researchers analyse → DebateEngine debate
III. Trader: makes buy/sell/hold decision from debate result
IV.  Risk Manager: evaluates the proposed trade
V.   Fund Manager: final approval / rejection

Usage
-----
    python -m cits.core.graph.trading_graph --paper --ticker 7203
"""

import argparse
import json
import logging
from datetime import datetime, timezone

from ..agents.fundamental import FundamentalAnalyst
from ..agents.sentiment import SentimentAnalyst
from ..agents.news import NewsAnalyst
from ..agents.technical import TechnicalAnalyst
from ..agents.bull_researcher import BullResearcher
from ..agents.bear_researcher import BearResearcher
from ..agents.trader import Trader
from ..agents.risk_manager import RiskManager
from ..agents.fund_manager import FundManager
from ..context_builder import ContextBuilder
from ..debate.debate_engine import DebateEngine
from cits.risk.position_sizer import PositionSizer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict = {
    "llm_provider": "anthropic",
    "deep_think_llm": "claude-opus-4-6",
    "quick_think_llm": "claude-sonnet-4-20250514",
    "max_debate_rounds": 2,
    "paper_mode": False,
    "log_dir": "cits/logs",
    "analyst_temperature": 0.3,
    "debate_temperature": 0.4,
    "trader_temperature": 0.2,
}


class TradingGraph:
    """Orchestrates the full 5-stage CITS trading pipeline.

    Parameters
    ----------
    config : dict, optional
        Override any key in ``DEFAULT_CONFIG``.  Unspecified keys fall back
        to their defaults.
    """

    def __init__(self, config: dict = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.logger = logging.getLogger("cits.graph.trading_graph")

        # Stage I – analyst team
        self.fundamental_analyst = FundamentalAnalyst()
        self.sentiment_analyst = SentimentAnalyst()
        self.news_analyst = NewsAnalyst()
        self.technical_analyst = TechnicalAnalyst()

        # Stage II – research team
        self.bull_researcher = BullResearcher()
        self.bear_researcher = BearResearcher()
        self.debate_engine = DebateEngine(
            max_rounds=self.config["max_debate_rounds"]
        )

        # Stage III–V – decision chain
        self.trader = Trader()
        self.risk_manager = RiskManager()
        self.fund_manager = FundManager()

        # Data enrichment & risk modules
        self.context_builder = ContextBuilder()
        self.position_sizer = PositionSizer()

        self.logger.info(
            "TradingGraph initialised: paper_mode=%s debate_rounds=%d",
            self.config["paper_mode"],
            self.config["max_debate_rounds"],
        )

    # ------------------------------------------------------------------
    # Stage runners
    # ------------------------------------------------------------------

    def _run_stage_1_analysts(self, context: dict) -> dict:
        """Stage I: Run the four analyst agents.

        Currently sequential; structured so each call is independent and
        can be converted to ``asyncio.gather`` / thread-pool dispatch.
        """
        self.logger.info("=== Stage I: Analyst Team ===")

        # Each analyst receives the same base context
        # Future: run via concurrent.futures.ThreadPoolExecutor
        fundamental = self.fundamental_analyst.analyze(context)
        self.logger.info("Fundamental analysis complete")

        sentiment = self.sentiment_analyst.analyze(context)
        self.logger.info("Sentiment analysis complete")

        news = self.news_analyst.analyze(context)
        self.logger.info("News analysis complete")

        technical = self.technical_analyst.analyze(context)
        self.logger.info("Technical analysis complete")

        analyst_reports = {
            "fundamental": fundamental,
            "sentiment": sentiment,
            "news": news,
            "technical": technical,
        }
        self.logger.info("Stage I complete: all analyst reports collected")
        return analyst_reports

    def _run_stage_2_research(self, context: dict, analyst_reports: dict) -> dict:
        """Stage II: Bull/Bear research + debate."""
        self.logger.info("=== Stage II: Research Team & Debate ===")

        research_context = {**context, "analyst_reports": analyst_reports}

        bull_case = self.bull_researcher.analyze(research_context)
        self.logger.info("Bull researcher complete")

        bear_case = self.bear_researcher.analyze(research_context)
        self.logger.info("Bear researcher complete")

        debate_result = self.debate_engine.run_debate(
            bull_case=bull_case,
            bear_case=bear_case,
            analyst_reports=analyst_reports,
        )
        self.logger.info(
            "Debate complete: winner=%s score=%d",
            debate_result["winner"],
            debate_result["final_score"],
        )

        return {
            "bull_case": bull_case,
            "bear_case": bear_case,
            "debate_result": debate_result,
        }

    def _run_stage_3_trader(self, context: dict, research: dict) -> dict:
        """Stage III: Trader makes buy/sell/hold decision."""
        self.logger.info("=== Stage III: Trader ===")

        trader_context = {**context, **research}
        trade_decision = self.trader.analyze(trader_context)
        self.logger.info(
            "Trader decision: %s", trade_decision.get("action", "unknown")
        )
        return trade_decision

    def _run_stage_4_risk(self, context: dict, trade_decision: dict) -> dict:
        """Stage IV: Risk Manager evaluates the trade."""
        self.logger.info("=== Stage IV: Risk Manager ===")

        # Calculate recommended position size
        position_sizing: dict = {}
        try:
            entry_price = float(trade_decision.get("entry_price", 0))
            stop_loss = float(trade_decision.get("stop_loss", 0))
            if entry_price > 0 and stop_loss > 0 and entry_price != stop_loss:
                position_sizing = self.position_sizer.calculate_size(
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                )
                self.logger.info(
                    "Position sizing: %d units, notional ¥%.0f",
                    position_sizing.get("position_size", 0),
                    position_sizing.get("notional_value", 0),
                )
            else:
                self.logger.info(
                    "Position sizing skipped — entry_price or stop_loss not provided"
                )
        except Exception:
            self.logger.exception("PositionSizer failed — continuing without sizing")

        risk_context = {
            **context,
            "trade_decision": trade_decision,
            "position_sizing": position_sizing,
        }
        risk_assessment = self.risk_manager.analyze(risk_context)
        risk_assessment["position_sizing"] = position_sizing
        self.logger.info(
            "Risk assessment: approved=%s",
            risk_assessment.get("approved", "unknown"),
        )
        return risk_assessment

    def _run_stage_5_fund_manager(
        self,
        context: dict,
        trade_decision: dict,
        risk_assessment: dict,
    ) -> dict:
        """Stage V: Fund Manager gives final approval."""
        self.logger.info("=== Stage V: Fund Manager ===")

        fm_context = {
            **context,
            "trade_decision": trade_decision,
            "risk_assessment": risk_assessment,
            "circuit_breaker": context.get("circuit_breaker", {}),
        }
        final_decision = self.fund_manager.analyze(fm_context)
        self.logger.info(
            "Fund Manager decision: %s",
            final_decision.get("final_action", "unknown"),
        )
        return final_decision

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, ticker: str, date: str = None) -> dict:
        """Execute the full 5-stage trading pipeline.

        Parameters
        ----------
        ticker : str
            Stock ticker symbol (e.g. ``"7203"`` for Toyota on TSE).
        date : str, optional
            Analysis date in ISO format (``YYYY-MM-DD``).  Defaults to
            today (UTC).

        Returns
        -------
        dict
            Complete pipeline output including all stage results,
            ``final_decision``, ``paper_mode`` flag, and ``timestamp``.
        """
        run_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.logger.info(
            "Pipeline start: ticker=%s date=%s paper_mode=%s",
            ticker,
            run_date,
            self.config["paper_mode"],
        )

        context = {
            "ticker": ticker,
            "date": run_date,
            "paper_mode": self.config["paper_mode"],
            "config": self.config,
        }

        # Enrich context with real market data
        self.logger.info("Enriching context via ContextBuilder...")
        try:
            enriched = self.context_builder.build(ticker, run_date)
            context.update(enriched)
            self.logger.info("Context enriched with %d data keys", len(enriched))
        except Exception:
            self.logger.exception(
                "ContextBuilder.build() failed — continuing with base context"
            )

        # Stage I
        analyst_reports = self._run_stage_1_analysts(context)

        # Stage II
        research = self._run_stage_2_research(context, analyst_reports)

        # Stage III
        trade_decision = self._run_stage_3_trader(context, research)

        # Stage IV
        risk_assessment = self._run_stage_4_risk(context, trade_decision)

        # Stage V
        final_decision = self._run_stage_5_fund_manager(
            context, trade_decision, risk_assessment
        )

        timestamp = datetime.now(timezone.utc).isoformat()

        pipeline_result = {
            "ticker": ticker,
            "date": run_date,
            "paper_mode": self.config["paper_mode"],
            "timestamp": timestamp,
            "stages": {
                "stage_1_analysts": analyst_reports,
                "stage_2_research": research,
                "stage_3_trader": trade_decision,
                "stage_4_risk": risk_assessment,
                "stage_5_fund_manager": final_decision,
            },
            "final_decision": final_decision,
        }

        self.logger.info(
            "Pipeline complete: ticker=%s final_action=%s",
            ticker,
            final_decision.get("final_action", "unknown"),
        )

        return pipeline_result


# ---------------------------------------------------------------------------
# CLI entry point  (python -m cits.core.graph.trading_graph)
# ---------------------------------------------------------------------------


def main():
    """Parse CLI arguments and run the trading pipeline."""
    parser = argparse.ArgumentParser(
        description="CITS Trading Pipeline – 5-stage AI trading system",
    )
    parser.add_argument(
        "--ticker",
        required=True,
        help="Stock ticker symbol (e.g. 7203)",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Analysis date (YYYY-MM-DD), defaults to today",
    )
    parser.add_argument(
        "--paper",
        action="store_true",
        default=False,
        help="Run in paper-trading mode (no real orders)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    config = {**DEFAULT_CONFIG, "paper_mode": args.paper}
    graph = TradingGraph(config=config)
    result = graph.run(ticker=args.ticker, date=args.date)

    # Print summary to stdout
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
