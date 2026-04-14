"""vps_ctl.py -- ローカルClaude CodeからVPSを操作するCLIヘルパー

使い方:
  python -m cits.scripts.vps_ctl status          # VPS最新状態表示
  python -m cits.scripts.vps_ctl send '{"id":"check_0001","type":"shell","command":"echo hi","timeout":10}'
  python -m cits.scripts.vps_ctl watch            # 新しい結果が来るまでポーリング
  python -m cits.scripts.vps_ctl login            # kabuStation再ログインコマンド送信
  python -m cits.scripts.vps_ctl scan             # live_trader morningスキャン送信
  python -m cits.scripts.vps_ctl positions        # 現在のポジション確認
  python -m cits.scripts.vps_ctl api              # kabuStation API疎通確認

git設定:
  VPS通信はGitHub経由（commands.json書込み→push、vps_status.json読込み）
  ローカルでgit pushが通る状態（remote urlにtokenが含まれているか、gh authでログイン済み）であれば動作する。
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env = Path(__file__).resolve().parent.parent / ".env"
    if _env.exists():
        load_dotenv(_env, override=True)
except ImportError:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMMANDS_FILE = REPO_ROOT / "cits" / "data" / "commands.json"
STATUS_FILE = REPO_ROOT / "cits" / "data" / "vps_status.json"
BRANCH = "claude/continue-kabusute-DmFKB"
OWNER = "ai-money-lab"
REPO = "mauloa.surf-gmail.com"
GITHUB_API_BASE = "https://api.github.com"


# ──────────────────────────────────────────────
# GitHub API (git fallback)
# ──────────────────────────────────────────────

def _token() -> str:
    # 1. 環境変数
    tok = os.environ.get("GITHUB_TOKEN", "")
    if tok:
        return tok
    # 2. git remote URL内のトークン
    try:
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=5,
        )
        url = r.stdout.strip()
        if "@github.com" in url and "//" in url:
            return url.split("//", 1)[1].split("@", 1)[0]
    except Exception:
        pass
    # 3. gh CLI
    try:
        r = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return ""


def _api_headers() -> dict:
    tok = _token()
    return {"Authorization": f"token {tok}", "Accept": "application/vnd.github.v3+json"}


def _api_read(path: str) -> str | None:
    try:
        import requests
        url = f"{GITHUB_API_BASE}/repos/{OWNER}/{REPO}/contents/{path}?ref={BRANCH}"
        r = requests.get(url, headers=_api_headers(), timeout=15)
        if r.status_code == 200:
            return base64.b64decode(r.json()["content"].replace("\n", "")).decode("utf-8")
    except Exception as e:
        print(f"[API read error] {e}", file=sys.stderr)
    return None


def _api_write(path: str, content: str, message: str) -> bool:
    try:
        import requests
        headers = _api_headers()
        url = f"{GITHUB_API_BASE}/repos/{OWNER}/{REPO}/contents/{path}"
        r_get = requests.get(url + f"?ref={BRANCH}", headers=headers, timeout=15)
        sha = r_get.json().get("sha") if r_get.status_code == 200 else None
        payload: dict = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": BRANCH,
        }
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers=headers, json=payload, timeout=15)
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[API write error] {e}", file=sys.stderr)
    return False


# ──────────────────────────────────────────────
# Git push / pull
# ──────────────────────────────────────────────

def _git_ok() -> bool:
    try:
        return subprocess.run(["git", "--version"], capture_output=True, timeout=5).returncode == 0
    except Exception:
        return False


def _git_pull() -> bool:
    try:
        r = subprocess.run(
            ["git", "pull", "--rebase", "origin", BRANCH, "--quiet"],
            cwd=str(REPO_ROOT), capture_output=True, timeout=30,
        )
        return r.returncode == 0
    except Exception:
        return False


def _git_push(commit_msg: str) -> bool:
    try:
        subprocess.run(["git", "add", "-f", "cits/data/commands.json"],
                       cwd=str(REPO_ROOT), capture_output=True, timeout=10)
        subprocess.run(["git", "commit", "-m", commit_msg, "--quiet"],
                       cwd=str(REPO_ROOT), capture_output=True, timeout=10)
        r = subprocess.run(["git", "push", "origin", BRANCH, "--quiet"],
                           cwd=str(REPO_ROOT), capture_output=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


# ──────────────────────────────────────────────
# commands.json 操作
# ──────────────────────────────────────────────

def _load_commands() -> list[dict]:
    # GitHub APIから最新を取得
    raw = _api_read("cits/data/commands.json")
    if raw:
        COMMANDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        COMMANDS_FILE.write_text(raw, encoding="utf-8")
        return json.loads(raw)
    # ローカルファイルにフォールバック
    if COMMANDS_FILE.exists():
        return json.loads(COMMANDS_FILE.read_text(encoding="utf-8"))
    return []


def _save_and_push(commands: list[dict], commit_msg: str) -> bool:
    content = json.dumps(commands, ensure_ascii=False, indent=2)
    COMMANDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    COMMANDS_FILE.write_text(content, encoding="utf-8")

    # git push を試みる
    if _git_ok():
        _git_pull()
        if _git_push(commit_msg):
            print(f"[git push OK] {commit_msg}")
            return True
        print("[git push failed, trying GitHub API...]", file=sys.stderr)

    # GitHub API fallback
    ok = _api_write("cits/data/commands.json", content, commit_msg)
    if ok:
        print(f"[API write OK] {commit_msg}")
    return ok


def _make_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%m%d_%H%M%S')}"


# ──────────────────────────────────────────────
# コマンド
# ──────────────────────────────────────────────

def cmd_status() -> None:
    """VPS最新状態を表示"""
    raw = _api_read("cits/data/vps_status.json")
    if not raw:
        if STATUS_FILE.exists():
            raw = STATUS_FILE.read_text(encoding="utf-8")
        else:
            print("vps_status.json not found")
            return
    data = json.loads(raw)
    ts = data.get("timestamp", "?")
    mode = data.get("git_mode", "?")
    results = data.get("results", [])
    print(f"\n=== VPS Status ({ts} / {mode}) ===")
    if not results:
        print("  results: (empty)")
    for r in results:
        status = r.get("status", "?")
        icon = "✅" if status == "ok" else "❌"
        print(f"  {icon} [{r.get('id')}] {status}")
        if r.get("stdout"):
            print(f"     stdout: {r['stdout'][:300]}")
        if r.get("stderr"):
            print(f"     stderr: {r['stderr'][:200]}")
        if r.get("error"):
            print(f"     error:  {r['error'][:200]}")


def cmd_send(cmd_json: str) -> None:
    """コマンドJSON文字列をcommands.jsonに追加してpush"""
    cmd = json.loads(cmd_json)
    if "id" not in cmd:
        cmd["id"] = _make_id("cmd")
    commands = _load_commands()
    existing_ids = {c.get("id") for c in commands}
    if cmd["id"] in existing_ids:
        print(f"ID {cmd['id']} already exists. Use a unique ID.")
        return
    commands.append(cmd)
    _save_and_push(commands, f"vps_ctl: send {cmd['id']}")
    print(f"Sent: {cmd['id']}")


def cmd_watch(timeout_sec: int = 120) -> None:
    """新しい結果が届くまでvps_status.jsonをポーリング"""
    print(f"Watching for new results (timeout={timeout_sec}s)...")
    prev_ts = None
    start = time.time()
    while time.time() - start < timeout_sec:
        raw = _api_read("cits/data/vps_status.json")
        if raw:
            data = json.loads(raw)
            ts = data.get("timestamp")
            if ts != prev_ts and prev_ts is not None:
                print(f"\n=== New result at {ts} ===")
                for r in data.get("results", []):
                    status = r.get("status", "?")
                    icon = "✅" if status == "ok" else "❌"
                    print(f"  {icon} [{r.get('id')}] {status}")
                    if r.get("stdout"):
                        print(f"     stdout: {r['stdout'][:500]}")
                    if r.get("stderr"):
                        print(f"     stderr: {r['stderr'][:200]}")
                return
            prev_ts = ts
        time.sleep(10)
        print(".", end="", flush=True)
    print("\nTimeout reached.")


def cmd_login() -> None:
    """kabuStation再ログインコマンドを送信"""
    now = datetime.now().strftime("%m%d_%H%M")
    kill_id = _make_id("kill_kabu")
    login_id = _make_id("kabu_login")
    commands = _load_commands()
    commands.append({
        "id": kill_id,
        "type": "shell",
        "command": "taskkill /f /im KabuS.exe 2>nul & echo killed",
        "timeout": 15,
    })
    commands.append({
        "id": login_id,
        "type": "module",
        "module": "cits.scripts.kabu_auto_login_vps",
        "timeout": 480,
    })
    _save_and_push(commands, f"vps_ctl: kabu login {now}")
    print(f"Login commands sent: {kill_id}, {login_id}")


def cmd_scan() -> None:
    """live_trader morning スキャン+発注コマンドを送信"""
    now = datetime.now().strftime("%m%d_%H%M")
    cmd_id = _make_id("live_trader_morning")
    commands = _load_commands()
    commands.append({
        "id": cmd_id,
        "type": "module",
        "module": "cits.scripts.live_trader",
        "args": ["--mode", "morning"],
        "timeout": 900,
    })
    _save_and_push(commands, f"vps_ctl: morning scan {now}")
    print(f"Scan command sent: {cmd_id}")


def cmd_positions() -> None:
    """VPS上のpositions.jsonを取得して表示"""
    raw = _api_read("cits/data/positions.json")
    if raw:
        data = json.loads(raw)
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        # VPSコマンド経由で取得
        cmd = {
            "id": _make_id("get_positions"),
            "type": "shell",
            "command": "type C:\\cits\\repo\\cits\\data\\positions.json 2>nul || echo {}",
            "timeout": 10,
        }
        cmd_send(json.dumps(cmd))
        print("Command sent. Run 'python -m cits.scripts.vps_ctl watch' to see result.")


def cmd_api_check() -> None:
    """kabuStation API疎通確認コマンドを送信"""
    cmd = {
        "id": _make_id("api_check"),
        "type": "shell",
        "command": (
            'curl -s -X POST http://localhost:18080/kabusapi/token '
            '-H "Content-Type: application/json" '
            '-d "{\\"APIPassword\\":\\"hiroki0380\\"}" 2>&1'
        ),
        "timeout": 15,
    }
    cmd_send(json.dumps(cmd))
    print("API check command sent. Run 'python -m cits.scripts.vps_ctl watch' to see result.")


# ──────────────────────────────────────────────
# エントリーポイント
# ──────────────────────────────────────────────

USAGE = """
python -m cits.scripts.vps_ctl <command> [args]

Commands:
  status              VPS最新状態を表示
  send '<json>'       コマンドJSONを送信
  watch [seconds]     新しい結果が届くまでポーリング（デフォルト120秒）
  login               kabuStation再ログイン
  scan                live_trader morningスキャン+発注
  positions           現在ポジション確認
  api                 kabuStation API疎通確認

Examples:
  python -m cits.scripts.vps_ctl status
  python -m cits.scripts.vps_ctl login
  python -m cits.scripts.vps_ctl scan
  python -m cits.scripts.vps_ctl send '{"id":"test_001","type":"shell","command":"echo hello","timeout":10}'
  python -m cits.scripts.vps_ctl watch 60
"""


def main():
    args = sys.argv[1:]
    if not args:
        print(USAGE)
        return

    subcmd = args[0]
    if subcmd == "status":
        cmd_status()
    elif subcmd == "send":
        if len(args) < 2:
            print("Usage: vps_ctl send '<json>'")
            sys.exit(1)
        cmd_send(args[1])
    elif subcmd == "watch":
        timeout = int(args[1]) if len(args) > 1 else 120
        cmd_watch(timeout)
    elif subcmd == "login":
        cmd_login()
    elif subcmd == "scan":
        cmd_scan()
    elif subcmd == "positions":
        cmd_positions()
    elif subcmd == "api":
        cmd_api_check()
    else:
        print(f"Unknown command: {subcmd}")
        print(USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
