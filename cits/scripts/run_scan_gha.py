"""
CITS Daily Scan -- GitHub Actions runner (run_scan_gha.py)

Runs independently of VPS. Fetches market data via yfinance,
runs CIS + Kei-kun scans, and writes scan_results.json.
Claude reads this file to answer "今日の想定は？" anytime.

Usage:
    python -m cits.scripts.run_scan_gha              # full scan
    python -m cits.scripts.run_scan_gha --etf-only   # fast ETF scan only
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
OUTPUT_FILE = DATA_DIR / "scan_results.json"
FULL_SCAN_TIMEOUT = 360  # seconds — give yfinance 6 min before falling back


def _fetch_gate_summary(gate_data: dict) -> dict:
    """Extract human-readable market gate info."""
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


def run(etf_only: bool = False) -> dict:
    from cits.scripts.live_trader import (
        _fetch_market_gate_data,
        check_market_gate,
        fetch_etf_data,
        fetch_full_data,
        scan_cis,
        scan_keikun,
    )

    now_jst = datetime.now(JST)
    print(f"=== CITS Scan {now_jst.strftime('%Y-%m-%d %H:%M JST')} ===")

    # ── 1. Market gate ─────────────────────────────────────────────
    print("[1] Fetching market gate data (Nikkei225 + VIX)...")
    gate_data = _fetch_market_gate_data()
    gate_open, gate_reason, size_mult = check_market_gate(gate_data)
    gate_summary = _fetch_gate_summary(gate_data)

    print(f"    Gate: {'OPEN' if gate_open else 'CLOSED'} ({gate_reason})")
    print(f"    N225={gate_summary.get('nikkei225')}  "
          f"SMA20={gate_summary.get('nikkei225_sma20')}  "
          f"VIX={gate_summary.get('vix')}")

    # ── 2. ETF scan (fast, always runs) ───────────────────────────
    print("[2] Fetching ETF data...")
    etf_data = fetch_etf_data()
    print(f"    ETF data: {len(etf_data)} tickers")

    # ── 3. Full scan (try with timeout) ───────────────────────────
    full_data: dict = {}
    scan_mode = "etf_only"
    if not etf_only:
        print(f"[3] Attempting full TSE scan (timeout={FULL_SCAN_TIMEOUT}s)...")
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(fetch_full_data)
                full_data = future.result(timeout=FULL_SCAN_TIMEOUT)
            scan_mode = "full"
            print(f"    Full scan OK: {len(full_data)} tickers")
        except FuturesTimeout:
            print(f"    Full scan timed out after {FULL_SCAN_TIMEOUT}s — using ETF only")
        except Exception as exc:
            print(f"    Full scan failed ({exc}) — using ETF only")
    else:
        print("[3] ETF-only mode — skipping full scan")

    # ── 4. Run CIS + Kei-kun ──────────────────────────────────────
    all_data = {**etf_data, **full_data}
    capital = 100_000

    print(f"[4] Scanning {len(all_data)} tickers (CIS + Kei-kun)...")
    cis_signals = scan_cis(all_data, capital)
    kei_signals = scan_keikun(all_data, capital)
    print(f"    CIS candidates: {len(cis_signals)}")
    print(f"    Kei-kun candidates: {len(kei_signals)}")

    # ── 5. Build output ───────────────────────────────────────────
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

    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"[5] Saved → {OUTPUT_FILE}")

    # ── 6. Summary ────────────────────────────────────────────────
    print("\n=== TOP CANDIDATES ===")
    if not gate_open:
        print(f"  *** MARKET GATE CLOSED: {gate_reason} ***")
    for s in cis_signals[:5]:
        print(f"  CIS  {s['ticker']:6s} ¥{s['price']:,.0f}  "
              f"breakout={s['breakout_pct']:+.1f}%  vol_ratio={s['vol_ratio']:.1f}x  "
              f"score={s['score']}")
    for s in kei_signals[:5]:
        print(f"  KEI  {s['ticker']:6s} ¥{s['price']:,.0f}  "
              f"breakout={s.get('breakout_pct', 0):+.1f}%  score={s.get('score', 0)}")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="CITS daily scan (GHA)")
    parser.add_argument("--etf-only", action="store_true",
                        help="Only scan ETFs (fast, ~30s)")
    args = parser.parse_args()
    run(etf_only=args.etf_only)


if __name__ == "__main__":
    main()
