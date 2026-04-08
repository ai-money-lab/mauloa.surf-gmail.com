"""CITS VPS Failover Monitor -- Auto-switch to local PC when VPS is down.

Runs on the local PC (not the VPS). Monitors VPS health every N minutes.
If VPS is unreachable, starts local trading as fallback.

Usage:
    python -m cits.scripts.vps_failover --check
    python -m cits.scripts.vps_failover --monitor
    python -m cits.scripts.vps_failover --force-local
"""

from __future__ import annotations

import argparse
import logging
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("cits.vps_failover")

VPS_HOST = os.environ.get("CITS_VPS_HOST", "150.66.3.162")
VPS_SSH_PORT = int(os.environ.get("CITS_VPS_SSH_PORT", "22"))
VPS_VNC_PORT = int(os.environ.get("CITS_VPS_VNC_PORT", "5900"))
KABU_API_PORT = 18080
CHECK_INTERVAL_SEC = 300
MAX_FAILURES_BEFORE_FAILOVER = 2

LOG_DIR = Path(__file__).resolve().parent.parent / "logs" / "failover"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def check_port(host: str, port: int, timeout: float = 5.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def check_vps_health() -> dict:
    results = {"timestamp": datetime.now().isoformat(), "ssh": False, "vnc": False, "kabu_api": False, "healthy": False, "details": ""}
    results["ssh"] = check_port(VPS_HOST, VPS_SSH_PORT, timeout=5)
    results["vnc"] = check_port(VPS_HOST, VPS_VNC_PORT, timeout=5)
    results["kabu_api"] = results["ssh"]
    results["healthy"] = results["ssh"]
    details = []
    details.append("SSH:OK" if results["ssh"] else "SSH:FAIL")
    details.append("VNC:OK" if results["vnc"] else "VNC:FAIL")
    results["details"] = " | ".join(details)
    return results


def run_local_trading(dry_run: bool = True) -> None:
    logger.warning("VPS FAILOVER -- Running trading on LOCAL PC")
    now = datetime.now()
    hour, minute = now.hour, now.minute
    if hour < 9 or (hour == 8 and minute >= 25):
        mode = "morning"
    elif 14 <= hour < 15:
        mode = "prefetch"
    elif hour >= 15:
        mode = "afternoon"
    else:
        logger.info("Not a trading window. Skipping.")
        return
    cmd = [sys.executable, "-m", "cits.scripts.live_trader", "--mode", mode, "--capital", "300000"]
    if dry_run:
        cmd.append("--dry-run")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=str(Path(__file__).resolve().parent.parent.parent))
        logger.info("Exit code: %d", result.returncode)
        if result.stdout:
            logger.info("Output:\n%s", result.stdout[-2000:])
    except subprocess.TimeoutExpired:
        logger.error("Local trading timed out")
    except Exception as e:
        logger.error("Local trading failed: %s", e)


def monitor_loop(dry_run: bool = True) -> None:
    logger.info("VPS failover monitor started")
    consecutive_failures = 0
    failover_triggered = False
    while True:
        now = datetime.now()
        if now.weekday() >= 5 or now.hour < 8 or (now.hour >= 15 and now.minute > 30):
            consecutive_failures = 0
            failover_triggered = False
            time.sleep(CHECK_INTERVAL_SEC)
            continue
        health = check_vps_health()
        logger.info("Health: %s [%s]", "OK" if health["healthy"] else "FAIL", health["details"])
        if health["healthy"]:
            consecutive_failures = 0
            if failover_triggered:
                logger.info("VPS recovered.")
                failover_triggered = False
        else:
            consecutive_failures += 1
            if consecutive_failures >= MAX_FAILURES_BEFORE_FAILOVER and not failover_triggered:
                logger.error("FAILOVER TRIGGERED")
                failover_triggered = True
                run_local_trading(dry_run=dry_run)
        time.sleep(CHECK_INTERVAL_SEC)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_DIR / "failover.log", encoding="utf-8")])
    parser = argparse.ArgumentParser(description="CITS VPS Failover")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--monitor", action="store_true")
    group.add_argument("--force-local", action="store_true")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    actual_dry_run = not args.live
    if args.check:
        health = check_vps_health()
        print(f"VPS Status: {'HEALTHY' if health['healthy'] else 'UNHEALTHY'}")
        print(f"  SSH: {'OK' if health['ssh'] else 'FAIL'}")
        print(f"  VNC: {'OK' if health['vnc'] else 'FAIL'}")
        print(f"  kabuAPI: {'OK' if health['kabu_api'] else 'FAIL'}")
        sys.exit(0 if health["healthy"] else 1)
    elif args.monitor:
        monitor_loop(dry_run=actual_dry_run)
    elif args.force_local:
        run_local_trading(dry_run=actual_dry_run)


if __name__ == "__main__":
    main()
