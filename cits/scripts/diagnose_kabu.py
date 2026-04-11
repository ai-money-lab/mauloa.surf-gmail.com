"""Auto-diagnose kabuStation API + push result to GitHub.

All-in-one diagnostic script. Run once on VPS, it:
1. Checks port 18080
2. Tests token endpoint with full response capture
3. Lists kabuStation processes
4. Saves result to cits/logs/kabu_diagnosis.json
5. Auto-commits + pushes to GitHub so this env can see it

Usage (VPS):
    C:\\cits\\venv\\Scripts\\python.exe -m cits.scripts.diagnose_kabu
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
BRANCH = "claude/japanese-stock-trading-agent-kJBwp"


def check_port(host: str = "localhost", port: int = 18080, timeout: float = 3.0) -> dict:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"status": "open", "host": host, "port": port}
    except Exception as e:
        return {"status": "closed", "error": str(e)}


def test_token_endpoint(password: str) -> dict:
    """Test /kabusapi/token with full error capture."""
    url = "http://localhost:18080/kabusapi/token"
    payload = {"APIPassword": password}
    result: dict = {"url": url, "password_set": bool(password)}

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


def list_kabu_processes() -> list[dict]:
    procs = []
    try:
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/V"],
            capture_output=True, text=True, encoding="cp932",
            errors="replace", timeout=10,
        )
        for line in out.stdout.splitlines():
            if "kabu" in line.lower() or "KabuS" in line:
                parts = [p.strip('"') for p in line.split('","')]
                if parts:
                    procs.append({"line": line.strip()[:200]})
    except Exception as e:
        return [{"error": str(e)}]
    return procs


def check_netstat() -> list[str]:
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
    """Push kabu_diagnosis.json to GitHub."""
    try:
        subprocess.run(
            ["git", "pull", "origin", BRANCH, "--quiet"],
            cwd=str(REPO_ROOT), capture_output=True, timeout=30,
        )
        subprocess.run(
            ["git", "add", "-f", "cits/logs/kabu_diagnosis.json"],
            cwd=str(REPO_ROOT), capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "commit", "-m", f"diag: kabuStation {datetime.now().isoformat()}", "--quiet"],
            cwd=str(REPO_ROOT), capture_output=True, timeout=10,
        )
        r = subprocess.run(
            ["git", "push", "origin", BRANCH, "--quiet"],
            cwd=str(REPO_ROOT), capture_output=True, timeout=30,
        )
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
        "tz": "JST (UTC+9)" if datetime.now().astimezone().utcoffset().total_seconds() == 32400 else "local",
        "port_check": check_port(),
        "token_test": test_token_endpoint(api_pw),
        "processes": list_kabu_processes(),
        "netstat_18080": check_netstat(),
    }

    # Pretty print
    for k, v in result.items():
        print(f"\n[{k}]")
        if isinstance(v, (dict, list)):
            print(json.dumps(v, ensure_ascii=False, indent=2, default=str))
        else:
            print(v)

    # Save to file
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nSaved to: {RESULT_FILE}")

    # Push to GitHub
    if git_push_result():
        print("✓ Pushed to GitHub")
    else:
        print("✗ Push failed")

    # Diagnosis
    print("\n" + "=" * 60)
    print("DIAGNOSIS")
    print("=" * 60)
    tt = result["token_test"]
    if tt.get("outcome") == "ok":
        print("✅ kabuStation API is working")
    elif tt.get("outcome") == "connection_error":
        print("❌ Connection error: kabuStation not listening on 18080")
        print("   → Check kabuStation is running")
        print("   → Check API setting: ツール→設定→API設定→「APIを利用する」ON")
    elif tt.get("outcome") == "http_error":
        sc = tt.get("status_code")
        print(f"❌ HTTP {sc}")
        if sc == 401:
            print("   → Wrong APIパスワード. Check settings.")
        elif sc == 400:
            print("   → Bad request. Response body:")
            print("  ", tt.get("body_json", tt.get("body_text", "")))
    else:
        print(f"❌ {tt.get('outcome')}: {tt.get('error', '')}")

    return 0 if result["token_test"].get("outcome") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
