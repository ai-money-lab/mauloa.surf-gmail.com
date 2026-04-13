"""
session1_click_login.py -- runs IN Administrator's interactive session (Session 1).
Uses ctypes mouse_event to click kabuStation login button and handle 2FA.
Writes result to C:\\cits\\session1_login_result.json.

Run with pythonw.exe (no console window) so nothing steals focus from kabuStation.
"""
import sys
import os
import ctypes
import ctypes.wintypes
import time
import subprocess
import json
from datetime import datetime, timedelta

# ─── Setup paths / env ──────────────────────────────────────────────────────
REPO_ROOT = r"C:\cits\repo"
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)

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
KABU_EXE       = r"C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe"
SCREEN_W, SCREEN_H = 1024, 768

# ─── WinAPI constants ────────────────────────────────────────────────────────
MOUSEEVENTF_MOVE      = 0x0001
MOUSEEVENTF_LEFTDOWN  = 0x0002
MOUSEEVENTF_LEFTUP    = 0x0004
MOUSEEVENTF_ABSOLUTE  = 0x8000
KEYEVENTF_KEYUP       = 0x0002
VK_RETURN  = 0x0D
VK_CONTROL = 0x11
VK_V       = 0x56
SW_RESTORE = 9

DIAGNOSTICS: list = []


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    DIAGNOSTICS.append(line)


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_window_title(hwnd: int) -> str:
    if not hwnd:
        return ""
    try:
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""


def click_at(x: int, y: int) -> None:
    """Move mouse to position (hover), then click."""
    ax = int(x * 65535 / SCREEN_W)
    ay = int(y * 65535 / SCREEN_H)
    # Move first and wait for hover effects
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, ax, ay, 0, 0)
    time.sleep(0.5)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_ABSOLUTE, ax, ay, 0, 0)
    time.sleep(0.1)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP | MOUSEEVENTF_ABSOLUTE, ax, ay, 0, 0)
    _log(f"click_at({x}, {y})")


def press_enter() -> None:
    """Press Enter key (triggers default button on forms)."""
    ctypes.windll.user32.keybd_event(VK_RETURN, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)
    _log("press_enter()")


def paste_text(text: str) -> None:
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


def bring_kabu_to_front() -> tuple[bool, int]:
    """Use MainWindowHandle + SetForegroundWindow.
    Returns (success, hwnd).
    """
    GA_ROOT = 2
    HWND_TOP = ctypes.c_void_p(0)
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001

    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "$p = Get-Process KabuS -ErrorAction SilentlyContinue; "
             "if ($p -and $p.MainWindowHandle -ne 0) { $p.MainWindowHandle } else { '0' }"],
            capture_output=True, text=True, timeout=8,
            encoding="utf-8", errors="replace",
        )
        hwnd_str = (r.stdout or "").strip()
        _log(f"KabuS MainWindowHandle: {hwnd_str!r}")
        if hwnd_str and hwnd_str.isdigit() and int(hwnd_str) != 0:
            hwnd = int(hwnd_str)
            user32 = ctypes.windll.user32

            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            _log(f"KabuS window rect: left={rect.left}, top={rect.top}, right={rect.right}, bottom={rect.bottom}")

            user32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.5)
            user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            rc = user32.SetForegroundWindow(hwnd)
            time.sleep(1)
            _log(f"SetForegroundWindow({hwnd}) -> rc={rc}")

            # Check what's at login button position
            pt = POINT(LOGIN_BTN[0], LOGIN_BTN[1])
            win_at = user32.WindowFromPoint(pt)
            win_title = get_window_title(win_at)
            _log(f"Window at LOGIN_BTN {LOGIN_BTN}: hwnd={win_at}, title={win_title!r}")

            if win_at and win_at != hwnd:
                top = user32.GetAncestor(win_at, GA_ROOT) or win_at
                if top == hwnd:
                    _log(f"Window at LOGIN_BTN is kabuStation CEF child (hwnd={win_at}) - OK")
                else:
                    top_title = get_window_title(top)
                    _log(f"BLOCKING foreign window: minimizing hwnd={top}, title={top_title!r}")
                    user32.ShowWindow(top, 6)  # SW_MINIMIZE
                    time.sleep(0.5)
                    user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
                    user32.SetForegroundWindow(hwnd)
                    time.sleep(1)
                    win_at2 = user32.WindowFromPoint(pt)
                    _log(f"After minimize, window at LOGIN_BTN: hwnd={win_at2}, title={get_window_title(win_at2)!r}")

            return True, hwnd
        _log("MainWindowHandle=0 or blank")
    except Exception as e:
        _log(f"bring_kabu_to_front error: {e}")

    return False, 0


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
        ok = '"Token"' in (r.stdout or "")
        _log(f"check_api -> {'OK' if ok else 'NOT_READY'} ({(r.stdout or '')[:80]!r})")
        return ok
    except Exception as e:
        _log(f"check_api error: {e}")
        return False


def check_gmail_diagnostic() -> str:
    """Check if ANY kabu 2FA email exists in Gmail INBOX (diagnostic only)."""
    try:
        import imaplib
        from pathlib import Path
        env_path = Path(r"C:\cits\repo\cits\.env")
        pwd = ""
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("GMAIL_APP_PASSWORD="):
                pwd = line.split("=", 1)[1].strip()
        if not pwd:
            return "no_gmail_password"
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login("mauloa.surf@gmail.com", pwd)
        mail.select("INBOX")
        _, msgs = mail.search(None, 'FROM "no-reply@mail.kabu.com"')
        count = len(msgs[0].split()) if msgs[0] else 0
        result = f"gmail_kabu_emails_in_inbox={count}"
        if count > 0:
            # Fetch subject+date of latest
            uid = msgs[0].split()[-1]
            _, data = mail.fetch(uid, "(BODY[HEADER.FIELDS (DATE SUBJECT)])")
            if data and data[0]:
                header = data[0][1].decode("utf-8", errors="replace").strip()
                result += f" | latest_header: {header[:200]}"
        mail.logout()
        return result
    except Exception as e:
        return f"gmail_check_error: {e}"


def main() -> dict:
    result = {"status": "unknown", "ts": datetime.now().isoformat()}
    _log(f"session1_click_login started at {result['ts']}")

    # Step 1: Ensure kabuStation is running
    if not kabu_running():
        _log("KabuS not running — starting directly...")
        subprocess.Popen([KABU_EXE])
        time.sleep(35)
        if not kabu_running():
            result["status"] = "FAILED: kabuStation did not start"
            result["diagnostics"] = DIAGNOSTICS
            return result
        _log("KabuS started, waiting 15s more for UI to fully load...")
        time.sleep(15)
    else:
        _log("KabuS already running")

    # Step 2: Check if already logged in
    if check_api():
        result["status"] = "ALREADY_LOGGED_IN"
        _log("Already logged in!")
        result["diagnostics"] = DIAGNOSTICS
        return result

    # Step 3: Bring kabuStation to front
    _log("Bringing kabuStation to foreground...")
    focused, kabu_hwnd = bring_kabu_to_front()
    result["window_focused"] = focused
    result["kabu_hwnd"] = kabu_hwnd
    time.sleep(1)

    # Step 4: Click login button AND press Enter (double approach)
    _log(f"Clicking LOGIN_BTN {LOGIN_BTN} then pressing Enter...")
    login_clicked_at = datetime.now()
    click_at(*LOGIN_BTN)
    time.sleep(0.5)
    press_enter()          # Enter key as backup (triggers default button)
    time.sleep(20)
    result["login_click_at"] = login_clicked_at.isoformat()

    # Step 5: Check if login succeeded without 2FA
    if check_api():
        result["status"] = "LOGIN_SUCCESS_NO_2FA"
        _log("LOGIN SUCCESS (no 2FA)!")
        result["diagnostics"] = DIAGNOSTICS
        return result

    # Step 5b: Gmail diagnostic — how many kabu emails exist at all?
    _log("Running Gmail diagnostic...")
    gmail_diag = check_gmail_diagnostic()
    _log(f"Gmail diagnostic: {gmail_diag}")
    result["gmail_diagnostic"] = gmail_diag

    # Step 6: Get 2FA code from Gmail
    _log("2FA required. Fetching from Gmail...")
    try:
        from cits.scripts.kabu_auto_login_vps import get_2fa_from_gmail
        code = get_2fa_from_gmail(max_wait_sec=150, not_before=login_clicked_at)
    except Exception as e:
        _log(f"Gmail error: {e}")
        import traceback
        result["gmail_error"] = traceback.format_exc()
        code = ""

    if not code:
        result["status"] = "FAILED: no 2FA code"
        _log("No 2FA code received")
        result["diagnostics"] = DIAGNOSTICS
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

    result["diagnostics"] = DIAGNOSTICS
    return result


if __name__ == "__main__":
    try:
        r = main()
    except Exception as exc:
        import traceback
        r = {
            "status": f"EXCEPTION: {exc}",
            "tb": traceback.format_exc(),
            "diagnostics": DIAGNOSTICS,
        }
        _log(f"Exception: {exc}")

    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(r, f, indent=2, ensure_ascii=False)
    _log(f"Result written: {r.get('status')}")
    try:
        print(json.dumps(r, ensure_ascii=False))
    except Exception:
        pass
