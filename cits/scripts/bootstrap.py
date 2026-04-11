"""CITS Bootstrap - all-in-one VPS setup + 2170 decision.

Run ONCE on VPS. It:
1. Fixes .env (adds KABU_API_PASSWORD if missing, ensures UTF-8)
2. Analyzes 2170 (board info + decision)
3. Sells 2170 ONLY if price > entry + margin (absolute no-loss rule)
4. Starts vps_agent in background (for future remote control)
5. Registers all task scheduler entries
6. Pushes results to GitHub

Usage (VPS):
    C:\\cits\\venv\\Scripts\\python.exe -m cits.scripts.bootstrap
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        try:
            load_dotenv(env_path, override=True)
        except UnicodeDecodeError:
            load_dotenv(env_path, override=True, encoding="cp932")
except ImportError:
    pass


REPO_ROOT = Path("C:/cits/repo")
ENV_FILE = REPO_ROOT / "cits" / ".env"
RESULT_FILE = REPO_ROOT / "cits" / "logs" / "bootstrap_result.json"
BRANCH = "claude/continue-kabusute-DmFKB"

ENTRY_PRICE = 580
MIN_PROFIT_PRICE = 585


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def fix_env():
    log("Step 1: Fixing .env...")
    if not ENV_FILE.exists():
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        ENV_FILE.write_text("", encoding="utf-8")

    try:
        content = ENV_FILE.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = ENV_FILE.read_text(encoding="cp932", errors="replace")

    existing_keys = {}
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            existing_keys[k.strip()] = v.strip()

    required = {
        "KABU_API_PASSWORD": "hiroki0380",
        "KABU_ORDER_PASSWORD": "hiroki0380HM",
    }

    changed = False
    for k, default_v in required.items():
        if k not in existing_keys:
            content += f"\n{k}={default_v}"
            changed = True
            log(f"  Added: {k}")
        else:
            log(f"  Exists: {k}")

    if changed:
        ENV_FILE.write_text(content.strip() + "\n", encoding="utf-8")
        log("  .env updated (UTF-8)")
    else:
        log("  .env already complete")

    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE, override=True)
    except Exception:
        pass


def analyze_2170():
    log("Step 2: Analyzing 2170...")
    try:
        from cits.japan.broker.kabu_api import KabuStationAPI
        api = KabuStationAPI()
        api._ensure_token()
        board = api.get_board("2170", exchange=1)
        price = board.get("CurrentPrice", 0)
        prev = board.get("PreviousClose", 0)

        result = {
            "ticker": "2170",
            "current": price,
            "prev_close": prev,
            "open": board.get("OpeningPrice", 0),
            "high": board.get("HighPrice", 0),
            "low": board.get("LowPrice", 0),
            "volume": board.get("TradingVolume", 0),
            "entry_price": ENTRY_PRICE,
            "min_profit_price": MIN_PROFIT_PRICE,
        }
        if prev and price:
            result["change_pct"] = round((price - prev) / prev * 100, 2)
        if price:
            result["pnl_vs_entry"] = price - ENTRY_PRICE
            result["pnl_pct"] = round((price - ENTRY_PRICE) / ENTRY_PRICE * 100, 2)
            result["decision"] = "SELL_OK" if price >= MIN_PROFIT_PRICE else "HOLD_NO_LOSS_RULE"

        log(f"  Price: {price} (prev={prev}, change={result.get('change_pct', '?')}%)")
        log(f"  Decision: {result.get('decision', 'UNKNOWN')}")
        return result
    except Exception as e:
        log(f"  ERROR: {e}")
        return {"error": str(e)}


def sell_2170_if_profit(analysis):
    log("Step 3: Sell 2170 (conditional)...")
    if analysis.get("decision") != "SELL_OK":
        log("  Skipping: not SELL_OK")
        return {"action": "skipped", "reason": analysis.get("decision", "error")}

    marker = REPO_ROOT / "cits" / "logs" / ".sold_2170"
    if marker.exists():
        log("  Already sold")
        return {"action": "already_sold"}

    try:
        from cits.japan.broker.kabu_api import KabuStationAPI
        api = KabuStationAPI()
        api._ensure_token()
        result = api.place_order(
            symbol="2170", side="sell", qty=100,
            order_type="market", exchange=1,
        )
        log(f"  Response: {result}")

        if "error" not in result and "OrderId" in result:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                f"Sold at {datetime.now().isoformat()} price={analysis.get('current')} order_id={result.get('OrderId')}"
            )
            log(f"  SOLD: OrderId={result.get('OrderId')}")
            return {"action": "sold", "order_id": result.get("OrderId"),
                    "price": analysis.get("current")}
        return {"action": "failed", "response": result}
    except Exception as e:
        log(f"  ERROR: {e}")
        return {"action": "exception", "error": str(e)}


def start_vps_agent():
    log("Step 4: Starting vps_agent (background)...")
    try:
        out = subprocess.run(
            ["wmic", "process", "where", "commandline like '%%vps_agent%%'",
             "get", "processid"],
            capture_output=True, text=True, timeout=10, encoding="cp932",
            errors="replace",
        )
        if "ProcessId" in out.stdout and any(
                c.isdigit() for c in out.stdout.split("ProcessId")[1]):
            log("  Already running")
            return {"status": "already_running"}
    except Exception:
        pass

    try:
        subprocess.Popen(
            [r"C:\cits\venv\Scripts\pythonw.exe", "-m", "cits.scripts.vps_agent"],
            cwd=str(REPO_ROOT),
            creationflags=0x08000000 | 0x00000200,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        log("  vps_agent started")
        return {"status": "started"}
    except Exception as e:
        log(f"  ERROR: {e}")
        return {"status": "failed", "error": str(e)}


def register_tasks():
    log("Step 5: Registering task scheduler...")
    tasks = [
        ("CITS_Afternoon", ["schtasks", "/Change", "/TN", "CITS_Afternoon", "/ST", "15:20"]),
        ("CITS_PositionMonitor", ["schtasks", "/Create", "/TN", "CITS_PositionMonitor",
                                  "/TR", r"C:\cits\repo\cits\run_monitor.bat",
                                  "/SC", "DAILY", "/ST", "09:30", "/RI", "30",
                                  "/DU", "05:30",
                                  "/D", "MON,TUE,WED,THU,FRI", "/F"]),
        ("CITS_StartupRecovery", ["schtasks", "/Create", "/TN", "CITS_StartupRecovery",
                                  "/TR", r"C:\cits\repo\cits\run_morning.bat",
                                  "/SC", "ONSTART", "/DELAY", "0005:00", "/F"]),
        ("CITS_VPSAgent", ["schtasks", "/Create", "/TN", "CITS_VPSAgent",
                           "/TR", r"C:\cits\repo\cits\run_agent.bat",
                           "/SC", "ONSTART", "/DELAY", "0002:00", "/F"]),
    ]
    results = {}
    for name, cmd in tasks:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=10, encoding="cp932", errors="replace")
            results[name] = "ok" if r.returncode == 0 else f"rc={r.returncode}"
            log(f"  {name}: {results[name]}")
        except Exception as e:
            results[name] = f"error: {e}"
            log(f"  {name}: error {e}")
    return results


def push_result(result):
    log("Step 6: Pushing to GitHub...")
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    try:
        subprocess.run(["git", "pull", "origin", BRANCH, "--quiet"],
                       cwd=str(REPO_ROOT), capture_output=True, timeout=30)
        subprocess.run(["git", "add", "-f", "cits/logs/bootstrap_result.json"],
                       cwd=str(REPO_ROOT), capture_output=True, timeout=10)
        subprocess.run(["git", "commit", "-m",
                        f"bootstrap: {datetime.now().isoformat()}", "--quiet"],
                       cwd=str(REPO_ROOT), capture_output=True, timeout=10)
        r = subprocess.run(["git", "push", "origin", BRANCH, "--quiet"],
                           cwd=str(REPO_ROOT), capture_output=True, timeout=30)
        if r.returncode == 0:
            log("  Pushed to GitHub")
            return True
    except Exception as e:
        log(f"  Push failed: {e}")
    return False


def main():
    log("=" * 60)
    log("CITS Bootstrap Starting")
    log("=" * 60)

    result = {"timestamp": datetime.now().isoformat()}

    try:
        fix_env()
        result["env_fix"] = "ok"
    except Exception as e:
        result["env_fix"] = f"error: {e}"

    analysis = analyze_2170()
    result["analysis"] = analysis

    sell_result = sell_2170_if_profit(analysis)
    result["sell"] = sell_result

    agent_result = start_vps_agent()
    result["vps_agent"] = agent_result

    task_result = register_tasks()
    result["tasks"] = task_result

    push_result(result)

    log("=" * 60)
    log("Bootstrap complete")
    log("=" * 60)
    print()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
