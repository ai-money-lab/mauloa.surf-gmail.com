"""CITS Watchdog -- VPS Self-Healing Monitor

Runs every 5 minutes via CITS_Watchdog scheduled task.
Self-contained: no imports from cits.* modules.

Actions:
1. kabuStation API health check (market hours 08:00-16:30 JST)
   -> restart via CITS_KabuStart_IT if down
   -> run full kabu_auto_login_vps if restart fails
2. vps_agent process check -> restart if dead
3. Critical schtask verification -> re-register any missing tasks
4. Push heartbeat to GitHub (on action taken, or every 30 min)
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ===== Config =====
REPO_ROOT = Path("C:/cits/repo")
LOG_DIR = Path("C:/cits/logs")
LOG_FILE = LOG_DIR / "watchdog.log"
LAST_PUSH_FILE = LOG_DIR / ".watchdog_last_push"
STATUS_FILE = REPO_ROOT / "cits" / "data" / "watchdog_status.json"
BRANCH = "claude/continue-kabusute-DmFKB"

JST = timezone(timedelta(hours=9))
MARKET_OPEN_H = 8     # 08:00 JST
MARKET_CLOSE_H = 16   # 16:30 JST
MARKET_CLOSE_M = 30
PUSH_INTERVAL_MIN = 30

# ===== Schtask definitions (name -> /Create command args) =====
TASK_DEFS: dict[str, list[str]] = {
    "CITS_KabuStart_IT": [
        "schtasks", "/Create", "/TN", "CITS_KabuStart_IT",
        "/TR", r"C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe",
        "/SC", "ONCE", "/SD", "12/31/2099", "/ST", "23:59", "/IT", "/F",
    ],
    "CITS_KabuStation_Start": [
        "schtasks", "/Create", "/TN", "CITS_KabuStation_Start",
        "/TR", r"C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe",
        "/SC", "DAILY", "/ST", "08:25",
        "/D", "MON,TUE,WED,THU,FRI", "/IT", "/F",
    ],
    "CITS_LiveTrader": [
        "schtasks", "/Create", "/TN", "CITS_LiveTrader",
        "/TR", r"C:\cits\repo\cits\run_morning.bat",
        "/SC", "DAILY", "/ST", "08:30",
        "/D", "MON,TUE,WED,THU,FRI", "/RL", "HIGHEST", "/F",
    ],
    "CITS_PositionMonitor": [
        "schtasks", "/Create", "/TN", "CITS_PositionMonitor",
        "/TR", r"C:\cits\repo\cits\run_monitor.bat",
        "/SC", "MINUTE", "/MO", "30", "/ST", "09:30", "/ET", "15:25",
        "/RL", "HIGHEST", "/F",
    ],
    "CITS_Afternoon": [
        "schtasks", "/Create", "/TN", "CITS_Afternoon",
        "/TR", r"C:\cits\repo\cits\run_afternoon.bat",
        "/SC", "DAILY", "/ST", "15:20",
        "/D", "MON,TUE,WED,THU,FRI", "/RL", "HIGHEST", "/F",
    ],
    "CITS_Prefetch": [
        "schtasks", "/Create", "/TN", "CITS_Prefetch",
        "/TR", r"C:\cits\repo\cits\run_prefetch.bat",
        "/SC", "DAILY", "/ST", "14:00",
        "/D", "MON,TUE,WED,THU,FRI", "/RL", "HIGHEST", "/F",
    ],
    "CITS_VPSAgent": [
        "schtasks", "/Create", "/TN", "CITS_VPSAgent",
        "/TR", r"C:\cits\repo\cits\run_agent.bat",
        "/SC", "ONSTART", "/DELAY", "0002:00", "/RL", "HIGHEST", "/F",
    ],
    "CITS_StartupRecovery": [
        "schtasks", "/Create", "/TN", "CITS_StartupRecovery",
        "/TR", r"C:\cits\repo\cits\run_morning.bat",
        "/SC", "ONSTART", "/DELAY", "0005:00", "/RL", "HIGHEST", "/F",
    ],
    "CITS_Watchdog": [
        "schtasks", "/Create", "/TN", "CITS_Watchdog",
        "/TR", r"C:\cits\repo\cits\run_watchdog.bat",
        "/SC", "MINUTE", "/MO", "5", "/RL", "HIGHEST", "/F",
    ],
}


def _log(msg: str) -> None:
    ts = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
    line = f"{ts} [watchdog] {msg}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode("ascii", errors="replace").decode(), flush=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    # Rotate at 10MB
    try:
        if LOG_FILE.stat().st_size > 10 * 1024 * 1024:
            backup = LOG_FILE.with_suffix(".log.bak")
            LOG_FILE.replace(backup)
    except OSError:
        pass


def _is_market_hours() -> bool:
    now = datetime.now(JST)
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    total_min = now.hour * 60 + now.minute
    return MARKET_OPEN_H * 60 <= total_min <= MARKET_CLOSE_H * 60 + MARKET_CLOSE_M


def _check_kabu_api() -> bool:
    try:
        import requests  # noqa: PLC0415
        r = requests.post(
            "http://localhost:18080/kabusapi/token",
            json={"APIPassword": os.environ.get("KABU_API_PASSWORD", "hiroki0380")},
            timeout=5,
        )
        return r.status_code == 200
    except Exception:
        return False


def _ensure_kabu_running() -> dict:
    result: dict = {"checked": True, "market_hours": _is_market_hours()}
    if not _is_market_hours():
        result["skipped"] = "outside_market_hours"
        return result

    if _check_kabu_api():
        result["api"] = "ok"
        return result

    _log("kabuStation API down during market hours — attempting restart")
    result["api"] = "down"

    # Step 1: restart via scheduled task
    r = subprocess.run(
        'schtasks /Run /TN "CITS_KabuStart_IT"',
        shell=True, capture_output=True,
        encoding="cp932", errors="replace", timeout=15,
    )
    if r.returncode != 0:
        _log(f"  CITS_KabuStart_IT run failed rc={r.returncode}")
    else:
        _log("  kabuStation start triggered (waiting 30s)")
        time.sleep(30)

    if _check_kabu_api():
        result["restart"] = "ok"
        result["action"] = "restarted_via_task"
        _log("  kabuStation API: OK after restart")
        return result

    # Step 2: full auto-login flow
    _log("  Restart via task failed — running kabu_auto_login_vps")
    proc = subprocess.run(
        [r"C:\cits\venv\Scripts\python.exe", "-m",
         "cits.scripts.kabu_auto_login_vps"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        encoding="cp932", errors="replace", timeout=400,
    )
    result["auto_login_rc"] = proc.returncode
    result["auto_login_tail"] = (proc.stdout or "")[-400:]
    result["action"] = "auto_login_attempted"
    if proc.returncode == 0:
        result["restart"] = "ok_via_auto_login"
        _log("  Auto-login succeeded")
    else:
        result["restart"] = "failed"
        _log(f"  Auto-login failed rc={proc.returncode}")
    return result


def _check_vps_agent() -> dict:
    """Verify vps_agent is running; restart via pythonw if not."""
    result: dict = {}
    try:
        out = subprocess.run(
            ["wmic", "process", "where",
             "commandline like '%%vps_agent%%'", "get", "processid"],
            capture_output=True, text=True, timeout=10,
            encoding="cp932", errors="replace",
        )
        lines = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
        pids = [ln for ln in lines[1:] if ln.isdigit()] if len(lines) > 1 else []
        if pids:
            result["status"] = "running"
            result["pid"] = pids[0]
            return result
    except Exception as exc:
        _log(f"wmic check failed: {exc}")

    _log("vps_agent not running — restarting")
    try:
        subprocess.Popen(
            [r"C:\cits\venv\Scripts\pythonw.exe", "-m", "cits.scripts.vps_agent"],
            cwd=str(REPO_ROOT),
            creationflags=0x08000000 | 0x00000200,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        result["status"] = "restarted"
        result["action"] = "restarted"
        _log("  vps_agent restarted")
    except Exception as exc:
        result["status"] = "restart_failed"
        result["error"] = str(exc)
        _log(f"  vps_agent restart failed: {exc}")
    return result


def _verify_tasks() -> dict:
    """Check each critical schtask exists; re-register if missing."""
    results: dict = {}
    for name, create_cmd in TASK_DEFS.items():
        try:
            r = subprocess.run(
                ["schtasks", "/Query", "/TN", name],
                capture_output=True, encoding="cp932", errors="replace", timeout=10,
            )
            if r.returncode == 0:
                results[name] = "ok"
            else:
                _log(f"Task missing: {name} — re-registering")
                r2 = subprocess.run(
                    create_cmd, capture_output=True,
                    encoding="cp932", errors="replace", timeout=15,
                )
                if r2.returncode == 0:
                    results[name] = "re-registered"
                    _log(f"  {name}: re-registered OK")
                else:
                    results[name] = f"failed(rc={r2.returncode})"
                    _log(f"  {name}: re-register FAILED: {(r2.stderr or '')[:100]}")
        except Exception as exc:
            results[name] = f"error:{exc}"
            _log(f"  {name}: error {exc}")
    return results


def _should_push(action_taken: bool) -> bool:
    if action_taken:
        return True
    try:
        if LAST_PUSH_FILE.exists():
            last = datetime.fromisoformat(LAST_PUSH_FILE.read_text(encoding="utf-8").strip())
            elapsed = (datetime.now(JST) - last).total_seconds() / 60
            return elapsed >= PUSH_INTERVAL_MIN
    except Exception:
        pass
    return True  # first run


def _push_status(status: dict, action_taken: bool) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(
        json.dumps(status, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    if not _should_push(action_taken):
        return
    _log("Pushing watchdog status to GitHub")
    try:
        subprocess.run(["git", "pull", "--quiet"],
                       cwd=str(REPO_ROOT), capture_output=True, timeout=30)
        subprocess.run(["git", "add", "-f", "cits/data/watchdog_status.json"],
                       cwd=str(REPO_ROOT), capture_output=True, timeout=10)
        subprocess.run(
            ["git", "commit", "-m",
             f"watchdog: {datetime.now(JST).strftime('%Y-%m-%dT%H:%M JST')}", "--quiet"],
            cwd=str(REPO_ROOT), capture_output=True, timeout=10,
        )
        r = subprocess.run(
            ["git", "push", "origin", BRANCH, "--quiet"],
            cwd=str(REPO_ROOT), capture_output=True, timeout=30,
        )
        if r.returncode == 0:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            LAST_PUSH_FILE.write_text(
                datetime.now(JST).isoformat(), encoding="utf-8",
            )
            _log("Push OK")
        else:
            _log(f"Push failed rc={r.returncode}")
    except Exception as exc:
        _log(f"Push error: {exc}")


def main() -> None:
    # Load .env
    try:
        from dotenv import load_dotenv  # noqa: PLC0415
        env_path = REPO_ROOT / "cits" / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=True)
    except ImportError:
        pass

    now_jst = datetime.now(JST)
    _log(f"=== run {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')} ===")

    actions: list[str] = []

    kabu = _ensure_kabu_running()
    if kabu.get("action"):
        actions.append(f"kabu:{kabu['action']}")

    agent = _check_vps_agent()
    if agent.get("action"):
        actions.append(f"agent:{agent['action']}")

    tasks = _verify_tasks()
    reregistered = [k for k, v in tasks.items() if v == "re-registered"]
    if reregistered:
        actions.append(f"tasks_reregistered:{','.join(reregistered)}")

    if actions:
        _log(f"Actions: {actions}")

    status = {
        "timestamp": now_jst.isoformat(),
        "market_hours": _is_market_hours(),
        "kabu": kabu,
        "vps_agent": agent,
        "tasks": tasks,
        "actions": actions,
    }
    _push_status(status, action_taken=bool(actions))
    _log("=== done ===")


if __name__ == "__main__":
    main()
