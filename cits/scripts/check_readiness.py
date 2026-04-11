"""CITS Readiness Check -- Pre-launch validation script.

Checks all prerequisites for live trading:
  1. pkl cache files exist (ETF + market)
  2. .env has both passwords (API + order)
  3. kabuStation API responds (localhost:18080)
  4. Task scheduler tasks exist (Windows)
  5. Python dependencies importable
  6. Key scripts compile without errors

Usage:
    python -m cits.scripts.check_readiness
    python -m cits.scripts.check_readiness --skip-api   (skip API check if kabuStation not running)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------
# Paths
# ---------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CITS_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = CITS_ROOT / "data"
SCRIPTS_DIR = CITS_ROOT / "scripts"

# Load .env (handle Japanese Windows cp932 encoding)
try:
    from dotenv import load_dotenv
    env_path = CITS_ROOT / ".env"
    if env_path.exists():
        try:
            load_dotenv(env_path, override=True)
        except UnicodeDecodeError:
            load_dotenv(env_path, override=True, encoding="cp932")
    root_env = PROJECT_ROOT / ".env"
    if root_env.exists():
        try:
            load_dotenv(root_env, override=False)
        except UnicodeDecodeError:
            load_dotenv(root_env, override=False, encoding="cp932")
except ImportError:
    pass


def _pass(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def _info(msg: str) -> None:
    print(f"  [INFO] {msg}")


# ---------------------------------------------------------------
# Check 1: Cache files
# ---------------------------------------------------------------
def check_caches() -> tuple[int, int]:
    """Check pkl cache files for today."""
    print("\n=== Cache Files ===")
    passes = 0
    fails = 0
    today = date.today()
    ds = today.strftime("%Y%m%d")

    etf_cache = DATA_DIR / f"etf_cache_{ds}.pkl"
    market_cache = DATA_DIR / f"market_cache_{ds}.pkl"

    if etf_cache.exists():
        size = etf_cache.stat().st_size
        _pass(f"ETF cache: {etf_cache.name} ({size:,} bytes)")
        passes += 1
    else:
        _fail(f"ETF cache missing: {etf_cache.name}")
        _info("Run prefetch mode first: python -m cits.scripts.live_trader --mode prefetch")
        fails += 1

    if market_cache.exists():
        size = market_cache.stat().st_size
        _pass(f"Market cache: {market_cache.name} ({size:,} bytes)")
        passes += 1
    else:
        _warn(f"Market cache missing: {market_cache.name}")
        _info("Afternoon mode will fall back to ETF-only if no cache")
        # Warn, not fail -- fallback exists

    # Check ticker cache
    ticker_cache = DATA_DIR / "tse_tickers.json"
    if ticker_cache.exists():
        _pass(f"Ticker list cache: {ticker_cache.name}")
        passes += 1
    else:
        _info("Ticker list cache not found (will be fetched from JPX)")

    return passes, fails


# ---------------------------------------------------------------
# Check 2: Environment variables
# ---------------------------------------------------------------
def check_env() -> tuple[int, int]:
    """Check .env has required passwords."""
    print("\n=== Environment Variables ===")
    passes = 0
    fails = 0

    env_file = CITS_ROOT / ".env"
    if env_file.exists():
        _pass(f".env file exists: {env_file}")
    else:
        _fail(f".env file missing: {env_file}")
        fails += 1
        return passes, fails

    api_pw = os.environ.get("KABU_API_PASSWORD", "")
    if api_pw:
        _pass(f"KABU_API_PASSWORD set ({len(api_pw)} chars)")
        passes += 1
    else:
        _fail("KABU_API_PASSWORD not set")
        fails += 1

    order_pw = os.environ.get("KABU_ORDER_PASSWORD", "")
    if order_pw:
        _pass(f"KABU_ORDER_PASSWORD set ({len(order_pw)} chars)")
        passes += 1
    else:
        _fail("KABU_ORDER_PASSWORD not set")
        fails += 1

    if api_pw and order_pw and api_pw == order_pw:
        _warn("API password and order password are identical")

    return passes, fails


# ---------------------------------------------------------------
# Check 3: kabuStation API
# ---------------------------------------------------------------
def check_api(skip: bool = False) -> tuple[int, int]:
    """Check kabuStation API responds."""
    print("\n=== kabuStation API ===")
    if skip:
        _info("Skipped (--skip-api)")
        return 0, 0

    passes = 0
    fails = 0

    import requests
    api_pw = os.environ.get("KABU_API_PASSWORD", "")
    if not api_pw:
        _fail("Cannot test API: KABU_API_PASSWORD not set")
        return 0, 1

    try:
        r = requests.post(
            "http://localhost:18080/kabusapi/token",
            json={"APIPassword": api_pw},
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json()
            token = data.get("Token", "")
            _pass(f"Token acquired ({len(token)} chars)")
            passes += 1
        else:
            _fail(f"Token request failed: HTTP {r.status_code}")
            _info("kabuStation may need re-login via GUI")
            fails += 1
    except requests.ConnectionError:
        _fail("Connection refused. kabuStation not running on localhost:18080")
        _info("Start kabuStation and login before trading")
        fails += 1
    except Exception as e:
        _fail(f"API check error: {e}")
        fails += 1

    return passes, fails


# ---------------------------------------------------------------
# Check 4: Task scheduler
# ---------------------------------------------------------------
def check_tasks() -> tuple[int, int]:
    """Check task scheduler tasks exist (Windows only)."""
    print("\n=== Task Scheduler ===")
    passes = 0
    fails = 0

    if sys.platform != "win32":
        _info("Not Windows -- skipping task scheduler check")
        return 0, 0

    required_tasks = [
        "CITS_LiveTrader",
        "CITS_Prefetch",
        "CITS_Afternoon",
    ]

    for task_name in required_tasks:
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", task_name, "/FO", "LIST"],
                capture_output=True, text=True, encoding="cp932",
                timeout=10,
            )
            if result.returncode == 0:
                # Extract status
                for line in result.stdout.splitlines():
                    if "Status" in line or "状態" in line:
                        _pass(f"{task_name}: {line.strip()}")
                        break
                else:
                    _pass(f"{task_name}: exists")
                passes += 1
            else:
                _fail(f"{task_name}: NOT FOUND")
                fails += 1
        except Exception as e:
            _warn(f"{task_name}: check failed ({e})")

    return passes, fails


# ---------------------------------------------------------------
# Check 5: Python dependencies
# ---------------------------------------------------------------
def check_deps() -> tuple[int, int]:
    """Check critical Python dependencies are importable."""
    print("\n=== Python Dependencies ===")
    passes = 0
    fails = 0

    deps = [
        "pandas", "yfinance", "requests", "dotenv",
    ]

    for dep in deps:
        try:
            __import__(dep)
            _pass(f"{dep}")
            passes += 1
        except ImportError:
            _fail(f"{dep} not importable")
            fails += 1

    # Check CITS modules
    cits_modules = [
        "cits.scripts.live_trader",
        "cits.scripts.solve_equation",
        "cits.japan.broker.kabu_api",
        "cits.japan.broker.software_oco",
    ]

    for mod in cits_modules:
        try:
            __import__(mod)
            _pass(f"{mod}")
            passes += 1
        except ImportError as e:
            _fail(f"{mod}: {e}")
            fails += 1

    return passes, fails


# ---------------------------------------------------------------
# Check 6: Script compilation
# ---------------------------------------------------------------
def check_compile() -> tuple[int, int]:
    """Check key scripts compile without errors."""
    print("\n=== Script Compilation ===")
    passes = 0
    fails = 0

    scripts = [
        SCRIPTS_DIR / "live_trader.py",
        SCRIPTS_DIR / "solve_equation.py",
        CITS_ROOT / "japan" / "broker" / "kabu_api.py",
        CITS_ROOT / "japan" / "broker" / "software_oco.py",
    ]

    for script in scripts:
        if not script.exists():
            _fail(f"File not found: {script.name}")
            fails += 1
            continue
        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(script)],
                capture_output=True, text=True, encoding="utf-8",
                timeout=10,
            )
            if result.returncode == 0:
                _pass(f"{script.name}")
                passes += 1
            else:
                _fail(f"{script.name}: {result.stderr.strip()}")
                fails += 1
        except Exception as e:
            _fail(f"{script.name}: {e}")
            fails += 1

    return passes, fails


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="CITS Readiness Check")
    parser.add_argument("--skip-api", action="store_true", help="Skip kabuStation API check")
    args = parser.parse_args()

    print("=" * 60)
    print("CITS READINESS CHECK")
    print(f"Date: {date.today()} ({date.today().strftime('%A')})")
    print(f"Project: {PROJECT_ROOT}")
    print("=" * 60)

    total_pass = 0
    total_fail = 0

    for check_fn, kwargs in [
        (check_caches, {}),
        (check_env, {}),
        (check_api, {"skip": args.skip_api}),
        (check_tasks, {}),
        (check_deps, {}),
        (check_compile, {}),
    ]:
        p, f = check_fn(**kwargs)
        total_pass += p
        total_fail += f

    print("\n" + "=" * 60)
    if total_fail == 0:
        print(f"RESULT: ALL PASS ({total_pass} checks passed)")
        print("System is READY for live trading.")
    else:
        print(f"RESULT: {total_fail} FAILURES ({total_pass} passed, {total_fail} failed)")
        print("FIX failures before going live!")
    print("=" * 60)

    sys.exit(1 if total_fail > 0 else 0)


if __name__ == "__main__":
    main()
