"""VPS Agent -- polls GitHub for command triggers and executes them.

Runs as a persistent background process on VPS. Every 60 seconds:
1. Fetch cits/data/commands.json from GitHub (via git pull)
2. Execute new commands
3. Push results back to vps_status.json
"""
from __future__ import annotations

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
POLL_INTERVAL = 60
BRANCH = "claude/continue-kabusute-DmFKB"

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


def git_pull():
    try:
        r = subprocess.run(
            ["git", "pull", "origin", BRANCH, "--quiet"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=30,
        )
        return r.returncode == 0
    except Exception as e:
        log.error(f"git pull failed: {e}")
        return False


def git_push_results():
    try:
        subprocess.run(["git", "add", "cits/data/vps_status.json"],
                       cwd=str(REPO_ROOT), capture_output=True, timeout=10)
        subprocess.run(
            ["git", "commit", "-m", f"vps_agent: status {datetime.now().isoformat()}", "--quiet"],
            cwd=str(REPO_ROOT), capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "push", "origin", BRANCH, "--quiet"],
            cwd=str(REPO_ROOT), capture_output=True, timeout=30,
        )
    except Exception as e:
        log.error(f"git push failed: {e}")


def load_processed_ids():
    if not PROCESSED_FILE.exists():
        return set()
    return set(PROCESSED_FILE.read_text(encoding="utf-8").strip().split("\n"))


def save_processed_ids(ids):
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_FILE.write_text("\n".join(sorted(ids)), encoding="utf-8")


def execute_command(cmd):
    cmd_type = cmd.get("type", "")
    cmd_id = cmd.get("id", "")
    result = {"id": cmd_id, "type": cmd_type, "status": "unknown",
              "timestamp": datetime.now().isoformat()}
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["CITS_SCHEDULED_RUN"] = "TASKSCHEDULER"
    if "KABU_ORDER_PASSWORD" not in env:
        env["KABU_ORDER_PASSWORD"] = "hiroki0380HM"

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
    except Exception as e:
        result["status"] = "exception"
        result["error"] = str(e)

    return result


def write_status(results):
    status = {
        "timestamp": datetime.now().isoformat(),
        "agent": "vps_agent",
        "results": results,
    }
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(
        json.dumps(status, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def main():
    log.info("VPS Agent started")
    processed = load_processed_ids()

    while True:
        try:
            git_pull()

            if COMMANDS_FILE.exists():
                try:
                    commands = json.loads(COMMANDS_FILE.read_text(encoding="utf-8"))
                except Exception as e:
                    log.error(f"commands.json parse error: {e}")
                    commands = []
            else:
                commands = []

            new_results = []
            for cmd in commands:
                cmd_id = cmd.get("id", "")
                if not cmd_id or cmd_id in processed:
                    continue
                log.info(f"Executing command {cmd_id}: {cmd.get('type')}")
                result = execute_command(cmd)
                new_results.append(result)
                processed.add(cmd_id)
                log.info(f"Command {cmd_id} result: {result.get('status')}")

            if new_results:
                write_status(new_results)
                save_processed_ids(processed)
                git_push_results()

        except Exception as e:
            log.error(f"Main loop error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
