"""CITS Watchdog -- VPS Self-Healing Monitor

Runs every 5 minutes via CITS_Watchdog scheduled task.
Self-contained: no imports from cits.* modules.

Actions:
1. Git health check -> repair via winget if broken
2. kabuStation API health check (market hours 08:00-16:30 JST)
   -> restart via CITS_KabuStart_IT if down
   -> run full kabu_auto_login_vps if restart fails
3. vps_agent process check -> restart if dead
4. Critical schtask verification -> re-register any missing tasks
5. Push heartbeat to GitHub (via git OR REST API fallback)
"""
from __future__ import annotations

import base64
import configparser
import json
import os
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ===== Config =====
REPO_ROOT = Path("C:/cits/repo")
LOG_DIR = Path("C:/cits/logs")
LOG_FILE = LOG_DIR / "watchdog.log"
LAST_PUSH_FILE = LOG_DIR / ".watchdog_last_push"
STATUS_FILE = REPO_ROOT / "cits" / "data" / "watchdog_status.json"
TOKEN_CACHE_FILE = Path("C:/cits/.github_token")
BRANCH = "claude/continue-kabusute-DmFKB"
OWNER = "ai-money-lab"
REPO_NAME = "mauloa.surf-gmail.com"
WATCHDOG_STATUS_API_PATH = "cits/data/watchdog_status.json"
GITHUB_API_BASE = "https://api.github.com"

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
    # 毎朝06:00にgitを自動修復（VC++ランタイム破損などを事前に修復）
    "CITS_GitRepair": [
        "schtasks", "/Create", "/TN", "CITS_GitRepair",
        "/TR", r"C:\cits\repo\cits\run_gitrepair.bat",
        "/SC", "DAILY", "/ST", "06:00",
        "/D", "MON,TUE,WED,THU,FRI", "/RL", "HIGHEST", "/F",
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


# ─────────────────────────────────────────────
# Git health check and repair
# ─────────────────────────────────────────────

def _check_git_health() -> dict:
    """Test git.exe. Returns dict with ok:bool and details."""
    result: dict = {}
    try:
        r = subprocess.run(
            ["git", "--version"],
            capture_output=True, text=True, timeout=5,
            encoding="cp932", errors="replace",
        )
        if r.returncode == 0:
            result["ok"] = True
            result["version"] = r.stdout.strip()
        else:
            result["ok"] = False
            result["error"] = f"rc={r.returncode} {r.stderr[:100]}"
    except FileNotFoundError:
        result["ok"] = False
        result["error"] = "git.exe not found"
    except subprocess.TimeoutExpired:
        result["ok"] = False
        result["error"] = "git.exe timeout (0xc0000142 or hung)"
    except Exception as exc:
        result["ok"] = False
        result["error"] = str(exc)
    return result


def _repair_git() -> dict:
    """
    Attempt to repair git.exe via winget or PowerShell installer download.
    Returns dict with method and success bool.
    """
    result: dict = {"attempted": True}
    _log("Git repair: trying winget first...")

    # Method 1: winget (preferred, idempotent)
    try:
        r = subprocess.run(
            ["winget", "install", "Git.Git",
             "--silent", "--accept-package-agreements",
             "--accept-source-agreements"],
            capture_output=True, text=True, timeout=300,
            encoding="cp932", errors="replace",
        )
        if r.returncode == 0:
            result["method"] = "winget"
            result["success"] = True
            _log("Git repair via winget: OK")
            return result
        _log(f"winget failed rc={r.returncode}: {r.stderr[:100]}")
    except Exception as exc:
        _log(f"winget not available: {exc}")

    # Method 2: PowerShell + direct download
    _log("Git repair: trying PowerShell download...")
    installer_path = r"C:\cits\git_installer.exe"
    git_url = (
        "https://github.com/git-for-windows/git/releases/download/"
        "v2.45.0.windows.1/Git-2.45.0-64-bit.exe"
    )
    ps_download = (
        f"Invoke-WebRequest -Uri '{git_url}' -OutFile '{installer_path}' "
        "-UseBasicParsing"
    )
    try:
        r2 = subprocess.run(
            ["powershell", "-NonInteractive", "-Command", ps_download],
            capture_output=True, text=True, timeout=180,
            encoding="cp932", errors="replace",
        )
        if r2.returncode != 0:
            result["method"] = "powershell_download"
            result["success"] = False
            result["error"] = r2.stderr[:200]
            _log(f"PowerShell download failed: {r2.stderr[:100]}")
            return result
        # Silent install
        r3 = subprocess.run(
            [installer_path, "/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES"],
            capture_output=True, timeout=300,
        )
        result["method"] = "powershell_download"
        result["success"] = r3.returncode == 0
        _log(f"Git installer rc={r3.returncode}")
    except Exception as exc:
        result["method"] = "powershell_download"
        result["success"] = False
        result["error"] = str(exc)
        _log(f"PowerShell install error: {exc}")

    return result


# ─────────────────────────────────────────────
# GitHub REST API (git-free status push)
# ─────────────────────────────────────────────

def _get_github_token() -> str:
    """Get PAT without calling git.exe."""
    if TOKEN_CACHE_FILE.exists():
        tok = TOKEN_CACHE_FILE.read_text(encoding="utf-8").strip()
        if tok:
            return tok
    git_cfg = REPO_ROOT / ".git" / "config"
    if git_cfg.exists():
        try:
            cfg = configparser.ConfigParser(strict=False)
            cfg.read(str(git_cfg), encoding="utf-8")
            url = cfg.get('remote "origin"', "url", fallback="")
            if "@github.com" in url and "//" in url:
                tok = url.split("//", 1)[1].split("@", 1)[0]
                if tok:
                    TOKEN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                    TOKEN_CACHE_FILE.write_text(tok, encoding="utf-8")
                    return tok
        except Exception:
            pass
    return os.environ.get("GITHUB_TOKEN", "")


def _github_api_write(api_path: str, content: str, message: str) -> bool:
    """Write file to GitHub via REST API. Returns True on success."""
    try:
        import requests  # noqa: PLC0415
        tok = _get_github_token()
        headers = {
            "Authorization": f"token {tok}",
            "Accept": "application/vnd.github.v3+json",
        }
        url = f"{GITHUB_API_BASE}/repos/{OWNER}/{REPO_NAME}/contents/{api_path}"
        r_get = requests.get(url + f"?ref={BRANCH}", headers=headers, timeout=15)
        sha = r_get.json().get("sha") if r_get.status_code == 200 else None
        payload: dict = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode(),
            "branch": BRANCH,
        }
        if sha:
            payload["sha"] = sha
        r_put = requests.put(url, headers=headers, json=payload, timeout=15)
        success = r_put.status_code in (200, 201)
        if not success:
            _log(f"GitHub API write {api_path} failed: {r_put.status_code} {r_put.text[:100]}")
        return success
    except Exception as exc:
        _log(f"GitHub API write error: {exc}")
        return False


# ─────────────────────────────────────────────
# Core checks
# ─────────────────────────────────────────────

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
    """
    kabuStation ログイン保証。
    毎回 kabu_auto_login_vps を呼ぶ。
    login_flow() が先にAPIチェックを行い、ログイン済みなら即時リターンするため
    既にログイン済みの場合のオーバーヘッドは数秒のみ。
    """
    result: dict = {"checked": True, "market_hours": _is_market_hours()}
    if not _is_market_hours():
        result["skipped"] = "outside_market_hours"
        return result

    if _check_kabu_api():
        result["api"] = "ok"
        _log("kabuStation API: already logged in")
        return result

    _log("kabuStation API down — running kabu_auto_login_vps (毎回ログイン)")
    result["api"] = "down"

    # 直接 kabu_auto_login_vps を実行（kill→start→VNC→2FA を全て処理）
    proc = subprocess.run(
        [r"C:\cits\venv\Scripts\python.exe", "-m",
         "cits.scripts.kabu_auto_login_vps"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        encoding="cp932", errors="replace", timeout=420,
    )
    result["auto_login_rc"] = proc.returncode
    result["auto_login_tail"] = (proc.stdout or "")[-600:]
    result["action"] = "auto_login"
    if proc.returncode == 0:
        result["restart"] = "ok"
        _log("  kabuStation login: SUCCESS")
    else:
        result["restart"] = "failed"
        _log(f"  kabuStation login: FAILED rc={proc.returncode}")
        _log(f"  tail: {result['auto_login_tail'][-200:]}")
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


# ─────────────────────────────────────────────
# Status push (git first, then API fallback)
# ─────────────────────────────────────────────

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
    content = json.dumps(status, ensure_ascii=False, indent=2, default=str)
    STATUS_FILE.write_text(content, encoding="utf-8")

    if not _should_push(action_taken):
        return

    ts = datetime.now(JST).strftime("%Y%m%dT%H%M JST")
    _log("Pushing watchdog status to GitHub")
    git_pushed = False

    # Try git push first
    try:
        git_ok_result = subprocess.run(
            ["git", "--version"], capture_output=True, timeout=5,
        )
        if git_ok_result.returncode == 0:
            subprocess.run(["git", "pull", "--quiet"],
                           cwd=str(REPO_ROOT), capture_output=True, timeout=30)
            subprocess.run(["git", "add", "-f", "cits/data/watchdog_status.json"],
                           cwd=str(REPO_ROOT), capture_output=True, timeout=10)
            subprocess.run(
                ["git", "commit", "-m", f"watchdog: {ts}", "--quiet"],
                cwd=str(REPO_ROOT), capture_output=True, timeout=10,
            )
            r = subprocess.run(
                ["git", "push", "origin", BRANCH, "--quiet"],
                cwd=str(REPO_ROOT), capture_output=True, timeout=30,
            )
            git_pushed = r.returncode == 0
            if git_pushed:
                LOG_DIR.mkdir(parents=True, exist_ok=True)
                LAST_PUSH_FILE.write_text(datetime.now(JST).isoformat(), encoding="utf-8")
                _log("Push OK (git)")
            else:
                _log(f"git push failed rc={r.returncode}")
    except Exception as exc:
        _log(f"git push error: {exc}")

    # GitHub REST API fallback
    if not git_pushed:
        _log("Falling back to GitHub REST API push")
        ok = _github_api_write(
            WATCHDOG_STATUS_API_PATH, content,
            f"watchdog: {ts} [api-mode]",
        )
        if ok:
            LAST_PUSH_FILE.write_text(datetime.now(JST).isoformat(), encoding="utf-8")
            _log("Push OK (api-mode)")
        else:
            _log("Push FAILED (both git and api)")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

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

    # ── 1. Git health check (最優先: git破損は全障害の根本原因)
    git_health = _check_git_health()
    git_repair_result: dict = {}
    if not git_health.get("ok"):
        _log(f"git.exe BROKEN: {git_health.get('error')} — attempting repair")
        git_repair_result = _repair_git()
        if git_repair_result.get("success"):
            actions.append("git_repaired")
            _log(f"git repaired via {git_repair_result.get('method')}")
            # Re-check after repair
            git_health = _check_git_health()
        else:
            actions.append("git_repair_failed")
            _log("git repair FAILED — continuing with API-mode fallback")
    else:
        _log(f"git health: OK ({git_health.get('version', '')})")
        # Cache token while git works
        _get_github_token()

    # ── 2. kabuStation API
    kabu = _ensure_kabu_running()
    if kabu.get("action"):
        actions.append(f"kabu:{kabu['action']}")

    # ── 3. vps_agent process
    agent = _check_vps_agent()
    if agent.get("action"):
        actions.append(f"agent:{agent['action']}")

    # ── 4. Task verification
    tasks = _verify_tasks()
    reregistered = [k for k, v in tasks.items() if v == "re-registered"]
    if reregistered:
        actions.append(f"tasks_reregistered:{','.join(reregistered)}")

    if actions:
        _log(f"Actions taken: {actions}")

    status = {
        "timestamp": now_jst.isoformat(),
        "market_hours": _is_market_hours(),
        "git_health": git_health,
        "git_repair": git_repair_result or None,
        "kabu": kabu,
        "vps_agent": agent,
        "tasks": tasks,
        "actions": actions,
    }
    _push_status(status, action_taken=bool(actions))
    _log("=== done ===")


if __name__ == "__main__":
    main()
