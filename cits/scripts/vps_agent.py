"""VPS Agent -- polls GitHub for command triggers and executes them.

Runs as a persistent background process on VPS. Every 60 seconds:
1. Fetch cits/data/commands.json from GitHub (git pull OR GitHub REST API)
2. Execute new commands
3. Push results back to vps_status.json (git push OR GitHub REST API)

Git-free fallback:
  If git.exe is unavailable (e.g. 0xc0000142 VC++ error), all communication
  falls back to the GitHub REST API via Python requests. The token is read
  from the git remote URL in .git/config (no git.exe call needed).
"""
from __future__ import annotations

import base64
import configparser
import json
import logging
import os
import subprocess
import sys
import time
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
COMMANDS_FILE = REPO_ROOT / "cits" / "data" / "commands.json"
RESULTS_FILE = REPO_ROOT / "cits" / "data" / "vps_status.json"
PROCESSED_FILE = REPO_ROOT / "cits" / "logs" / ".processed_commands"
LOG_FILE = REPO_ROOT / "cits" / "logs" / "vps_agent.log"
TOKEN_CACHE_FILE = Path("C:/cits/.github_token")
PID_FILE = Path("C:/cits/vps_agent.pid")
POLL_INTERVAL = 60
BRANCH = "claude/continue-kabusute-DmFKB"
OWNER = "ai-money-lab"
REPO = "mauloa.surf-gmail.com"
COMMANDS_API_PATH = "cits/data/commands.json"
STATUS_API_PATH = "cits/data/vps_status.json"
GITHUB_API_BASE = "https://api.github.com"

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("vps_agent")


# ─────────────────────────────────────────────
# GitHub REST API fallback (git-free)
# ─────────────────────────────────────────────

def _get_github_token() -> str:
    """
    Get GitHub PAT without calling git.exe.
    Priority:
      1. Cached token file
      2. Parse directly from .git/config remote URL
      3. GITHUB_TOKEN env var
    """
    # 1. Cache file
    if TOKEN_CACHE_FILE.exists():
        tok = TOKEN_CACHE_FILE.read_text(encoding="utf-8").strip()
        if tok:
            return tok
    # 2. Parse .git/config directly (no git.exe)
    git_cfg = REPO_ROOT / ".git" / "config"
    if git_cfg.exists():
        try:
            cfg = configparser.ConfigParser(strict=False)
            cfg.read(str(git_cfg), encoding="utf-8")
            url = cfg.get('remote "origin"', "url", fallback="")
            # URL format: https://TOKEN@github.com/owner/repo.git
            if "@github.com" in url and "//" in url:
                tok = url.split("//", 1)[1].split("@", 1)[0]
                if tok:
                    # Cache for future use
                    TOKEN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                    TOKEN_CACHE_FILE.write_text(tok, encoding="utf-8")
                    return tok
        except Exception as exc:
            log.warning("git config parse error: %s", exc)
    # 3. Env var
    return os.environ.get("GITHUB_TOKEN", "")


def _github_api_headers() -> dict:
    tok = _get_github_token()
    return {
        "Authorization": f"token {tok}",
        "Accept": "application/vnd.github.v3+json",
    }


def _github_api_read(api_path: str) -> str | None:
    """Read a file from GitHub via REST API. Returns decoded content or None."""
    try:
        import requests as req
        url = f"{GITHUB_API_BASE}/repos/{OWNER}/{REPO}/contents/{api_path}?ref={BRANCH}"
        r = req.get(url, headers=_github_api_headers(), timeout=15)
        if r.status_code == 200:
            return base64.b64decode(r.json()["content"].replace("\n", "")).decode("utf-8")
        log.warning("GitHub API read %s status=%d", api_path, r.status_code)
    except Exception as exc:
        log.error("GitHub API read failed: %s", exc)
    return None


def _github_api_write(api_path: str, content: str, message: str) -> bool:
    """Create or update a file on GitHub via REST API. Returns True on success."""
    try:
        import requests as req
        headers = _github_api_headers()
        url = f"{GITHUB_API_BASE}/repos/{OWNER}/{REPO}/contents/{api_path}"
        # Get current SHA (needed for update; omit for create)
        r_get = req.get(url + f"?ref={BRANCH}", headers=headers, timeout=15)
        sha = r_get.json().get("sha") if r_get.status_code == 200 else None
        payload: dict = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode(),
            "branch": BRANCH,
        }
        if sha:
            payload["sha"] = sha
        r_put = req.put(url, headers=headers, json=payload, timeout=15)
        if r_put.status_code in (200, 201):
            log.info("GitHub API write OK: %s", api_path)
            return True
        log.error("GitHub API write %s status=%d body=%s",
                  api_path, r_put.status_code, r_put.text[:200])
    except Exception as exc:
        log.error("GitHub API write failed: %s", exc)
    return False


# ─────────────────────────────────────────────
# Git health check
# ─────────────────────────────────────────────

def _git_ok() -> bool:
    """Return True if git.exe is functional."""
    try:
        r = subprocess.run(
            ["git", "--version"],
            capture_output=True, timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


# ─────────────────────────────────────────────
# Pull / Push with fallback
# ─────────────────────────────────────────────

def pull_commands() -> str | None:
    """
    Fetch commands.json content.
    Try git pull first; fall back to GitHub REST API if git fails.
    Returns raw JSON string or None.
    """
    # Try git pull
    if _git_ok():
        try:
            r = subprocess.run(
                ["git", "pull", "origin", BRANCH, "--quiet"],
                cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0 and COMMANDS_FILE.exists():
                return COMMANDS_FILE.read_text(encoding="utf-8-sig")
        except Exception as exc:
            log.warning("git pull failed: %s — falling back to API", exc)
    else:
        log.warning("git.exe unavailable — using GitHub REST API for pull")

    # GitHub REST API fallback
    content = _github_api_read(COMMANDS_API_PATH)
    if content:
        # Also write locally so the rest of the code can read it
        COMMANDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        COMMANDS_FILE.write_text(content, encoding="utf-8")
    return content


def push_results(results: list[dict]) -> None:
    """
    Push vps_status.json.
    Try git push first; fall back to GitHub REST API if git fails.
    """
    status = {
        "timestamp": datetime.now().isoformat(),
        "agent": "vps_agent",
        "git_mode": "git" if _git_ok() else "api",
        "results": results,
    }
    content = json.dumps(status, ensure_ascii=False, indent=2, default=str)
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(content, encoding="utf-8")

    # Try git push
    git_succeeded = False
    if _git_ok():
        try:
            # Pull first so our push is a fast-forward (prevents non-fast-forward rejection
            # when the remote has new commits from code pushes or other agents)
            subprocess.run(
                ["git", "pull", "origin", BRANCH, "--quiet"],
                cwd=str(REPO_ROOT), capture_output=True, timeout=30,
            )
            subprocess.run(["git", "add", "-f", "cits/data/vps_status.json"],
                           cwd=str(REPO_ROOT), capture_output=True, timeout=10)
            subprocess.run(
                ["git", "commit", "-m",
                 f"vps_agent: status {datetime.now().isoformat()}", "--quiet"],
                cwd=str(REPO_ROOT), capture_output=True, timeout=10,
            )
            r = subprocess.run(
                ["git", "push", "origin", BRANCH, "--quiet"],
                cwd=str(REPO_ROOT), capture_output=True, timeout=30,
            )
            git_succeeded = r.returncode == 0
        except Exception as exc:
            log.warning("git push failed: %s — falling back to API", exc)

    if not git_succeeded:
        log.warning("git push unavailable — using GitHub REST API for push")
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        _github_api_write(
            STATUS_API_PATH, content,
            f"vps_agent: status {ts} [api-mode]",
        )


# ─────────────────────────────────────────────
# Command execution
# ─────────────────────────────────────────────

def load_processed_ids() -> set[str]:
    if not PROCESSED_FILE.exists():
        return set()
    return set(PROCESSED_FILE.read_text(encoding="utf-8").strip().split("\n"))


def save_processed_ids(ids: set[str]) -> None:
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_FILE.write_text("\n".join(sorted(ids)), encoding="utf-8")


def execute_command(cmd: dict) -> dict:
    cmd_type = cmd.get("type", "")
    cmd_id = cmd.get("id", "")
    result: dict = {
        "id": cmd_id, "type": cmd_type,
        "status": "unknown", "timestamp": datetime.now().isoformat(),
    }
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["CITS_SCHEDULED_RUN"] = "TASKSCHEDULER"
    if "KABU_ORDER_PASSWORD" not in env:
        log.error("KABU_ORDER_PASSWORD not set — order commands will fail. Set in .env or bat file.")
        # Do NOT hardcode password here. Set via .env or run_*.bat.

    try:
        if cmd_type == "shell":
            proc = subprocess.run(
                cmd["command"], shell=True, capture_output=True,
                text=True, timeout=cmd.get("timeout", 120), cwd=str(REPO_ROOT),
                encoding="cp932", errors="replace", env=env,
            )
            result["status"] = "ok" if proc.returncode == 0 else "error"
            result["returncode"] = proc.returncode
            result["stdout"] = (proc.stdout or "")[-2000:]
            result["stderr"] = (proc.stderr or "")[-1000:]

        elif cmd_type == "python":
            proc = subprocess.run(
                [r"C:\cits\venv\Scripts\python.exe", "-c", cmd["code"]],
                capture_output=True, text=True, timeout=cmd.get("timeout", 120),
                cwd=str(REPO_ROOT), encoding="cp932", errors="replace", env=env,
            )
            result["status"] = "ok" if proc.returncode == 0 else "error"
            result["stdout"] = (proc.stdout or "")[-2000:]
            result["stderr"] = (proc.stderr or "")[-1000:]

        elif cmd_type == "module":
            args = [r"C:\cits\venv\Scripts\python.exe", "-m", cmd["module"]]
            args.extend(cmd.get("args", []))
            proc = subprocess.run(
                args, capture_output=True, text=True,
                timeout=cmd.get("timeout", 300),
                cwd=str(REPO_ROOT), encoding="cp932", errors="replace", env=env,
            )
            result["status"] = "ok" if proc.returncode == 0 else "error"
            result["stdout"] = (proc.stdout or "")[-2000:]
            result["stderr"] = (proc.stderr or "")[-1000:]
        else:
            result["status"] = "unknown_type"
    except subprocess.TimeoutExpired:
        result["status"] = "timeout"
    except Exception as exc:
        result["status"] = "exception"
        result["error"] = str(exc)

    return result


# ─────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────

def _pid_is_alive(pid: str) -> bool:
    """Return True if a pythonw.exe process with the given PID is running.

    Filters by both PID and IMAGENAME to avoid false positives from PID reuse
    (Windows recycles PIDs; an unrelated process could occupy the same PID).
    """
    try:
        r = subprocess.run(
            [
                "tasklist",
                "/fi", f"PID eq {pid}",
                "/fi", "IMAGENAME eq pythonw.exe",
                "/fo", "csv", "/nh",
            ],
            capture_output=True, text=True, timeout=5,
        )
        return pid in r.stdout
    except Exception:
        return False


def _claim_singleton() -> bool:
    """Ensure only one vps_agent instance runs. Returns False if another is alive.

    Uses actual PID liveness check (tasklist) instead of file age, so force-kill
    via taskkill /f does not leave a phantom lock preventing restart.
    """
    import atexit
    try:
        if PID_FILE.exists():
            old_pid = ""
            try:
                old_pid = PID_FILE.read_text(encoding="utf-8").strip()
            except Exception:
                pass
            if old_pid and _pid_is_alive(old_pid):
                log.warning("vps_agent PID %s is running. Exiting.", old_pid)
                return False
            log.info("Stale PID file (PID %s not running). Claiming.", old_pid)
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
        atexit.register(lambda: PID_FILE.unlink(missing_ok=True))
        return True
    except Exception as exc:
        log.warning("Singleton check failed: %s — proceeding anyway", exc)
        return True


def main() -> None:
    if not _claim_singleton():
        sys.exit(0)
    log.info("VPS Agent started (git_ok=%s)", _git_ok())
    # Cache GitHub token while git may still be working (first run)
    _get_github_token()
    processed = load_processed_ids()
    cycle = 0

    while True:
        try:
            raw = pull_commands()
            if raw:
                try:
                    commands = json.loads(raw)
                except Exception as exc:
                    log.error("commands.json parse error: %s", exc)
                    # FIX 1: Immediate API fallback on local parse error
                    log.info("Trying GitHub API fallback due to parse error")
                    raw2 = _github_api_read(COMMANDS_API_PATH)
                    if raw2:
                        COMMANDS_FILE.parent.mkdir(parents=True, exist_ok=True)
                        # Write BOM-free UTF-8
                        COMMANDS_FILE.write_bytes(raw2.encode("utf-8"))
                        try:
                            commands = json.loads(raw2)
                            log.info("API fallback commands.json OK (%d cmds)", len(commands))
                        except Exception as exc2:
                            log.error("API fallback also invalid JSON: %s", exc2)
                            commands = []
                    else:
                        commands = []
            else:
                commands = []

            new_results: list[dict] = []
            for cmd in commands:
                cmd_id = cmd.get("id", "")
                if not cmd_id or cmd_id in processed:
                    continue
                log.info("Executing command %s: %s", cmd_id, cmd.get("type"))
                result = execute_command(cmd)
                new_results.append(result)
                processed.add(cmd_id)
                log.info("Command %s result: %s", cmd_id, result.get("status"))

            cycle += 1
            # Refresh PID file mtime so singleton check sees us as alive
            try:
                PID_FILE.touch()
            except Exception:
                pass
            if new_results:
                # Save processed IDs to disk BEFORE pushing, so a self-kill command
                # (e.g. taskkill via shell command) doesn't cause re-execution on restart.
                save_processed_ids(processed)
                push_results(new_results)
            elif cycle % 10 == 0:
                # FIX 2: Heartbeat push every ~10 minutes so vps_status.json stays current
                log.info("Heartbeat push (cycle=%d)", cycle)
                push_results([])

        except Exception as exc:
            log.error("Main loop error: %s", exc)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
