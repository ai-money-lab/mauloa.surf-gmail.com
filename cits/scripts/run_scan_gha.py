"""
CITS Daily Scan -- GitHub Actions runner (run_scan_gha.py)

Runs independently of VPS. Fetches market data via yfinance,
runs CIS + Kei-kun scans, and writes scan_results.json.
Claude reads this file to answer "今日の想定は？" anytime.

Modes:
    python -m cits.scripts.run_scan_gha                    # full TSE scan → scan_results.json
    python -m cits.scripts.run_scan_gha --etf-only         # ETF scan only → scan_results.json
    python -m cits.scripts.run_scan_gha --market-only      # N225+VIX only → market_status.json (fast)
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SCAN_RESULTS_FILE = DATA_DIR / "scan_results.json"
MARKET_STATUS_FILE = DATA_DIR / "market_status.json"
FULL_SCAN_TIMEOUT = 360  # seconds


def _fetch_gate_summary(gate_data: dict) -> dict:
    """Extract human-readable market gate info from raw gate_data."""
    summary: dict = {}
    n225 = gate_data.get("^N225")
    vix = gate_data.get("^VIX")
    if n225 is not None and len(n225) >= 21:
        closes = [float(x) for x in n225["Close"]]
        price = closes[-1]
        sma20 = sum(closes[-20:]) / 20
        summary["nikkei225"] = round(price, 0)
        summary["nikkei225_sma20"] = round(sma20, 0)
        summary["nikkei225_vs_sma20_pct"] = round((price / sma20 - 1) * 100, 2)
    if vix is not None and len(vix) >= 1:
        summary["vix"] = round(float(vix["Close"].iloc[-1]), 2)
    return summary


def run_market_only() -> dict:
    """
    Fast mode (~10s): fetch N225 + VIX only, write market_status.json.
    Used by 5-minute market monitor to keep gate status fresh.
    """
    from cits.scripts.live_trader import _fetch_market_gate_data, check_market_gate

    now_jst = datetime.now(JST)
    print(f"=== Market Status {now_jst.strftime('%Y-%m-%d %H:%M JST')} ===")

    gate_data = _fetch_market_gate_data()
    gate_open, gate_reason, size_mult = check_market_gate(gate_data)
    gate_summary = _fetch_gate_summary(gate_data)

    result = {
        "timestamp": now_jst.isoformat(),
        "market_gate": {
            "open": gate_open,
            "reason": gate_reason,
            "size_multiplier": size_mult,
            **gate_summary,
        },
    }
    MARKET_STATUS_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    status = "OPEN ✅" if gate_open else "CLOSED ❌"
    print(f"  Gate: {status}  N225={gate_summary.get('nikkei225')}  "
          f"vs SMA20={gate_summary.get('nikkei225_vs_sma20_pct'):+.2f}%  "
          f"VIX={gate_summary.get('vix')}")
    print(f"  Reason: {gate_reason}")
    print(f"  → {MARKET_STATUS_FILE}")
    return result


def run_scan(etf_only: bool = False) -> dict:
    """
    Scan mode: run CIS + Kei-kun, write scan_results.json.
    etf_only=True → only scan 9 ETFs (fast, ~30s)
    etf_only=False → full TSE scan (~5-7 min, timeout=6 min)
    """
    from cits.scripts.live_trader import (
        _fetch_market_gate_data,
        check_market_gate,
        fetch_etf_data,
        fetch_full_data,
        scan_cis,
        scan_keikun,
    )

    now_jst = datetime.now(JST)
    mode_label = "ETF-only" if etf_only else "Full TSE"
    print(f"=== CITS {mode_label} Scan {now_jst.strftime('%Y-%m-%d %H:%M JST')} ===")

    # ── 1. Market gate ──────────────────────────────────────────
    print("[1] Market gate (N225 + VIX)...")
    gate_data = _fetch_market_gate_data()
    gate_open, gate_reason, size_mult = check_market_gate(gate_data)
    gate_summary = _fetch_gate_summary(gate_data)
    print(f"    {'OPEN' if gate_open else 'CLOSED'}  "
          f"N225={gate_summary.get('nikkei225')}  VIX={gate_summary.get('vix')}")

    # ── 2. ETF data (always) ────────────────────────────────────
    print("[2] ETF data...")
    etf_data = fetch_etf_data()
    print(f"    {len(etf_data)} ETFs loaded")

    # ── 3. Full TSE data (optional) ─────────────────────────────
    full_data: dict = {}
    scan_mode = "etf_only"
    if not etf_only:
        print(f"[3] Full TSE scan (timeout={FULL_SCAN_TIMEOUT}s)...")
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(fetch_full_data)
                full_data = future.result(timeout=FULL_SCAN_TIMEOUT)
            scan_mode = "full"
            print(f"    {len(full_data)} tickers loaded")
        except FuturesTimeout:
            print(f"    Timed out after {FULL_SCAN_TIMEOUT}s → ETF only")
        except Exception as exc:
            print(f"    Failed ({exc}) → ETF only")
    else:
        print("[3] ETF-only — skipping full TSE")

    # ── 4. Scan ─────────────────────────────────────────────────
    all_data = {**etf_data, **full_data}
    capital = 100_000
    print(f"[4] Scanning {len(all_data)} tickers...")
    cis_signals = scan_cis(all_data, capital)
    kei_signals = scan_keikun(all_data, capital)
    print(f"    CIS={len(cis_signals)}  KEI={len(kei_signals)}")

    # ── 5. Output ───────────────────────────────────────────────
    result = {
        "scan_time": now_jst.isoformat(),
        "scan_mode": scan_mode,
        "tickers_scanned": len(all_data),
        "market_gate": {
            "open": gate_open,
            "reason": gate_reason,
            "size_multiplier": size_mult,
            **gate_summary,
        },
        "cis_candidates": cis_signals[:15],
        "keikun_candidates": kei_signals[:15],
        "cis_count": len(cis_signals),
        "keikun_count": len(kei_signals),
    }
    SCAN_RESULTS_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"[5] Saved → {SCAN_RESULTS_FILE}")

    if not gate_open:
        print(f"\n*** MARKET GATE CLOSED: {gate_reason} ***")
    else:
        print("\n=== TOP CIS CANDIDATES ===")
        for s in cis_signals[:5]:
            print(f"  {s['ticker']:6s}  ¥{s['price']:,.0f}  "
                  f"break={s['breakout_pct']:+.1f}%  vol={s['vol_ratio']:.1f}x  "
                  f"score={s['score']}")
        print("=== TOP KEI CANDIDATES ===")
        for s in kei_signals[:5]:
            print(f"  {s['ticker']:6s}  ¥{s['price']:,.0f}  "
                  f"break={s.get('breakout_pct', 0):+.1f}%  score={s.get('score', 0)}")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="CITS scan (GHA)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--market-only", action="store_true",
                       help="N225+VIX only → market_status.json (fast, ~10s)")
    group.add_argument("--etf-only", action="store_true",
                       help="ETF scan → scan_results.json (fast, ~30s)")
    args = parser.parse_args()

    if args.market_only:
        run_market_only()
    else:
        run_scan(etf_only=args.etf_only)


if __name__ == "__main__":
    main()
