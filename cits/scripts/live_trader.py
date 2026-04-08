"""CITS Live Trader v3 -- Two-Stage Scan Architecture

Three execution modes per day:
  08:30  morning   -- CIS on 9 ETFs only (instant, 10 seconds)
  14:00  prefetch  -- Fetch 3,950 tickers + 9 ETFs, cache to disk (no trading)
  15:00  afternoon -- Kei-kun on cached data + CIS ETF fallback (instant, orders by 15:01)

Key fixes over v2:
  - Two-stage scan: prefetch at 14:00, signal scan at 15:00 on cached data
  - ETF lot_size=1, individual stock lot_size=100
  - Capital 300K (from 100K)
  - ETF fallback: if kei-kun signals are all too expensive, CIS on 9 ETFs
  - Exchange=9 (SOR), AccountType=4, FundType="AA"
  - Order password separate from API password

Usage:
    python -m cits.scripts.live_trader --mode morning   --capital 300000
    python -m cits.scripts.live_trader --mode prefetch  --capital 300000
    python -m cits.scripts.live_trader --mode afternoon --capital 300000
    python -m cits.scripts.live_trader --mode morning   --capital 300000 --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pickle
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

# .env auto-load
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
    root_env = Path(__file__).resolve().parent.parent.parent / ".env"
    if root_env.exists():
        load_dotenv(root_env, override=False)
except ImportError:
    pass

from cits.scripts.solve_equation import (
    TICKERS as ETF_TICKERS,
    _check_cis_entry,
    _sma,
)

# ---------------------------------------------------------------
# Paths
# ---------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR = Path(__file__).resolve().parent.parent / "logs" / "live_trades"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TICKER_CACHE = DATA_DIR / "tse_tickers.json"

# ---------------------------------------------------------------
# Logging (stdout + file)
# ---------------------------------------------------------------
# Force logging setup (basicConfig is no-op if already called by imports)
_root = logging.getLogger()
_root.setLevel(logging.INFO)
# Remove any pre-existing handlers (from solve_equation etc.)
for _h in _root.handlers[:]:
    _root.removeHandler(_h)
_fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt)
_root.addHandler(_sh)
_fh = logging.FileHandler(LOG_DIR / "live_trader.log", encoding="utf-8")
_fh.setFormatter(_fmt)
_root.addHandler(_fh)

logger = logging.getLogger("cits.live_trader")

# ---------------------------------------------------------------
# Strategy Parameters
# ---------------------------------------------------------------
CIS_PARAMS = {
    "stop_pct": 1.5,
    "target_pct": 5.0,
    "hold_days": 5,
    "risk_pct": 0.05,
    "use_volume_confirm": True,
}

KEI_PARAMS = {
    "sideways_days": 60,
    "sideways_range_pct": 15,
    "new_high_exit_days": 7,
    "stop_pct": 5.0,
    "max_hold_days": 30,
    "risk_pct": 0.05,
}

# ---------------------------------------------------------------
# Safety limits
# ---------------------------------------------------------------
MAX_DAILY_LOSS_PCT = 3.0
MAX_POSITIONS = 3
MAX_SINGLE_POSITION_PCT = 50  # 300K * 50% = 150K max per position


# ---------------------------------------------------------------
# Lot size helper
# ---------------------------------------------------------------
def _get_lot_size(ticker: str) -> int:
    """ETFs trade in 1-share lots, individual stocks in 100-share lots."""
    if ticker in ETF_TICKERS:
        return 1
    return 100


# ---------------------------------------------------------------
# TSE ticker list (JPX, cached daily)
# ---------------------------------------------------------------
def _fetch_tse_tickers() -> list[str]:
    """Fetch full TSE ticker list from JPX, cached daily."""
    import io
    import requests as req

    if TICKER_CACHE.exists():
        cache = json.loads(TICKER_CACHE.read_text(encoding="utf-8"))
        if cache.get("date") == str(date.today()):
            return cache["tickers"]
    try:
        url = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
        r = req.get(url, timeout=30)
        r.raise_for_status()
        df = pd.read_excel(io.BytesIO(r.content))
        market_col = [c for c in df.columns if "市場" in str(c) or "商品" in str(c)][0]
        valid = {
            "プライム（内国株式）", "スタンダード（内国株式）",
            "グロース（内国株式）", "ETF・ETN",
        }
        stock_df = df[df[market_col].isin(valid)]
        code_col = [c for c in df.columns if "コード" in str(c)][0]
        tickers = [
            str(c) for c in stock_df[code_col].tolist()
            if str(c).isdigit() and len(str(c)) == 4
        ]
        TICKER_CACHE.parent.mkdir(parents=True, exist_ok=True)
        TICKER_CACHE.write_text(
            json.dumps(
                {"date": str(date.today()), "tickers": tickers, "count": len(tickers)},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        logger.info("TSE ticker list updated: %d tickers", len(tickers))
        return tickers
    except Exception as e:
        logger.warning("JPX fetch failed (%s), using ETF fallback", e)
        return list(ETF_TICKERS)


# ---------------------------------------------------------------
# Cache file paths
# ---------------------------------------------------------------
def _market_cache_path(target_date: date | None = None) -> Path:
    d = target_date or date.today()
    return DATA_DIR / f"market_cache_{d.strftime('%Y%m%d')}.pkl"


def _etf_cache_path(target_date: date | None = None) -> Path:
    d = target_date or date.today()
    return DATA_DIR / f"etf_cache_{d.strftime('%Y%m%d')}.pkl"


# ---------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------
def fetch_etf_data() -> dict[str, pd.DataFrame]:
    """Fetch 9 ETFs. Fast (~10 seconds)."""
    end = date.today()
    start = end - timedelta(days=200)
    symbols = [f"{t}.T" for t in ETF_TICKERS]
    logger.info("Fetching ETF data for %d tickers...", len(ETF_TICKERS))

    data: dict[str, pd.DataFrame] = {}
    try:
        df_all = yf.download(
            symbols, start=str(start), end=str(end),
            auto_adjust=True, progress=False, threads=True,
        )
        if df_all is None or df_all.empty:
            logger.warning("ETF download returned empty")
            return data
        if isinstance(df_all.columns, pd.MultiIndex):
            for s in symbols:
                key = s.replace(".T", "")
                try:
                    df = df_all.xs(s, level=1, axis=1)
                    if len(df.dropna()) >= 22:
                        data[key] = df.dropna()
                except (KeyError, ValueError):
                    pass
        else:
            # Single ticker case
            key = symbols[0].replace(".T", "")
            if len(df_all.dropna()) >= 22:
                data[key] = df_all.dropna()
    except Exception as e:
        logger.error("ETF fetch error: %s", e)

    logger.info("ETF data loaded: %d / %d", len(data), len(ETF_TICKERS))
    return data


def fetch_full_data() -> dict[str, pd.DataFrame]:
    """Fetch all ~3,950 TSE tickers. Slow (5-7 minutes)."""
    end = date.today()
    start = end - timedelta(days=200)
    tickers = _fetch_tse_tickers()
    symbols = [f"{t}.T" for t in tickers]
    logger.info("Fetching full market data for %d tickers...", len(tickers))

    data: dict[str, pd.DataFrame] = {}
    chunk_size = 200
    total_chunks = (len(symbols) + chunk_size - 1) // chunk_size

    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i:i + chunk_size]
        chunk_num = i // chunk_size + 1
        logger.info("  Batch %d/%d (%d tickers)...", chunk_num, total_chunks, len(chunk))
        try:
            df_all = yf.download(
                chunk, start=str(start), end=str(end),
                auto_adjust=True, progress=False, threads=True,
            )
            if df_all is None or df_all.empty:
                continue
            if isinstance(df_all.columns, pd.MultiIndex):
                for s in chunk:
                    key = s.replace(".T", "")
                    try:
                        df = df_all.xs(s, level=1, axis=1)
                        if len(df.dropna()) >= 22:
                            data[key] = df.dropna()
                    except (KeyError, ValueError):
                        pass
            else:
                key = chunk[0].replace(".T", "")
                if len(df_all.dropna()) >= 22:
                    data[key] = df_all.dropna()
        except Exception as e:
            logger.warning("  Batch %d error: %s", chunk_num, e)

    logger.info("Full data loaded: %d / %d tickers", len(data), len(tickers))
    return data


def save_cache(data: dict[str, pd.DataFrame], cache_path: Path) -> None:
    """Save market data to pickle cache."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    size_mb = cache_path.stat().st_size / (1024 * 1024)
    logger.info("Cache saved: %s (%.1f MB, %d tickers)", cache_path.name, size_mb, len(data))


def load_cache(cache_path: Path) -> dict[str, pd.DataFrame] | None:
    """Load market data from pickle cache. Returns None if missing/corrupt."""
    if not cache_path.exists():
        logger.warning("Cache not found: %s", cache_path)
        return None
    try:
        with open(cache_path, "rb") as f:
            data = pickle.load(f)
        logger.info("Cache loaded: %s (%d tickers)", cache_path.name, len(data))
        return data
    except Exception as e:
        logger.error("Cache load failed: %s -- %s", cache_path, e)
        return None


# ---------------------------------------------------------------
# Filters
# ---------------------------------------------------------------
def _is_shite_stock(volumes: list[float], price: float) -> bool:
    """Detect shite-kabu (manipulated penny stocks)."""
    if len(volumes) < 21:
        return False
    avg_vol = sum(volumes[-21:-1]) / 20
    if avg_vol <= 0:
        return True
    vol_ratio = volumes[-1] / avg_vol
    if vol_ratio > 10 and price < 500:
        return True
    if avg_vol < 5000:
        return True
    return False


# ---------------------------------------------------------------
# CIS Scan (momentum breakout)
# ---------------------------------------------------------------
def scan_cis(data: dict[str, pd.DataFrame], capital: float) -> list[dict]:
    """CIS strategy: 20-day breakout + volume spike."""
    signals = []
    for ticker, df in data.items():
        if len(df) < 22:
            continue
        closes = [float(x) for x in df["Close"]]
        volumes = [float(x) for x in df["Volume"]]
        price = closes[-1]
        if price < 100 or _is_shite_stock(volumes, price):
            continue

        # ---- WINNING PATTERN FILTER (CIS版) ----
        # 直近5日の出来高異常チェック（思惑買い排除）
        if len(volumes) >= 25:
            avg_vol_20 = sum(volumes[-25:-5]) / 20
            if avg_vol_20 > 0:
                recent_5 = volumes[-5:]
                max_recent_ratio = max(v / avg_vol_20 for v in recent_5)
                if max_recent_ratio > 5.0:
                    continue  # 出来高異常 → 除外

        if not _check_cis_entry(closes, volumes, CIS_PARAMS["use_volume_confirm"]):
            continue

        entry = price
        stop_dist = entry * CIS_PARAMS["stop_pct"] / 100
        if stop_dist <= 0:
            continue

        lot_size = _get_lot_size(ticker)
        risk_amt = capital * CIS_PARAMS["risk_pct"]
        size = max(int(risk_amt / stop_dist) // lot_size * lot_size, lot_size)
        notional = size * entry
        max_notional = capital * MAX_SINGLE_POSITION_PCT / 100
        if notional > max_notional:
            size = max(int(max_notional / entry / lot_size) * lot_size, lot_size)
            notional = size * entry
        if notional > capital * 0.9:
            continue

        high_20 = max(closes[-21:-1])
        breakout_pct = (price - high_20) / high_20 * 100
        avg_vol = sum(volumes[-21:-1]) / 20
        vol_ratio = volumes[-1] / avg_vol if avg_vol > 0 else 0

        signals.append({
            "ticker": ticker, "strategy": "CIS", "lot_size": lot_size,
            "price": round(price, 1), "size": size,
            "notional": round(notional, 0),
            "stop_loss": round(entry * (1 - CIS_PARAMS["stop_pct"] / 100), 1),
            "take_profit": round(entry * (1 + CIS_PARAMS["target_pct"] / 100), 1),
            "breakout_pct": round(breakout_pct, 2),
            "vol_ratio": round(vol_ratio, 2),
            "score": round(breakout_pct * 2 + min(vol_ratio * 5, 20), 1),
            "last_date": df.index[-1].strftime("%Y-%m-%d"),
        })

    signals.sort(key=lambda s: s["score"], reverse=True)
    return signals


# ---------------------------------------------------------------
# Kei-kun Scan (sideways breakout)
# ---------------------------------------------------------------
def scan_keikun(data: dict[str, pd.DataFrame], capital: float) -> list[dict]:
    """Kei-kun strategy: 60-day sideways + breakout + 7-day new high exit."""
    signals = []
    sd = KEI_PARAMS["sideways_days"]

    for ticker, df in data.items():
        if len(df) < sd + 5:
            continue
        closes = [float(x) for x in df["Close"]]
        volumes = [float(x) for x in df["Volume"]]
        price = closes[-1]
        if price < 100 or _is_shite_stock(volumes, price):
            continue

        # ---- WINNING PATTERN FILTER (強化版) ----

        # Filter 1: 直近5日の出来高異常チェック（思惑買い排除）
        if len(volumes) >= 25:
            avg_vol_20 = sum(volumes[-25:-5]) / 20  # 5日前までの20日平均
            if avg_vol_20 > 0:
                # 直近5日のどれかが20日平均の5倍以上 → 思惑買い → 除外
                recent_5 = volumes[-5:]
                max_recent_ratio = max(v / avg_vol_20 for v in recent_5)
                if max_recent_ratio > 5.0:
                    continue  # Skip: 出来高異常（思惑買い・仕手の疑い）

        # Filter 2: Stage2確認（Minervini基準）
        if len(closes) >= 50:
            sma50 = sum(closes[-50:]) / 50
            if price < sma50:
                continue  # Skip: SMA50割れ → Stage2ではない

        # Sideways check: last N days range < threshold
        window = closes[-sd - 1:-1]
        w_min, w_max = min(window), max(window)
        if w_min <= 0:
            continue
        range_pct = (w_max - w_min) / w_min * 100
        if range_pct > KEI_PARAMS["sideways_range_pct"]:
            continue

        # Breakout: today close > range high
        if price <= w_max * 1.005:
            continue

        # Position sizing
        entry = price
        stop_dist = entry * KEI_PARAMS["stop_pct"] / 100
        if stop_dist <= 0:
            continue

        lot_size = _get_lot_size(ticker)
        risk_amt = capital * KEI_PARAMS["risk_pct"]
        size = max(int(risk_amt / stop_dist) // lot_size * lot_size, lot_size)
        notional = size * entry
        max_notional = capital * MAX_SINGLE_POSITION_PCT / 100
        if notional > max_notional:
            size = max(int(max_notional / entry / lot_size) * lot_size, lot_size)
            notional = size * entry
        if notional > capital * 0.9:
            continue

        breakout_pct = (price - w_max) / w_max * 100
        avg_vol = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else 1
        vol_ratio = volumes[-1] / avg_vol if avg_vol > 0 else 0

        signals.append({
            "ticker": ticker, "strategy": "KEI", "lot_size": lot_size,
            "price": round(price, 1), "size": size,
            "notional": round(notional, 0),
            "stop_loss": round(entry * (1 - KEI_PARAMS["stop_pct"] / 100), 1),
            "take_profit": 0,  # exit on 7 new highs, not fixed TP
            "sideways_days": sd,
            "sideways_range_pct": round(range_pct, 1),
            "breakout_pct": round(breakout_pct, 2),
            "vol_ratio": round(vol_ratio, 2),
            "exit_rule": "new_high_7 or max_hold_30 or stop_-5%",
            "score": round(breakout_pct * 3 + min(vol_ratio * 3, 15), 1),
            "last_date": df.index[-1].strftime("%Y-%m-%d"),
        })

    signals.sort(key=lambda s: s["score"], reverse=True)
    return signals


# ---------------------------------------------------------------
# Execution
# ---------------------------------------------------------------
def execute_signals(signals: list[dict], capital: float, dry_run: bool) -> list[dict]:
    """Execute trade signals. dry_run=True logs only, no orders."""
    if not signals:
        logger.info("No signals to execute. HOLD.")
        return []

    results = []

    if dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN MODE -- no orders placed")
        logger.info("=" * 60)
        cum_notional = 0.0
        for sig in signals[:MAX_POSITIONS]:
            # Apply same cumulative guard as live mode
            if cum_notional + sig["notional"] > capital * 0.9:
                logger.warning(
                    "  [%s] %s BLOCKED: cumulative Y%.0f + Y%.0f > 90%% cap Y%.0f",
                    sig["strategy"], sig["ticker"],
                    cum_notional, sig["notional"], capital * 0.9,
                )
                results.append({**sig, "status": "blocked_cumulative"})
                continue
            cum_notional += sig["notional"]
            logger.info(
                "  [%s] %s x%d (lot=%d) @ Y%.1f  notional=Y%.0f  SL=%.1f  "
                "breakout=+%.2f%%  vol=%.1fx  score=%.1f",
                sig["strategy"], sig["ticker"], sig["size"], sig["lot_size"],
                sig["price"], sig["notional"], sig["stop_loss"],
                sig["breakout_pct"], sig["vol_ratio"], sig["score"],
            )
            results.append({**sig, "status": "dry_run"})
        return results

    # --- LIVE execution ---
    from cits.japan.broker.kabu_api import KabuStationAPI
    from cits.japan.broker.software_oco import SoftwareOCO

    try:
        broker = KabuStationAPI()
        broker._ensure_token()
        logger.info("kabuStation connected")
    except Exception as e:
        logger.error("kabuStation connection failed: %s", e)
        return []

    oco_manager = SoftwareOCO(broker=broker, check_interval=5.0)

    # Log all pending signals
    for sig in signals[:MAX_POSITIONS]:
        logger.info(
            "PENDING: BUY %s x%d (lot=%d) @ MARKET [%s] notional=Y%.0f",
            sig["ticker"], sig["size"], sig["lot_size"],
            sig["strategy"], sig["notional"],
        )

    # SAFETY: validate and filter
    approved_signals = []
    cumulative_notional = 0.0
    for sig in signals[:MAX_POSITIONS]:
        if sig["notional"] > capital:
            logger.error(
                "BLOCKED: %s notional Y%.0f > capital Y%.0f",
                sig["ticker"], sig["notional"], capital,
            )
            results.append({**sig, "status": "blocked_overcapital"})
            continue
        if sig["notional"] > capital * MAX_SINGLE_POSITION_PCT / 100:
            logger.error(
                "BLOCKED: %s notional Y%.0f > %d%% cap Y%.0f",
                sig["ticker"], sig["notional"],
                MAX_SINGLE_POSITION_PCT, capital * MAX_SINGLE_POSITION_PCT / 100,
            )
            results.append({**sig, "status": "blocked_oversize"})
            continue
        # Cumulative capital guard: total notional must not exceed 90% of capital
        if cumulative_notional + sig["notional"] > capital * 0.9:
            logger.warning(
                "BLOCKED: %s cumulative notional Y%.0f + Y%.0f > 90%% cap Y%.0f",
                sig["ticker"], cumulative_notional, sig["notional"], capital * 0.9,
            )
            results.append({**sig, "status": "blocked_cumulative"})
            continue
        cumulative_notional += sig["notional"]
        approved_signals.append(sig)

    for sig in approved_signals:
        ticker = sig["ticker"]
        logger.info(
            "EXECUTING: BUY %s x%d @ MARKET [%s]",
            ticker, sig["size"], sig["strategy"],
        )
        try:
            order_resp = broker.place_order(
                symbol=ticker, side="buy", qty=sig["size"],
                order_type="market", exchange=9,
            )
            order_id = order_resp.get("OrderId", "unknown")
            if "error" in order_resp:
                logger.error("Order failed: %s", order_resp["error"])
                results.append({**sig, "status": "error", "error": order_resp["error"]})
                continue

            board = broker.get_board(ticker, exchange=1)  # board info: TSE=1, order: SOR=9
            fill_price = board.get("CurrentPrice", sig["price"])

            if sig["strategy"] == "CIS":
                oco_id = oco_manager.create_oco(
                    symbol=ticker, side="buy", qty=sig["size"],
                    take_profit=sig["take_profit"], stop_loss=sig["stop_loss"],
                )
            else:
                # Kei-kun: SL only, TP is software-monitored (new high 7)
                oco_id = oco_manager.create_oco(
                    symbol=ticker, side="buy", qty=sig["size"],
                    take_profit=fill_price * 1.50,  # wide safety net
                    stop_loss=sig["stop_loss"],
                )

            results.append({
                **sig, "status": "filled", "order_id": order_id,
                "fill_price": fill_price, "oco_id": oco_id,
            })

            # Register in position DB for monitoring
            try:
                from cits.scripts.position_monitor import register_position
                register_position(
                    ticker=ticker, strategy=sig["strategy"],
                    entry_price=fill_price, size=sig["size"],
                    stop_loss=sig["stop_loss"],
                    sl_order_id=str(oco_id),
                    exit_deadline=sig.get("exit_deadline", ""),
                )
            except Exception as reg_err:
                logger.error("Position registration failed: %s", reg_err)
        except Exception as e:
            logger.error("Execution error for %s: %s", ticker, e)
            results.append({**sig, "status": "error", "error": str(e)})

    return results


# ---------------------------------------------------------------
# Trade log
# ---------------------------------------------------------------
def save_trade_log(signals: list[dict], results: list[dict], mode: str) -> None:
    """Save JSON trade log per execution."""
    today_str = date.today().strftime("%Y-%m-%d")
    ts = datetime.now().strftime("%H%M%S")
    log_file = LOG_DIR / f"trades_{today_str}_{mode}_{ts}.json"
    log_data = {
        "date": today_str,
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "cis_params": CIS_PARAMS,
        "kei_params": KEI_PARAMS,
        "safety": {
            "max_daily_loss_pct": MAX_DAILY_LOSS_PCT,
            "max_positions": MAX_POSITIONS,
            "max_single_position_pct": MAX_SINGLE_POSITION_PCT,
        },
        "signals_found": len(signals),
        "signals": signals,
        "executions": results,
    }
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Trade log saved: %s", log_file)


# ---------------------------------------------------------------
# Mode: prefetch (14:00 -- data collection only)
# ---------------------------------------------------------------
def run_prefetch() -> None:
    """Fetch all market data and save to disk cache. No trading."""
    logger.info("=" * 60)
    logger.info("PREFETCH MODE -- data collection only, no trading")
    logger.info("=" * 60)

    t0 = datetime.now()

    # 1) Fetch and cache ETFs
    etf_data = fetch_etf_data()
    if etf_data:
        save_cache(etf_data, _etf_cache_path())

    # 2) Fetch and cache full market
    full_data = fetch_full_data()
    if full_data:
        save_cache(full_data, _market_cache_path())

    elapsed = (datetime.now() - t0).total_seconds()
    logger.info(
        "Prefetch complete: %d ETFs + %d stocks in %.1f seconds",
        len(etf_data), len(full_data), elapsed,
    )


# ---------------------------------------------------------------
# Mode: morning (08:30 -- CIS on ETFs only)
# ---------------------------------------------------------------
def run_morning(capital: float, dry_run: bool) -> None:
    """Morning scan: CIS on 9 ETFs. Fast execution."""
    logger.info("=" * 60)
    logger.info("MORNING MODE -- CIS ETF scan (9 tickers, ~10 seconds)")
    logger.info("=" * 60)

    etf_data = fetch_etf_data()
    if len(etf_data) < 3:
        logger.error("Insufficient ETF data (%d). Aborting.", len(etf_data))
        return

    cis_signals = scan_cis(etf_data, capital)
    logger.info("[CIS-ETF] %d signals from %d tickers", len(cis_signals), len(etf_data))
    for i, s in enumerate(cis_signals[:5], 1):
        logger.info(
            "  CIS #%d %s Y%.1f lot=%d x%d notional=Y%.0f breakout=+%.2f%% vol=%.1fx score=%.1f",
            i, s["ticker"], s["price"], s["lot_size"], s["size"],
            s["notional"], s["breakout_pct"], s["vol_ratio"], s["score"],
        )

    # Execute top 3 ETF signals
    top_signals = cis_signals[:MAX_POSITIONS]
    results = execute_signals(top_signals, capital, dry_run)
    save_trade_log(cis_signals, results, "morning")

    _print_summary(cis_signals, results)


# ---------------------------------------------------------------
# Mode: afternoon (15:20 -- kei-kun on cached data + FRESH ETF)
# ---------------------------------------------------------------
def run_afternoon(capital: float, dry_run: bool) -> None:
    """Afternoon scan: Kei-kun on cached full market + FRESH CIS ETF.

    Runs at 15:20 when chart patterns are nearly finalized.
    Uses 14:00 prefetch cache for kei-kun (60-day sideways needs history).
    Fetches FRESH ETF data for CIS (needs latest closing pattern).
    """
    logger.info("=" * 60)
    logger.info("AFTERNOON MODE -- Kei-kun (cached) + FRESH CIS ETF (15:20)")
    logger.info("=" * 60)

    # 1) Load cached full market data (from 14:00 prefetch)
    market_data = load_cache(_market_cache_path())
    if market_data is None:
        logger.warning("No market cache found. Falling back to ETF-only mode.")
        market_data = {}

    # 2) ALWAYS fetch FRESH ETF data (10 seconds, latest chart shape)
    logger.info("Fetching FRESH ETF data for latest chart pattern...")
    etf_cache = fetch_etf_data()
    if not etf_cache:
        logger.warning("Fresh ETF fetch failed. Trying cache...")
        etf_cache = load_cache(_etf_cache_path()) or {}

    all_signals: list[dict] = []
    kei_count = 0

    # 3) Kei-kun scan on cached full market data
    if market_data:
        kei_signals = scan_keikun(market_data, capital)
        logger.info("[KEI] %d signals from %d tickers", len(kei_signals), len(market_data))
        for i, s in enumerate(kei_signals[:5], 1):
            logger.info(
                "  KEI #%d %s Y%.1f lot=%d x%d notional=Y%.0f "
                "sideways=%dd range=%.1f%% breakout=+%.2f%% score=%.1f",
                i, s["ticker"], s["price"], s["lot_size"], s["size"],
                s["notional"], s["sideways_days"],
                s["sideways_range_pct"], s["breakout_pct"], s["score"],
            )
        # Take top 2 kei-kun signals
        all_signals.extend(kei_signals[:2])
        kei_count = min(len(kei_signals), 2)
    else:
        logger.warning("[KEI] Skipped -- no cached market data")
        kei_signals = []

    # 4) CIS scan on ETFs (instant)
    if etf_cache:
        cis_signals = scan_cis(etf_cache, capital)
        logger.info("[CIS-ETF] %d signals from %d ETFs", len(cis_signals), len(etf_cache))
        for i, s in enumerate(cis_signals[:5], 1):
            logger.info(
                "  CIS #%d %s Y%.1f lot=%d x%d notional=Y%.0f "
                "breakout=+%.2f%% vol=%.1fx score=%.1f",
                i, s["ticker"], s["price"], s["lot_size"], s["size"],
                s["notional"], s["breakout_pct"], s["vol_ratio"], s["score"],
            )

        # Avoid duplicates with KEI
        kei_tickers = {s["ticker"] for s in all_signals}
        cis_unique = [s for s in cis_signals if s["ticker"] not in kei_tickers]

        # 5) Fallback logic: if no kei-kun signals, CIS gets more slots
        if kei_count == 0:
            # No kei-kun => CIS gets all 3 slots
            remaining = MAX_POSITIONS
            logger.info("No KEI signals -- CIS gets all %d slots", remaining)
        else:
            # Kei-kun found => CIS gets remaining slots (3 - kei_count)
            remaining = MAX_POSITIONS - kei_count

        all_signals.extend(cis_unique[:remaining])
    else:
        cis_signals = []
        logger.warning("[CIS-ETF] Skipped -- no ETF data")

    # Sort combined signals by score
    all_signals.sort(key=lambda s: s["score"], reverse=True)

    logger.info("=" * 60)
    logger.info(
        "COMBINED: %d signals (KEI: %d + CIS: %d)",
        len(all_signals), kei_count,
        len(all_signals) - kei_count,
    )
    logger.info("=" * 60)

    results = execute_signals(all_signals, capital, dry_run)
    combined_log = kei_signals + cis_signals
    save_trade_log(combined_log, results, "afternoon")

    _print_summary(all_signals, results)


# ---------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------
def _print_summary(all_signals: list[dict], results: list[dict]) -> None:
    logger.info("")
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    executed = [r for r in results if r.get("status") in ("filled", "dry_run")]
    cis_exec = [r for r in executed if r.get("strategy") == "CIS"]
    kei_exec = [r for r in executed if r.get("strategy") == "KEI"]
    logger.info("  Total signals found: %d", len(all_signals))
    logger.info("  Executed: %d (CIS: %d, KEI: %d)", len(executed), len(cis_exec), len(kei_exec))
    if executed:
        total_notional = sum(r.get("notional", 0) for r in executed)
        logger.info("  Total notional: Y%s / Y%s capital",
                     f"{total_notional:,.0f}",
                     f"{sum(1 for _ in []):,.0f}" if False else "300,000")


# ---------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------
def preflight_check(dry_run: bool) -> bool:
    """Validate environment before trading. Returns True if OK."""
    # Market day check
    today = date.today()
    if today.weekday() >= 5:
        logger.error("TODAY IS %s. Market closed. Exiting.", today.strftime("%A"))
        return False

    if dry_run:
        return True

    # API pre-check (non-destructive, never kill kabuStation)
    import requests as req
    api_pw = os.environ.get("KABU_API_PASSWORD", "")
    if not api_pw:
        logger.error("KABU_API_PASSWORD not set. Check .env file.")
        return False

    try:
        r = req.post(
            "http://localhost:18080/kabusapi/token",
            json={"APIPassword": api_pw},
            timeout=5,
        )
        if r.status_code == 200:
            logger.info("API pre-check: OK (token obtained)")
        else:
            logger.error(
                "API pre-check: FAILED (%d). kabuStation may need re-login.",
                r.status_code,
            )
            logger.error("DO NOT restart kabuStation. Check GUI login status.")
            return False
    except Exception as e:
        logger.error(
            "API pre-check: CONNECTION FAILED (%s). kabuStation may not be running.", e,
        )
        return False

    # Task scheduler safety gate
    scheduled_marker = os.environ.get("CITS_SCHEDULED_RUN", "")
    if scheduled_marker != "TASKSCHEDULER":
        logger.error("BLOCKED: Live execution only from Task Scheduler.")
        logger.error("Set CITS_SCHEDULED_RUN=TASKSCHEDULER in bat file.")
        logger.error("AI must NEVER set this env var directly.")
        return False

    logger.warning("LIVE TRADE MODE (scheduled)")
    return True


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="CITS Live Trader v3")
    parser.add_argument("--capital", type=float, default=300_000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--mode",
        choices=["morning", "afternoon", "prefetch"],
        required=True,
        help="morning=CIS ETF 8:30, prefetch=data cache 14:00, afternoon=KEI+ETF 15:00",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("CITS Live Trader v3 -- Two-Stage Scan Architecture")
    logger.info("=" * 60)
    logger.info("  Mode: %s", args.mode)
    logger.info("  Capital: Y%s", f"{args.capital:,.0f}")
    logger.info("  Execution: %s", "DRY RUN" if args.dry_run else "LIVE")
    logger.info("  Date: %s (%s)", date.today(), date.today().strftime("%A"))
    logger.info("  Time: %s", datetime.now().strftime("%H:%M:%S"))
    logger.info("=" * 60)

    # Prefetch mode: no trading, no pre-flight needed beyond market day
    if args.mode == "prefetch":
        today = date.today()
        if today.weekday() >= 5:
            logger.error("TODAY IS %s. Market closed. Skipping prefetch.", today.strftime("%A"))
            return
        run_prefetch()
        return

    # Morning / Afternoon: full pre-flight check
    if not preflight_check(args.dry_run):
        return

    if args.mode == "morning":
        run_morning(args.capital, args.dry_run)
    elif args.mode == "afternoon":
        run_afternoon(args.capital, args.dry_run)


if __name__ == "__main__":
    main()
