"""Auto-diagnose kabuStation API + push result to GitHub.

v2: Shows what password is being sent + tries multiple candidates.
"""
from __future__ import annotations

import json
import os
import socket
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

import requests  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULT_FILE = REPO_ROOT / "cits" / "logs" / "kabu_diagnosis.json"
ENV_FILE = REPO_ROOT / "cits" / ".env"
BRANCH = "claude/continue-kabusute-DmFKB"


def check_port(host="localhost", port=18080, timeout=3.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"status": "open", "host": host, "port": port}
    except Exception as e:
        return {"status": "closed", "error": str(e)}


def mask_password(pw):
    if not pw:
        return "<empty>"
    if len(pw) <= 4:
        return "*" * len(pw)
    return f"{pw[:2]}{'*' * (len(pw) - 4)}{pw[-2:]}"


def test_token(password):
    url = "http://localhost:18080/kabusapi/token"
    try:
        resp = requests.post(url, json={"APIPassword": password}, timeout=10)
        try:
            body = resp.json()
        except Exception:
            body = {"text": resp.text[:300]}
        return {
            "status_code": resp.status_code,
            "body": body,
            "ok": resp.status_code == 200,
        }
    except Exception as e:
        return {"error": str(e), "ok": False}


def read_env_file():
    result = {"exists": ENV_FILE.exists(), "keys": {}}
    if not ENV_FILE.exists():
        return result
    try:
        content = ENV_FILE.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = ENV_FILE.read_text(encoding="cp932", errors="replace")
    result["size_bytes"] = len(content)
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("KABU_") and "=" in line:
            k, v = line.split("=", 1)
            result["keys"][k] = {
                "length": len(v),
                "masked": mask_password(v),
                "has_spaces": " " in v,
                "has_quotes": '"' in v or "'" in v,
            }
    return result


def list_kabu_processes():
    procs = []
    try:
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/V"],
            capture_output=True, text=True, encoding="cp932",
            errors="replace", timeout=10,
        )
        for line in out.stdout.splitlines():
            if "kabu" in line.lower() or "KabuS" in line:
                procs.append({"line": line.strip()[:200]})
    except Exception as e:
        return [{"error": str(e)}]
    return procs


def check_netstat():
    try:
        out = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, encoding="cp932",
            errors="replace", timeout=10,
        )
        return [line.strip() for line in out.stdout.splitlines() if ":18080" in line]
    except Exception as e:
        return [f"error: {e}"]


def git_push_result():
    try:
        subprocess.run(["git", "pull", "origin", BRANCH, "--quiet"],
                       cwd=str(REPO_ROOT), capture_output=True, timeout=30)
        subprocess.run(["git", "add", "-f", "cits/logs/kabu_diagnosis.json"],
                       cwd=str(REPO_ROOT), capture_output=True, timeout=10)
        subprocess.run(["git", "commit", "-m",
                        f"diag: kabuStation v2 {datetime.now().isoformat()}", "--quiet"],
                       cwd=str(REPO_ROOT), capture_output=True, timeout=10)
        r = subprocess.run(["git", "push", "origin", BRANCH, "--quiet"],
                           cwd=str(REPO_ROOT), capture_output=True, timeout=30)
        return r.returncode == 0
    except Exception as e:
        print(f"git push failed: {e}")
        return False


def main():
    print("=" * 60)
    print("kabuStation API Auto-Diagnosis v2")
    print("=" * 60)

    env_pw = os.environ.get("KABU_API_PASSWORD", "")

    candidates = [
        ("env_KABU_API_PASSWORD", env_pw),
        ("hiroki0380", "hiroki0380"),
        ("hiroki0380HM", "hiroki0380HM"),
        ("3Hximek2cb", "3Hximek2cb"),
    ]
    seen = set()
    unique_candidates = []
    for name, pw in candidates:
        if pw and pw not in seen:
            seen.add(pw)
            unique_candidates.append((name, pw))

    token_tests = []
    found_password = None
    for name, pw in unique_candidates:
        print(f"\nTrying: {name} (len={len(pw)}, masked={mask_password(pw)})")
        r = test_token(pw)
        r["source"] = name
        r["masked_pw"] = mask_password(pw)
        r["pw_length"] = len(pw)
        token_tests.append(r)
        print(f"  -> {r.get('status_code', 'ERR')}: {r.get('body', r.get('error'))}")
        if r.get("ok"):
            found_password = name
            break

    result = {
        "timestamp": datetime.now().isoformat(),
        "port_check": check_port(),
        "env_file": read_env_file(),
        "token_tests": token_tests,
        "found_working_password": found_password,
        "processes": list_kabu_processes(),
        "netstat_18080": check_netstat(),
    }

    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nSaved to: {RESULT_FILE}")

    if git_push_result():
        print("Pushed to GitHub")
    else:
        print("Push failed")

    print("\n" + "=" * 60)
    print("DIAGNOSIS")
    print("=" * 60)
    if found_password:
        print(f"OK: Working password = {found_password}")
    else:
        print("FAIL: No candidate password worked")
        print("   -> Check kabuStation > Tools > Settings > API")
        print("   -> Or reset APIパスワード(本番用) in kabuStation GUI")
        print(f"\n   .env file: {result['env_file']}")

    return 0 if found_password else 1


if __name__ == "__main__":
    sys.exit(main())
