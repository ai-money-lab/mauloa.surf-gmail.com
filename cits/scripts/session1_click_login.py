"""
session1_click_login.py -- runs IN Administrator's interactive session (Session 1).
Uses ctypes mouse_event to click kabuStation login button and handle 2FA.
Writes result to C:\\cits\\session1_login_result.json.
"""
import sys
import os
import ctypes
import time
import subprocess
import json
from datetime import datetime, timedelta

# ─── Setup paths / env ──────────────────────────────────────────────────────
REPO_ROOT = r"C:\cits\repo"
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)

# Load .env for GMAIL_APP_PASSWORD etc.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(REPO_ROOT, "cits", ".env"), override=True)
except Exception:
    pass

RESULT_FILE = r"C:\cits\session1_login_result.json"

# ─── Screen coords (1024×768 VPS) ───────────────────────────────────────────
LOGIN_BTN      = (779, 475)
TWO_FA_INPUT   = (769, 455)
TWO_FA_SUBMIT  = (769, 530)
TASKBAR_KABU   = (449, 750)
KABU_EXE       = r"C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe"
SCREEN_W, SCREEN_H = 1024, 768

# ─── WinAPI constants ────────────────────────────────────────────────────────
MOUSEEVENTF_MOVE      = 0x0001
MOUSEEVENTF_LEFTDOWN  = 0x0002
MOUSEEVENTF_LEFTUP    = 0x0004
MOUSEEVENTF_ABSOLUTE  = 0x8000
KEYEVENTF_KEYUP       = 0x0002
VK_CONTROL = 0x11
VK_V       = 0x56


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def click_at(x: int, y: int) -> None:
    ax = int(x * 65535 / SCREEN_W)
    ay = int(y * 65535 / SCREEN_H)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, ax, ay, 0, 0)
    time.sleep(0.1)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, ax, ay, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, ax, ay, 0, 0)
    _log(f"click_at({x}, {y})")


def paste_text(text: str) -> None:
    """Set clipboard via PowerShell then paste with Ctrl+V."""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", f'Set-Clipboard -Value "{text}"'],
        capture_output=True, timeout=5,
    )
    time.sleep(0.3)
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    _log(f"pasted text (len={len(text)})")


def kabu_running() -> bool:
    r = subprocess.run(
        'tasklist /fi "IMAGENAME eq KabuS.exe" /fo csv /nh',
        shell=True, capture_output=True, text=True,
        timeout=5, encoding="cp932", errors="replace",
    )
    return "KabuS" in (r.stdout or "")


def check_api() -> bool:
    try:
        r = subprocess.run(
            'curl -s -X POST http://localhost:18080/kabusapi/token'
            ' -H "Content-Type: application/json"'
            ' -d "{\\"APIPassword\\":\\"hiroki0380\\"}"',
            shell=True, capture_output=True, text=True,
            timeout=8, encoding="cp932", errors="replace",
        )
        return '"Token"' in (r.stdout or "")
    except Exception:
        return False


def get_2fa() -> str:
    """Import and call get_2fa_from_gmail with a recent not_before."""
    try:
        from cits.scripts.kabu_auto_login_vps import get_2fa_from_gmail
        not_before = datetime.now() - timedelta(minutes=1)
        code = get_2fa_from_gmail(max_wait_sec=120, not_before=not_before)
        return code or ""
    except Exception as e:
        _log(f"get_2fa error: {e}")
        return ""


def main() -> dict:
    result = {"status": "unknown", "ts": datetime.now().isoformat()}

    # Step 1: Ensure kabuStation is running
    if not kabu_running():
        _log("KabuS not running — starting directly...")
        subprocess.Popen([KABU_EXE])
        time.sleep(30)
        if not kabu_running():
            result["status"] = "FAILED: kabuStation did not start"
            return result
        _log("KabuS started")
    else:
        _log("KabuS already running")

    # Step 2: Check if already logged in
    if check_api():
        result["status"] = "ALREADY_LOGGED_IN"
        _log("Already logged in!")
        return result

    # Step 3: Bring kabuStation window to front
    _log("Clicking taskbar to bring kabuStation to front...")
    click_at(*TASKBAR_KABU)
    time.sleep(3)

    # Step 4: Click login button
    _log("Clicking LOGIN_BTN (779, 475)...")
    login_clicked_at = datetime.now()
    click_at(*LOGIN_BTN)
    time.sleep(15)
    result["login_click_at"] = login_clicked_at.isoformat()

    # Step 5: Check if login succeeded without 2FA
    if check_api():
        result["status"] = "LOGIN_SUCCESS_NO_2FA"
        _log("LOGIN SUCCESS (no 2FA)!")
        return result

    # Step 6: Get 2FA code from Gmail
    _log("2FA required. Fetching from Gmail...")
    try:
        from cits.scripts.kabu_auto_login_vps import get_2fa_from_gmail
        code = get_2fa_from_gmail(max_wait_sec=120, not_before=login_clicked_at)
    except Exception as e:
        _log(f"Gmail error: {e}")
        code = ""

    if not code:
        result["status"] = "FAILED: no 2FA code"
        _log("No 2FA code received")
        return result

    _log(f"2FA code: {code}")
    result["code_received"] = True

    # Step 7: Enter 2FA code
    click_at(*TWO_FA_INPUT)
    time.sleep(1)
    paste_text(code)
    time.sleep(1)
    click_at(*TWO_FA_SUBMIT)
    time.sleep(15)

    # Step 8: Final API check
    if check_api():
        result["status"] = "LOGIN_SUCCESS_WITH_2FA"
        _log("LOGIN SUCCESS (with 2FA)!")
    else:
        result["status"] = "FAILED: API not ready after 2FA"
        _log("Login failed after 2FA")

    return result


if __name__ == "__main__":
    try:
        r = main()
    except Exception as exc:
        import traceback
        r = {"status": f"EXCEPTION: {exc}", "tb": traceback.format_exc()}
        _log(f"Exception: {exc}")

    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(r, f, indent=2, ensure_ascii=False)
    _log(f"Result written: {r.get('status')}")
    print(json.dumps(r, ensure_ascii=False))
