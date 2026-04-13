"""
session1_click_login.py -- runs IN Administrator's interactive session (Session 1).

Click strategy (in order):
  1. vncdo — TightVNC hardware-level injection (same path as noVNC user click)
  2. PostMessage(WM_LBUTTONDOWN) — bypasses LLMHF_INJECTED CEF filter
  3. press_enter() — keybd_event(VK_RETURN) proven to work (20:37:31 JST login)

Screenshot before clicking: saved to C:\\cits\\login_screenshot.png for diagnosis.
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

RESULT_FILE      = r"C:\cits\session1_login_result.json"
SCREENSHOT_FILE  = r"C:\cits\login_screenshot.png"

# ─── Screen coords (1024×768 VPS) ───────────────────────────────────────────
LOGIN_BTN      = (779, 475)
TWO_FA_INPUT   = (769, 455)
TWO_FA_SUBMIT  = (769, 530)
KABU_EXE       = r"C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe"
SCREEN_W, SCREEN_H = 1024, 768

# ─── VNC settings ────────────────────────────────────────────────────────────
VNCDO_EXE = r"C:\cits\venv\Scripts\vncdo.exe"
VNC_PASS  = "cits2026"

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

# WM_ message constants (for PostMessage direct injection)
WM_MOUSEMOVE   = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP   = 0x0202
MK_LBUTTON     = 0x0001

# subprocess flag — suppress all console windows
CREATE_NO_WINDOW = 0x08000000

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


def take_screenshot(path: str = SCREENSHOT_FILE) -> bool:
    """Take a screenshot of the desktop (Session 1) and save to path."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(path)
        # Log the pixel color at the login button position
        px = img.getpixel(LOGIN_BTN)
        _log(f"Screenshot saved to {path} | pixel@LOGIN_BTN{LOGIN_BTN}=RGB{px}")
        return True
    except Exception as e:
        _log(f"Screenshot failed (PIL not available?): {e}")
        return False


def find_login_btn_in_screenshot() -> tuple[int, int] | None:
    """Try to find the login button in the screenshot by color.
    kabuStation login button is blue. Returns (x, y) or None.
    Falls back to hardcoded LOGIN_BTN if PIL unavailable.
    """
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(SCREENSHOT_FILE)
        # Check if expected pixel at LOGIN_BTN looks like a blue button
        # Blue range: R<120, G<150, B>150
        px = img.getpixel(LOGIN_BTN)
        _log(f"find_login_btn: pixel@{LOGIN_BTN}=RGB{px}")
        if len(px) >= 3 and px[2] > px[0] + 50:  # definitely more blue than red
            _log(f"Login button appears to be at hardcoded {LOGIN_BTN} (blue pixel confirmed)")
            return LOGIN_BTN

        # Scan kabuStation window area for blue button
        kabu_left, kabu_top = 23, 57
        kabu_right, kabu_bottom = 1001, 662
        best = None
        for y in range(kabu_top + 300, kabu_bottom - 50, 5):
            for x in range(kabu_left + 400, kabu_right - 100, 5):
                p = img.getpixel((x, y))
                if len(p) >= 3 and p[2] > 150 and p[2] > p[0] + 80 and p[2] > p[1] + 30:
                    best = (x, y)
        if best:
            _log(f"find_login_btn: found blue pixel at {best}")
        else:
            _log(f"find_login_btn: no blue button found, using hardcoded {LOGIN_BTN}")
            best = LOGIN_BTN
        return best
    except Exception as e:
        _log(f"find_login_btn error: {e} — using hardcoded {LOGIN_BTN}")
        return LOGIN_BTN


def vncdo_click(x: int, y: int) -> bool:
    """Hardware-level click via TightVNC server.
    TightVNC injects at kernel level — CEF accepts these events (same as noVNC).
    """
    if not os.path.isfile(VNCDO_EXE):
        _log(f"vncdo_click: {VNCDO_EXE} not found — skipping")
        return False
    try:
        r = subprocess.run(
            [VNCDO_EXE, "-s", "localhost", f"--port=5900",
             f"--password={VNC_PASS}", "move", str(x), str(y), "click", "1"],
            capture_output=True, text=True, timeout=10,
            creationflags=CREATE_NO_WINDOW,
        )
        _log(f"vncdo_click({x},{y}) rc={r.returncode} "
             f"out={r.stdout.strip()!r} err={r.stderr.strip()[:80]!r}")
        return r.returncode == 0
    except Exception as e:
        _log(f"vncdo_click error: {e}")
        return False


def click_at(x: int, y: int) -> None:
    """Fallback: mouse_event (synthetic, tagged LLMHF_INJECTED — CEF may ignore)."""
    ax = int(x * 65535 / SCREEN_W)
    ay = int(y * 65535 / SCREEN_H)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, ax, ay, 0, 0)
    time.sleep(0.5)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_ABSOLUTE, ax, ay, 0, 0)
    time.sleep(0.1)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP | MOUSEEVENTF_ABSOLUTE, ax, ay, 0, 0)
    _log(f"click_at({x}, {y}) [mouse_event fallback]")


def post_click_cef(x_screen: int, y_screen: int) -> bool:
    """PostMessage WM_LBUTTONDOWN/UP directly to the window under the cursor.
    Bypasses LLMHF_INJECTED — better than mouse_event but less reliable than vncdo.
    """
    user32 = ctypes.windll.user32
    ax = int(x_screen * 65535 / SCREEN_W)
    ay = int(y_screen * 65535 / SCREEN_H)
    user32.mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, ax, ay, 0, 0)
    time.sleep(0.5)

    pt = POINT(x_screen, y_screen)
    target_hwnd = user32.WindowFromPoint(pt)
    title = get_window_title(target_hwnd)
    _log(f"post_click_cef: hwnd={target_hwnd}, title={title!r}")

    if target_hwnd:
        client_pt = POINT(x_screen, y_screen)
        user32.ScreenToClient(target_hwnd, ctypes.byref(client_pt))
        cx, cy = client_pt.x, client_pt.y
        lParam = ctypes.c_long((cy << 16) | (cx & 0xFFFF)).value
        user32.PostMessageW(target_hwnd, WM_MOUSEMOVE, 0, lParam)
        time.sleep(0.15)
        user32.PostMessageW(target_hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lParam)
        time.sleep(0.15)
        user32.PostMessageW(target_hwnd, WM_LBUTTONUP, 0, lParam)
        _log(f"PostMessage sent to hwnd={target_hwnd}, client=({cx},{cy})")
        return True

    _log("post_click_cef: no hwnd — falling back to mouse_event")
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_ABSOLUTE, ax, ay, 0, 0)
    time.sleep(0.1)
    user32.mouse_event(MOUSEEVENTF_LEFTUP | MOUSEEVENTF_ABSOLUTE, ax, ay, 0, 0)
    return False


def press_enter() -> None:
    """Press Enter key — triggers default button on focused form."""
    ctypes.windll.user32.keybd_event(VK_RETURN, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)
    _log("press_enter()")


def paste_text(text: str) -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", f'Set-Clipboard -Value "{text}"'],
        capture_output=True, timeout=5,
        creationflags=CREATE_NO_WINDOW,
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
    """Use MainWindowHandle + SetForegroundWindow. Returns (success, hwnd)."""
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
            creationflags=CREATE_NO_WINDOW,
        )
        hwnd_str = (r.stdout or "").strip()
        _log(f"KabuS MainWindowHandle: {hwnd_str!r}")
        if hwnd_str and hwnd_str.isdigit() and int(hwnd_str) != 0:
            hwnd = int(hwnd_str)
            user32 = ctypes.windll.user32

            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            _log(f"KabuS rect: left={rect.left}, top={rect.top}, "
                 f"right={rect.right}, bottom={rect.bottom}")

            user32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.5)
            user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            rc = user32.SetForegroundWindow(hwnd)
            time.sleep(1)
            _log(f"SetForegroundWindow({hwnd}) -> rc={rc}")

            pt = POINT(LOGIN_BTN[0], LOGIN_BTN[1])
            win_at = user32.WindowFromPoint(pt)
            win_title = get_window_title(win_at)
            _log(f"Window at LOGIN_BTN {LOGIN_BTN}: hwnd={win_at}, title={win_title!r}")

            if win_at and win_at != hwnd:
                top = user32.GetAncestor(win_at, GA_ROOT) or win_at
                if top == hwnd:
                    _log(f"LOGIN_BTN window is kabuStation CEF child — OK")
                else:
                    top_title = get_window_title(top)
                    _log(f"BLOCKING foreign window: minimizing hwnd={top}, title={top_title!r}")
                    user32.ShowWindow(top, 6)
                    time.sleep(0.5)
                    user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
                    user32.SetForegroundWindow(hwnd)
                    time.sleep(1)
                    win_at2 = user32.WindowFromPoint(pt)
                    _log(f"After minimize, LOGIN_BTN window: {win_at2} title={get_window_title(win_at2)!r}")

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
        creationflags=CREATE_NO_WINDOW,
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
            creationflags=CREATE_NO_WINDOW,
        )
        ok = '"Token"' in (r.stdout or "")
        _log(f"check_api -> {'OK' if ok else 'NOT_READY'} ({(r.stdout or '')[:80]!r})")
        return ok
    except Exception as e:
        _log(f"check_api error: {e}")
        return False


def check_gmail_diagnostic() -> str:
    """Count ALL kabu 2FA emails in Gmail INBOX + latest header."""
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
        subprocess.Popen([KABU_EXE], creationflags=CREATE_NO_WINDOW)
        # Wait up to 90s for kabuStation to fully load its login UI
        for i in range(9):
            time.sleep(10)
            if kabu_running():
                _log(f"KabuS started after {(i+1)*10}s")
                break
        else:
            result["status"] = "FAILED: kabuStation did not start"
            result["diagnostics"] = DIAGNOSTICS
            return result
        _log("Waiting 60s for kabuStation login UI to fully render...")
        time.sleep(60)
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

    # Step 4: Screenshot + find login button coords
    _log("Taking screenshot to locate login button...")
    btn_pos = find_login_btn_in_screenshot()
    result["btn_pos_found"] = btn_pos
    _log(f"Using login button position: {btn_pos}")

    # Step 5: Click login button — 3-layer approach
    login_clicked_at = datetime.now()
    result["login_click_at"] = login_clicked_at.isoformat()

    # Layer 1: vncdo (TightVNC hardware injection — same path as noVNC)
    _log(f"[Layer 1] vncdo_click{btn_pos}...")
    vnc_ok = vncdo_click(*btn_pos)
    result["vncdo_ok"] = vnc_ok
    time.sleep(1)

    # Layer 2: PostMessage to CEF window (bypasses LLMHF_INJECTED)
    _log(f"[Layer 2] post_click_cef{btn_pos}...")
    post_click_cef(*btn_pos)
    time.sleep(0.5)

    # Layer 3: Enter key (proven to work — triggered 20:37:31 JST login)
    _log("[Layer 3] press_enter()...")
    press_enter()
    time.sleep(20)

    # Step 6: Check if login succeeded without 2FA
    if check_api():
        result["status"] = "LOGIN_SUCCESS_NO_2FA"
        _log("LOGIN SUCCESS (no 2FA)!")
        result["diagnostics"] = DIAGNOSTICS
        return result

    # Step 6b: Gmail diagnostic
    _log("Running Gmail diagnostic...")
    gmail_diag = check_gmail_diagnostic()
    _log(f"Gmail diagnostic: {gmail_diag}")
    result["gmail_diagnostic"] = gmail_diag

    # Step 7: Get 2FA code from Gmail
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

    # Step 8: Enter 2FA code
    vncdo_click(*TWO_FA_INPUT)
    post_click_cef(*TWO_FA_INPUT)
    time.sleep(1)
    paste_text(code)
    time.sleep(1)
    vncdo_click(*TWO_FA_SUBMIT)
    post_click_cef(*TWO_FA_SUBMIT)
    time.sleep(15)

    # Step 9: Final API check
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
