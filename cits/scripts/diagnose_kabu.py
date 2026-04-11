"""Auto-diagnose kabuStation API + push result to GitHub."""
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
BRANCH = "claude/japanese-stock-trading-agent-kJBwp"


def check_port(host="localhost", port=18080, timeout=3.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"status": "open", "host": host, "port": port}
    except Exception as e:
        return {"status": "closed", "error": str(e)}


def test_token_endpoint(password):
    url = "http://localhost:18080/kabusapi/token"
    payload = {"APIPassword": password}
    result = {"url": url, "password_set": bool(password)}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        result["status_code"] = resp.status_code
        result["headers"] = dict(resp.headers)
        try:
            result["body_json"] = resp.json()
        except Exception:
            result["body_text"] = resp.text[:500]
        result["outcome"] = "ok" if resp.status_code == 200 else "http_error"
    except requests.exceptions.ConnectionError as e:
        result["outcome"] = "connection_error"
        result["error"] = str(e)
    except requests.exceptions.Timeout as e:
        result["outcome"] = "timeout"
        result["error"] = str(e)
    except Exception as e:
        result["outcome"] = "exception"
        result["error_type"] = type(e).__name__
        result["error"] = str(e)
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
        return [line for line in out.stdout.splitlines() if ":18080" in line]
    except Exception as e:
        return [f"error: {e}"]


def git_push_result():
    try:
        subprocess.run(["git", "pull", "origin", BRANCH, "--quiet"],
                       cwd=str(REPO_ROOT), capture_output=True, timeout=30)
        subprocess.run(["git", "add", "-f", "cits/logs/kabu_diagnosis.json"],
                       cwd=str(REPO_ROOT), capture_output=True, timeout=10)
        subprocess.run(["git", "commit", "-m",
                        f"diag: kabuStation {datetime.now().isoformat()}", "--quiet"],
                       cwd=str(REPO_ROOT), capture_output=True, timeout=10)
        r = subprocess.run(["git", "push", "origin", BRANCH, "--quiet"],
                           cwd=str(REPO_ROOT), capture_output=True, timeout=30)
        return r.returncode == 0
    except Exception as e:
        print(f"git push failed: {e}")
        return False


def main():
    print("=" * 60)
    print("kabuStation API Auto-Diagnosis")
    print("=" * 60)

    api_pw = os.environ.get("KABU_API_PASSWORD", "hiroki0380")
    result = {
        "timestamp": datetime.now().isoformat(),
        "port_check": check_port(),
        "token_test": test_token_endpoint(api_pw),
        "processes": list_kabu_processes(),
        "netstat_18080": check_netstat(),
    }

    for k, v in result.items():
        print(f"\n[{k}]")
        if isinstance(v, (dict, list)):
            print(json.dumps(v, ensure_ascii=False, indent=2, default=str))
        else:
            print(v)

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
    tt = result["token_test"]
    if tt.get("outcome") == "ok":
        print("OK: kabuStation API is working")
    elif tt.get("outcome") == "connection_error":
        print("FAIL: Connection error")
        print("   -> Check kabuStation is running")
        print("   -> Check API setting (Tools->Settings->API)")
    elif tt.get("outcome") == "http_error":
        sc = tt.get("status_code")
        print(f"FAIL: HTTP {sc}")
        if sc == 401:
            print("   -> Wrong API password")
        elif sc == 400:
            print("   -> Bad request:")
            print("  ", tt.get("body_json", tt.get("body_text", "")))
    else:
        print(f"FAIL: {tt.get('outcome')}: {tt.get('error', '')}")

    return 0 if result["token_test"].get("outcome") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
