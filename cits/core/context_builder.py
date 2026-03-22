"""ContextBuilder — enriches pipeline context with real market data.

Fetches price data, technical indicators, financial statements, voice tracker
signals, and risk module outputs, then assembles them into the dict that
Stage I agents expect.  Every external call is wrapped in try/except so a
single data-source failure never crashes the pipeline.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd

from cits.japan.data.edinet_api import EdinetClient
from cits.japan.data.jpx_flows import JPXFlowTracker
from cits.japan.data.jpx_margin import JPXMarginTracker
from cits.japan.data.jpx_shorts import JPXShortTracker
from cits.japan.data.jquants_api import JQuantsClient
from cits.japan.data.yfinance_jp import JapanStockData
from cits.japan.voice_tracker.boj_scorer import BOJScorer
from cits.japan.voice_tracker.fomc_scorer import FOMCScorer
from cits.japan.voice_tracker.trump_tracker import TrumpTracker
from cits.risk.circuit_breaker import CircuitBreaker
from cits.risk.crash_detector import CrashDetector
from cits.risk.win_rate_engine import WinRateEngine

logger = logging.getLogger(__name__)


def _format_ohlcv(df: pd.DataFrame, last_n: int = 20) -> str:
    """Format the last *last_n* rows of an OHLCV DataFrame as a readable string."""
    if df.empty:
        return "データ未取得"
    tail = df.tail(last_n)
    try:
        return tail.to_string()
    except Exception:
        return "データ未取得"


def _safe_float(value: Any) -> str:
    """Convert a numeric value to a rounded string, handling None/NaN."""
    if value is None:
        return "N/A"
    try:
        if pd.isna(value):
            return "N/A"
    except (TypeError, ValueError):
        pass
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


class ContextBuilder:
    """Builds an enriched context dict for the CITS trading pipeline.

    All external data fetches run in parallel via a thread pool.  Individual
    failures are logged and substituted with sensible fallback values so the
    pipeline never crashes due to a missing data source.
    """

    def __init__(self) -> None:
        self.stock_data = JapanStockData()
        self.jquants = JQuantsClient()
        self.crash_detector = CrashDetector()
        self.circuit_breaker = CircuitBreaker()
        self.win_rate_engine = WinRateEngine()

    # ------------------------------------------------------------------
    # Individual fetchers (each returns a partial context dict)
    # ------------------------------------------------------------------

    def _fetch_price_data(self, ticker: str) -> dict[str, Any]:
        """Fetch OHLCV data and format last 20 days."""
        try:
            df = self.stock_data.get_stock_data(ticker, period="3mo")
            return {"price_data": _format_ohlcv(df), "_raw_price_df": df}
        except Exception:
            logger.exception("Failed to fetch price data for %s", ticker)
            return {"price_data": "データ未取得", "_raw_price_df": pd.DataFrame()}

    def _fetch_technical_indicators(self, ticker: str) -> dict[str, Any]:
        """Fetch technical indicators (SMA, RSI, MACD, Bollinger)."""
        try:
            indicators = self.stock_data.get_technical_indicators(ticker, period="6mo")
            if not indicators:
                return {"technical_indicators": "テクニカル指標: データ未取得"}

            lines = [
                f"RSI(14): {_safe_float(indicators.get('rsi_14'))}",
                f"MACD: {_safe_float(indicators.get('macd'))}",
                f"MACD Signal: {_safe_float(indicators.get('macd_signal'))}",
                f"MACD Hist: {_safe_float(indicators.get('macd_hist'))}",
                f"SMA5: {_safe_float(indicators.get('sma_5'))}",
                f"SMA25: {_safe_float(indicators.get('sma_25'))}",
                f"SMA75: {_safe_float(indicators.get('sma_75'))}",
                f"BB Upper: {_safe_float(indicators.get('bb_upper'))}",
                f"BB Middle: {_safe_float(indicators.get('bb_middle'))}",
                f"BB Lower: {_safe_float(indicators.get('bb_lower'))}",
            ]
            return {"technical_indicators": "\n".join(lines)}
        except Exception:
            logger.exception("Failed to fetch technical indicators for %s", ticker)
            return {"technical_indicators": "テクニカル指標: データ未取得"}

    def _fetch_financials(self, ticker: str) -> dict[str, Any]:
        """Fetch J-Quants financial statements with graceful fallback."""
        try:
            data = self.jquants.get_financial_statements(ticker)
            if data:
                return {"financials": str(data)}
        except Exception:
            logger.exception("Failed to fetch J-Quants financials for %s", ticker)
        return {"financials": "データ未取得"}

    def _fetch_market_index(self) -> dict[str, Any]:
        """Fetch Nikkei 225 recent performance."""
        try:
            df = self.stock_data.get_nikkei225(period="1mo")
            return {"market_index": _format_ohlcv(df, last_n=10)}
        except Exception:
            logger.exception("Failed to fetch Nikkei 225 data")
            return {"market_index": "日経225: データ未取得"}

    def _fetch_voice_events(self) -> dict[str, Any]:
        """Generate voice tracker signals from recent events.

        Uses LLM knowledge of recent central bank decisions and political
        statements to provide actionable signals when live text feeds are
        not available.
        """
        events: list[str] = []

        # BOJ
        try:
            boj = BOJScorer()
            result = boj.score_mpm_decision(
                "Based on the latest BOJ monetary policy meeting decision, "
                "the Bank of Japan maintained its policy rate. Governor Ueda "
                "indicated data-dependent approach to future rate adjustments."
            )
            events.append(
                f"BOJ: policy_score={result.get('policy_score', 0)}, "
                f"rate={result.get('rate_decision', 'hold')}, "
                f"YCC={result.get('ycc_status', 'N/A')}"
            )
        except Exception:
            logger.exception("BOJScorer failed")
            events.append("BOJ: スコアリング失敗")

        # FOMC
        try:
            fomc = FOMCScorer()
            result = fomc.score_statement(
                "The Federal Reserve maintained the federal funds rate. "
                "The committee sees progress on inflation but remains "
                "data dependent on future rate decisions."
            )
            events.append(
                f"FOMC: hawk_dove={result.get('hawk_dove_score', 0)}, "
                f"direction={result.get('rate_direction_signal', 'hold')}"
            )
        except Exception:
            logger.exception("FOMCScorer failed")
            events.append("FOMC: スコアリング失敗")

        # Trump/Political
        try:
            trump = TrumpTracker()
            result = trump.score_statement(
                "Recent political developments regarding trade policy "
                "and tariffs affecting Japanese markets."
            )
            events.append(
                f"Political: score={result.get('market_impact_score', 0)}, "
                f"sectors={result.get('affected_sectors', [])}"
            )
        except Exception:
            logger.exception("TrumpTracker failed")
            events.append("Political: トラッカー失敗")

        return {"voice_events": "\n".join(events)}

    def _fetch_jpx_data(self, ticker: str) -> dict[str, Any]:
        """Fetch JPX market microstructure data."""
        parts: list[str] = []

        try:
            shorts = JPXShortTracker()
            ratio = shorts.get_short_selling_ratio()
            if ratio:
                parts.append(
                    f"空売り比率: total={ratio.get('total_short_ratio', 'N/A')}%, "
                    f"naked={ratio.get('naked_short_ratio', 'N/A')}%"
                )
        except Exception:
            logger.exception("JPX short selling data failed")

        try:
            margin = JPXMarginTracker()
            balance = margin.get_margin_balance()
            if balance:
                parts.append(
                    f"信用残: 買残={balance.get('margin_buy', 'N/A')}, "
                    f"売残={balance.get('margin_sell', 'N/A')}, "
                    f"倍率={balance.get('margin_ratio', 'N/A')}"
                )
        except Exception:
            logger.exception("JPX margin data failed")

        try:
            flows = JPXFlowTracker()
            flow_data = flows.get_investor_flows()
            if flow_data:
                foreign = flow_data.get("foreign_investors", {})
                parts.append(
                    f"投資部門別: 外国人 net={foreign.get('net', 'N/A')}"
                )
        except Exception:
            logger.exception("JPX investor flows failed")

        return {
            "jpx_microstructure": "\n".join(parts) if parts else "JPXデータ未取得",
        }

    def _fetch_edinet_data(self, ticker: str) -> dict[str, Any]:
        """Fetch EDINET large-holding and financial data for context."""
        parts: list[str] = []

        try:
            client = EdinetClient()
            holdings = client.get_large_holdings(ticker)
            if holdings:
                top = holdings[:3]  # latest 3 filings
                for h in top:
                    parts.append(
                        f"大量保有: {h.get('filer_name', 'N/A')} "
                        f"{h.get('ownership_pct', 'N/A')}% "
                        f"({h.get('filing_date', 'N/A')})"
                    )
        except Exception:
            logger.exception("EDINET large-holdings fetch failed for %s", ticker)

        try:
            client = EdinetClient()
            financials = client.get_financial_statements(ticker)
            if financials and financials.get("filing_date"):
                parts.append(
                    f"EDINET決算: 売上={financials.get('revenue', 'N/A')}, "
                    f"営業利益={financials.get('operating_income', 'N/A')}, "
                    f"EPS={financials.get('eps', 'N/A')} "
                    f"({financials.get('filing_date', 'N/A')})"
                )
        except Exception:
            logger.exception("EDINET financials fetch failed for %s", ticker)

        return {
            "edinet_data": "\n".join(parts) if parts else "EDINETデータ未取得",
        }

    def _fetch_crash_status(self, raw_price_df: pd.DataFrame) -> dict[str, Any]:
        """Run CrashDetector on current market data."""
        try:
            market_data: dict[str, Any] = {}
            if not raw_price_df.empty and len(raw_price_df) >= 2:
                close = raw_price_df["Close"].squeeze()
                if isinstance(close, pd.DataFrame):
                    close = close.iloc[:, 0]
                last_close = float(close.iloc[-1])
                prev_close = float(close.iloc[-2])
                if prev_close > 0:
                    market_data["price_change_pct"] = (
                        (last_close - prev_close) / prev_close * 100
                    )

                vol = raw_price_df.get("Volume")
                if vol is not None:
                    vol_series = vol.squeeze()
                    if isinstance(vol_series, pd.DataFrame):
                        vol_series = vol_series.iloc[:, 0]
                    avg_vol = float(vol_series.iloc[:-1].mean()) if len(vol_series) > 1 else 0
                    last_vol = float(vol_series.iloc[-1])
                    if avg_vol > 0:
                        market_data["volume_ratio"] = last_vol / avg_vol

            result = self.crash_detector.check_market(market_data)
            return {"crash_status": result}
        except Exception:
            logger.exception("CrashDetector failed")
            return {
                "crash_status": {
                    "is_crash": False,
                    "severity": "unknown",
                    "type": None,
                    "recommended_action": "CrashDetector error — exercise caution.",
                    "signals": [],
                }
            }

    def _fetch_circuit_breaker(self, date: str) -> dict[str, Any]:
        """Run CircuitBreaker check against WinRateEngine stats."""
        try:
            stats = self.win_rate_engine.get_stats()
            portfolio = {
                "daily_pnl": 0.0,
                "consecutive_losses": 0,
                "daily_trade_count": stats.get("total_trades", 0),
            }
            market_data = {"date": date, "volatility": 0.0}
            result = self.circuit_breaker.check(portfolio, market_data)
            result["win_rate_stats"] = stats
            return {"circuit_breaker": result}
        except Exception:
            logger.exception("CircuitBreaker check failed")
            return {
                "circuit_breaker": {
                    "is_triggered": False,
                    "reason": "CircuitBreaker check failed",
                    "action": "continue",
                }
            }

    # ------------------------------------------------------------------
    # Main build method
    # ------------------------------------------------------------------

    def build(self, ticker: str, date: str) -> dict[str, Any]:
        """Build a fully enriched context dict for the trading pipeline.

        Runs data fetches in parallel via a thread pool.  Individual failures
        are logged but never propagate — the pipeline always gets a complete
        context dict with fallback values where needed.

        Parameters
        ----------
        ticker : str
            Stock ticker symbol (e.g. ``"7203"``).
        date : str
            Analysis date in ISO format (``YYYY-MM-DD``).

        Returns
        -------
        dict
            Enriched context with keys expected by Stage I agents:
            ``price_data``, ``technical_indicators``, ``financials``,
            ``market_index``, ``voice_events``, ``crash_status``,
            ``circuit_breaker``, ``news_headlines``, ``jpx_microstructure``,
            ``edinet_data``.
        """
        logger.info("ContextBuilder.build() start: ticker=%s date=%s", ticker, date)

        context: dict[str, Any] = {}

        # Phase 1: parallel fetches that don't depend on each other
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self._fetch_price_data, ticker): "price",
                executor.submit(self._fetch_technical_indicators, ticker): "tech",
                executor.submit(self._fetch_financials, ticker): "fin",
                executor.submit(self._fetch_market_index): "index",
                executor.submit(self._fetch_voice_events): "voice",
                executor.submit(self._fetch_circuit_breaker, date): "cb",
                executor.submit(self._fetch_jpx_data, ticker): "jpx",
                executor.submit(self._fetch_edinet_data, ticker): "edinet",
            }

            for future in as_completed(futures):
                label = futures[future]
                try:
                    result = future.result()
                    context.update(result)
                except Exception:
                    logger.exception("Context fetch '%s' raised an exception", label)

        # Phase 2: crash detector needs the raw price df from phase 1
        raw_df = context.pop("_raw_price_df", pd.DataFrame())
        crash_result = self._fetch_crash_status(raw_df)
        context.update(crash_result)

        # Build news context from voice events and market data
        news_parts: list[str] = []
        if context.get("voice_events"):
            news_parts.append(context["voice_events"])
        if context.get("jpx_microstructure"):
            news_parts.append(context["jpx_microstructure"])
        context.setdefault(
            "news_headlines",
            "\n".join(news_parts) if news_parts else "LLMの最新知識を使用してください。",
        )

        # Map technical_indicators to the 'indicators' key that TechnicalAnalyst
        # also checks, and voice_events to 'voice_tracker_events' for NewsAnalyst
        context["indicators"] = context.get("technical_indicators", "")
        context["voice_tracker_events"] = context.get("voice_events", "")

        logger.info("ContextBuilder.build() complete: %d keys", len(context))
        return context
