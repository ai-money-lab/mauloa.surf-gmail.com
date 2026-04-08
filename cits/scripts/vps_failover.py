"""CITS VPS Failover Monitor -- Auto-switch to local PC when VPS is down.

Runs on the local PC (not the VPS). Monitors VPS health every N minutes.
If VPS is unreachable, starts local trading as fallback.

Setup:
  1. Run on local PC as a scheduled task (e.g. every 5 min from 08:00-15:30)
  2. Set VPS_HOST, VPS_SSH_KEY environment variables
  3. Local PC needs: Python, cits code, kabuStation API access

Usage:
    python -m cits.scripts.vps_failover --check          # one-time health check
    python -m cits.scripts.vps_failover --monitor         # continuous monitoring
    python -m cits.scripts.vps_failover --force-local     # force local execution
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

# Configuration
VPS_HOST = os.environ.get("CITS_VPS_HOST", "150.66.3.162")
VPS_SSH_PORT = int(os.environ.get("CITS_VPS_SSH_PORT", "22"))
VPS_VNC_PORT = int(os.environ.get("CITS_VPS_VNC_PORT", "5900"))
KABU_API_PORT = 18080
CHECK_INTERVAL_SEC = 300  # 5 minutes
MAX_FAILURES_BEFORE_FAILOVER = 2

LOG_DIR = Path(__file__).resolve().parent.parent / "logs" / "failover"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def check_port(host: str, port: int, timeout: float = 5.0) -> bool:
    """Check if a TCP port is open."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def check_vps_health() -> dict:
    """Run comprehensive VPS health check.

    Returns:
        dict with keys: healthy (bool), ssh (bool), vnc (bool),
                       kabu_api (bool), details (str)
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "ssh": False,
        "vnc": False,
        "kabu_api": False,
        "healthy": False,
        "details": "",
    }

    # Check SSH
    results["ssh"] = check_port(VPS_HOST, VPS_SSH_PORT, timeout=5)

    # Check VNC (TightVNC on port 5900)
    results["vnc"] = check_port(VPS_HOST, VPS_VNC_PORT, timeout=5)

    # Check kabuStation API (via SSH tunnel or direct if VPN)
    # Note: kabuStation API is on localhost:18080 on the VPS, not externally accessible
    # We check SSH as a proxy for VPS health
    results["kabu_api"] = results["ssh"]  # assume API is up if VPS is reachable

    # Overall health: SSH must be up
    results["healthy"] = results["ssh"]

    details = []
    if results["ssh"]:
        details.append("SSH:OK")
    else:
        details.append("SSH:FAIL")
    if results["vnc"]:
        details.append("VNC:OK")
    else:
        details.append("VNC:FAIL")
    results["details"] = " | ".join(details)

    return results


def run_local_trading(dry_run: bool = True) -> None:
    """Execute trading on local PC as fallback.

    Only runs in dry-run mode by default for safety.
    Live execution requires explicit --force-local flag.
    """
    logger.warning("=" * 60)
    logger.warning("VPS FAILOVER -- Running trading on LOCAL PC")
    logger.warning("=" * 60)

    now = datetime.now()
    hour = now.hour
    minute = now.minute

    # Determine which mode to run based on time
    if hour < 9 or (hour == 8 and minute >= 25):
        mode = "morning"
    elif 14 <= hour < 15:
        mode = "prefetch"
    elif hour >= 15:
        mode = "afternoon"
    else:
        logger.info("Not a trading window (current: %02d:%02d). Skipping.", hour, minute)
        return

    cmd = [
        sys.executable, "-m", "cits.scripts.live_trader",
        "--mode", mode,
        "--capital", "300000",
    ]
    if dry_run:
        cmd.append("--dry-run")

    logger.info("Executing: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=600,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        logger.info("Exit code: %d", result.returncode)
        if result.stdout:
            logger.info("Output:\n%s", result.stdout[-2000:])
        if result.returncode != 0 and result.stderr:
            logger.error("Stderr:\n%s", result.stderr[-1000:])
    except subprocess.TimeoutExpired:
        logger.error("Local trading timed out after 600s")
    except Exception as e:
        logger.error("Local trading failed: %s", e)


def monitor_loop(dry_run: bool = True) -> None:
    """Continuous monitoring loop. Triggers failover after consecutive failures."""
    logger.info("VPS failover monitor started (interval=%ds, failover after %d failures)",
                CHECK_INTERVAL_SEC, MAX_FAILURES_BEFORE_FAILOVER)
    logger.info("VPS: %s (SSH:%d, VNC:%d)", VPS_HOST, VPS_SSH_PORT, VPS_VNC_PORT)

    consecutive_failures = 0
    failover_triggered = False

    while True:
        now = datetime.now()

        # Only monitor during market hours (08:00-15:30)
        if now.weekday() >= 5:
            logger.debug("Weekend -- sleeping")
            time.sleep(CHECK_INTERVAL_SEC)
            continue

        if now.hour < 8 or (now.hour >= 15 and now.minute > 30):
            logger.debug("Outside market hours -- sleeping")
            consecutive_failures = 0
            failover_triggered = False
            time.sleep(CHECK_INTERVAL_SEC)
            continue

        health = check_vps_health()
        logger.info(
            "Health check: %s [%s]",
            "HEALTHY" if health["healthy"] else "UNHEALTHY",
            health["details"],
        )

        if health["healthy"]:
            consecutive_failures = 0
            if failover_triggered:
                logger.info("VPS recovered. Failover mode OFF.")
                failover_triggered = False
        else:
            consecutive_failures += 1
            logger.warning(
                "VPS unhealthy (%d/%d consecutive failures)",
                consecutive_failures, MAX_FAILURES_BEFORE_FAILOVER,
            )

            if consecutive_failures >= MAX_FAILURES_BEFORE_FAILOVER and not failover_triggered:
                logger.error("FAILOVER TRIGGERED -- switching to local PC")
                failover_triggered = True
                run_local_trading(dry_run=dry_run)

        time.sleep(CHECK_INTERVAL_SEC)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_DIR / "failover.log", encoding="utf-8"),
        ],
    )

    parser = argparse.ArgumentParser(description="CITS VPS Failover Monitor")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true",
                       help="One-time VPS health check")
    group.add_argument("--monitor", action="store_true",
                       help="Continuous monitoring loop")
    group.add_argument("--force-local", action="store_true",
                       help="Force local trading execution")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Local trading in dry-run mode (default: True)")
    parser.add_argument("--live", action="store_true",
                        help="Local trading in LIVE mode (use with caution)")
    args = parser.parse_args()

    actual_dry_run = not args.live

    if args.check:
        health = check_vps_health()
        status = "HEALTHY" if health["healthy"] else "UNHEALTHY"
        print(f"VPS Status: {status}")
        print(f"  SSH:      {'OK' if health['ssh'] else 'FAIL'}")
        print(f"  VNC:      {'OK' if health['vnc'] else 'FAIL'}")
        print(f"  kabuAPI:  {'OK' if health['kabu_api'] else 'FAIL'}")
        sys.exit(0 if health["healthy"] else 1)

    elif args.monitor:
        monitor_loop(dry_run=actual_dry_run)

    elif args.force_local:
        run_local_trading(dry_run=actual_dry_run)


if __name__ == "__main__":
    main()
