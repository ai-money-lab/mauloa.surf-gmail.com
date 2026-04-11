"""CITS Daily Trade Report -- Email to mauloa.surf@gmail.com.

Generates a daily summary of all trading activity and sends via email.
Can be run manually or called from live_trader after trade execution.

Usage:
    python -m cits.scripts.daily_report
    python -m cits.scripts.daily_report --dry-run    # print only, no send
"""

from __future__ import annotations

import json
import logging
import smtplib
import sys
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

logger = logging.getLogger("cits.daily_report")

LOG_DIR = Path(__file__).resolve().parent.parent / "logs" / "live_trades"
POSITION_DB = Path(__file__).resolve().parent.parent / "data" / "positions.json"
REPORT_DIR = Path(__file__).resolve().parent.parent / "logs" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

RECIPIENT = "mauloa.surf@gmail.com"


def _load_todays_trade_logs() -> list[dict]:
    today_str = date.today().strftime("%Y-%m-%d")
    logs = []
    if not LOG_DIR.exists():
        return logs
    for f in sorted(LOG_DIR.glob(f"trades_{today_str}_*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            logs.append(data)
        except Exception as e:
            logger.warning("Failed to read %s: %s", f, e)
    return logs


def _load_positions() -> list[dict]:
    if POSITION_DB.exists():
        try:
            return json.loads(POSITION_DB.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def generate_report() -> str:
    today = date.today()
    now = datetime.now()
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("CITS Daily Trade Report")
    lines.append(f"Date: {today} ({today.strftime('%A')})")
    lines.append(f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 60)
    lines.append("")
    trade_logs = _load_todays_trade_logs()
    if not trade_logs:
        lines.append("[No trade logs found for today]")
        lines.append("")
    else:
        total_signals = 0
        total_executed = 0
        for log in trade_logs:
            mode = log.get("mode", "unknown")
            signals = log.get("signals", [])
            executions = log.get("executions", [])
            total_signals += len(signals)
            total_executed += len([e for e in executions if e.get("status") in ("filled", "dry_run")])
            lines.append(f"--- {mode.upper()} Session ({log.get('timestamp', '')}) ---")
            lines.append(f"  Signals found: {len(signals)}")
            lines.append(f"  Executed: {len(executions)}")
            lines.append("")
            if signals:
                lines.append("  Top Signals:")
                for s in signals[:5]:
                    lines.append(f"    [{s.get('strategy', '?')}] {s.get('ticker', '?')} Y{s.get('price', 0):.1f} x{s.get('size', 0)} score={s.get('score', 0):.1f}")
                lines.append("")
            if executions:
                lines.append("  Executions:")
                for e in executions:
                    lines.append(f"    [{e.get('strategy', '?')}] {e.get('ticker', '?')} x{e.get('size', 0)} @ Y{e.get('price', 0):.1f} SL=Y{e.get('stop_loss', 0):.1f} status={e.get('status', 'unknown')}")
                lines.append("")
        lines.append(f"TOTAL: {total_signals} signals found, {total_executed} executed")
        lines.append("")
    positions = _load_positions()
    open_positions = [p for p in positions if p.get("status") == "open"]
    lines.append("--- Open Positions ---")
    if not open_positions:
        lines.append("  (No open positions)")
    else:
        for p in open_positions:
            hold = p.get("hold_days", 0)
            lines.append(f"  [{p.get('strategy', '?')}] {p.get('ticker', '?')} x{p.get('size', 0)} @ Y{p.get('entry_price', 0):.1f} SL=Y{p.get('stop_loss', 0):.1f} hold={hold}d high=Y{p.get('high_since_entry', 0):.1f}")
    lines.append("")
    lines.append("=" * 60)
    lines.append("End of Report")
    lines.append("=" * 60)
    return "\n".join(lines)


def send_report(report: str, dry_run: bool = False) -> bool:
    import os
    today_str = date.today().strftime("%Y-%m-%d")
    report_path = REPORT_DIR / f"daily_{today_str}.txt"
    report_path.write_text(report, encoding="utf-8")
    logger.info("Report saved: %s", report_path)
    if dry_run:
        logger.info("DRY RUN -- email not sent")
        return True
    smtp_user = os.environ.get("GMAIL_USER", RECIPIENT)
    smtp_pass = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not smtp_pass:
        logger.warning("GMAIL_APP_PASSWORD not set. Report saved to %s but NOT emailed.", report_path)
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = RECIPIENT
        msg["Subject"] = f"CITS Daily Report - {today_str}"
        msg.attach(MIMEText(report, "plain", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [RECIPIENT], msg.as_string())
        logger.info("Report emailed to %s", RECIPIENT)
        return True
    except Exception as e:
        logger.error("Email send failed: %s. Report saved to %s", e, report_path)
        return False


def main() -> None:
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
    parser = argparse.ArgumentParser(description="CITS Daily Report")
    parser.add_argument("--dry-run", action="store_true", help="Print report only, do not send email")
    args = parser.parse_args()
    report = generate_report()
    print(report)
    send_report(report, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
