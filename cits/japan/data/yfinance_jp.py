"""Japan stock data via yfinance with technical indicator calculations."""

import logging
from typing import Optional

import pandas as pd
import yfinance as yf
import ta

logger = logging.getLogger(__name__)


class JapanStockData:
    """Fetches Japanese equity data from Yahoo Finance and computes technicals."""

    @staticmethod
    def _ensure_tse_suffix(ticker: str) -> str:
        """Append .T for TSE stocks if not already suffixed."""
        if ticker.startswith("^"):
            return ticker
        if "." not in ticker:
            return f"{ticker}.T"
        return ticker

    def get_stock_data(self, ticker: str, period: str = "3mo") -> pd.DataFrame:
        """Get OHLCV data for a Japanese stock.

        Args:
            ticker: Stock code (e.g. "7203" for Toyota). ".T" is appended automatically.
            period: yfinance period string (e.g. "1d", "5d", "1mo", "3mo", "1y", "max").

        Returns:
            DataFrame with Open, High, Low, Close, Volume columns.
        """
        symbol = self._ensure_tse_suffix(ticker)
        try:
            data = yf.download(symbol, period=period, progress=False)
            if data.empty:
                logger.warning("No data returned for %s (period=%s)", symbol, period)
            return data
        except Exception as e:
            logger.error("Failed to fetch stock data for %s: %s", symbol, e)
            return pd.DataFrame()

    def get_nikkei225(self, period: str = "3mo") -> pd.DataFrame:
        """Get Nikkei 225 index data."""
        try:
            data = yf.download("^N225", period=period, progress=False)
            if data.empty:
                logger.warning("No data returned for ^N225 (period=%s)", period)
            return data
        except Exception as e:
            logger.error("Failed to fetch Nikkei 225 data: %s", e)
            return pd.DataFrame()

    def get_topix(self, period: str = "3mo") -> pd.DataFrame:
        """Get TOPIX index data."""
        try:
            data = yf.download("^TOPX", period=period, progress=False)
            if data.empty:
                logger.warning("No data returned for ^TOPX (period=%s)", period)
            return data
        except Exception as e:
            logger.error("Failed to fetch TOPIX data: %s", e)
            return pd.DataFrame()

    def get_financial_info(self, ticker: str) -> dict:
        """Get company financial information (PE, PBR, dividend yield, etc.).

        Args:
            ticker: Stock code (e.g. "7203").

        Returns:
            Dict with keys like trailingPE, priceToBook, dividendYield, marketCap, etc.
        """
        symbol = self._ensure_tse_suffix(ticker)
        try:
            stock = yf.Ticker(symbol)
            info = stock.info or {}
            return {
                "ticker": symbol,
                "shortName": info.get("shortName"),
                "longName": info.get("longName"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "marketCap": info.get("marketCap"),
                "trailingPE": info.get("trailingPE"),
                "forwardPE": info.get("forwardPE"),
                "priceToBook": info.get("priceToBook"),
                "dividendYield": info.get("dividendYield"),
                "trailingEps": info.get("trailingEps"),
                "forwardEps": info.get("forwardEps"),
                "bookValue": info.get("bookValue"),
                "revenuePerShare": info.get("revenuePerShare"),
                "returnOnEquity": info.get("returnOnEquity"),
                "debtToEquity": info.get("debtToEquity"),
                "freeCashflow": info.get("freeCashflow"),
                "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
                "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
            }
        except Exception as e:
            logger.error("Failed to fetch financial info for %s: %s", symbol, e)
            return {}

    def get_technical_indicators(self, ticker: str, period: str = "6mo") -> dict:
        """Calculate technical indicators for a Japanese stock.

        Computes SMA(5,25,75), RSI(14), MACD, and Bollinger Bands.

        Args:
            ticker: Stock code (e.g. "7203").
            period: Data period for calculation (needs enough history).

        Returns:
            Dict with latest values for each indicator.
        """
        df = self.get_stock_data(ticker, period=period)
        if df.empty:
            return {}

        try:
            close = df["Close"].squeeze()
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]

            result: dict = {"ticker": self._ensure_tse_suffix(ticker)}

            # SMA
            for window in (5, 25, 75):
                sma = ta.trend.sma_indicator(close, window=window)
                result[f"sma_{window}"] = sma.iloc[-1] if len(sma) >= window else None

            # RSI(14)
            rsi = ta.momentum.rsi(close, window=14)
            result["rsi_14"] = rsi.iloc[-1] if len(rsi) >= 14 else None

            # MACD
            macd = ta.trend.MACD(close)
            result["macd"] = macd.macd().iloc[-1] if not macd.macd().empty else None
            result["macd_signal"] = macd.macd_signal().iloc[-1] if not macd.macd_signal().empty else None
            result["macd_hist"] = macd.macd_diff().iloc[-1] if not macd.macd_diff().empty else None

            # Bollinger Bands (20, 2)
            bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
            result["bb_upper"] = bb.bollinger_hband().iloc[-1] if not bb.bollinger_hband().empty else None
            result["bb_middle"] = bb.bollinger_mavg().iloc[-1] if not bb.bollinger_mavg().empty else None
            result["bb_lower"] = bb.bollinger_lband().iloc[-1] if not bb.bollinger_lband().empty else None

            return result
        except Exception as e:
            logger.error("Failed to compute technical indicators for %s: %s", ticker, e)
            return {}
