"""
session1_click_login.py -- runs IN Administrator's interactive session (Session 1).

Click strategy (in order):
  0. Playwright connect_over_cdp — DOM-level click (bypasses all synthetic input issues)
  1. Direct VNC RFB PointerEvent — hardware-level (same as noVNC manual click)
  2. PostMessage(WM_LBUTTONDOWN)
  3. press_enter()

Writes result to C:\\cits\\session1_login_result.json.
Run with pythonw.exe (no console window).
"""
import sys
import os
import ctypes
import ctypes.wintypes
import time
import subprocess
import json
from datetime import datetime

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

RESULT_FILE     = r"C:\cits\session1_login_result.json"
SCREENSHOT_FILE = r"C:\cits\login_screenshot.png"
KABU_EXE        = r"C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe"

# ─── Screen coords (1024×768 VPS) ───────────────────────────────────────────
# Button color: ORANGE (255,86,0) confirmed by pixel scan 2026-04-13
LOGIN_BTN     = (779, 505)   # orange button center (was 475 = gray background)
TWO_FA_INPUT  = (769, 455)
TWO_FA_SUBMIT = (769, 530)
SCREEN_W, SCREEN_H = 1024, 768

# ─── VNC settings ────────────────────────────────────────────────────────────
VNC_HOST = "localhost"
VNC_PORT = 5900
VNC_PASS = "cits2026"

# ─── CDP ports to scan for KabuStation ──────────────────────────────────────
# Port 9222 = Chrome browser; 9223+ might be KabuStation CEF
CDP_PORTS_TO_TRY = [9223, 9224, 9225, 9222, 9226, 9227, 9228, 9229, 9230]

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
WM_MOUSEMOVE   = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP   = 0x0202
MK_LBUTTON     = 0x0001
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


# ─── Layer 0: Playwright CDP click ──────────────────────────────────────────

def _find_kabu_cdp_url() -> str | None:
    """Scan CDP ports to find KabuStation CEF (not Chrome/X.com/etc)."""
    import urllib.request
    import json as _json
    # Keywords that indicate this is NOT KabuStation
    NON_KABU = ("google", "keep", "gmail", "chrome-extension",
                 "x.com", "twitter", "service worker", "youtube",
                 "facebook", "bing", "microsoft")
    for port in CDP_PORTS_TO_TRY:
        try:
            with urllib.request.urlopen(f"http://localhost:{port}/json", timeout=2) as r:
                targets = _json.loads(r.read())
            titles = [t.get("title", "") for t in targets]
            urls   = [t.get("url",   "") for t in targets]
            combined = " ".join(titles + urls).lower()
            is_not_kabu = any(kw in combined for kw in NON_KABU)
            _log(f"CDP port {port}: {len(targets)} targets, titles={[t[:25] for t in titles[:3]]}, not_kabu={is_not_kabu}")
            if not is_not_kabu and targets:
                _log(f"CDP port {port}: candidate for KabuStation!")
                return f"http://localhost:{port}"
        except Exception as e:
            _log(f"CDP port {port}: {e}")
    _log("CDP: no KabuStation port found (all ports are Chrome/X.com or empty)")
    return None


def playwright_click_login() -> bool:
    """Layer 0: Click login button via Playwright + CDP.
    Works even if the button isn't visible in screenshot — DOM-level click.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        _log("Playwright not installed — skipping. Run: pip install playwright")
        return False

    cdp_url = _find_kabu_cdp_url()
    if not cdp_url:
        _log("Playwright: no KabuStation CDP port found (all ports have Chrome or no targets)")
        return False

    _log(f"Playwright: connecting to {cdp_url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url, timeout=15000)
            _log(f"Playwright: connected, {len(browser.contexts)} contexts")
            for ctx in browser.contexts:
                for page in ctx.pages:
                    _log(f"Playwright: page url={page.url[:80]!r}")
                    # Dump DOM for diagnosis
                    try:
                        info = page.evaluate(
                            "document.title + ' | readyState:' + document.readyState "
                            "+ ' | buttons:' + document.querySelectorAll('button').length"
                        )
                        _log(f"Playwright: page info: {info!r}")
                    except Exception as e:
                        _log(f"Playwright: eval error: {e}")

                    # Try multiple selectors to find login button
                    selectors = [
                        "button:has-text('ログイン')",
                        "input[type=submit]",
                        "button[type=submit]",
                        "text=ログイン",
                        "button",
                    ]
                    for sel in selectors:
                        try:
                            locs = page.locator(sel).all()
                            for loc in locs:
                                try:
                                    txt = loc.inner_text(timeout=500)
                                    visible = loc.is_visible(timeout=500)
                                    _log(f"Playwright: found '{sel}' text={txt!r} visible={visible}")
                                    if visible or "ログイン" in txt:
                                        loc.click(timeout=3000, force=True)
                                        _log(f"Playwright: CLICKED '{txt}'!")
                                        return True
                                except Exception:
                                    pass
                        except Exception:
                            pass
    except Exception as e:
        _log(f"Playwright: error: {e}")
    _log("Playwright: login button not found")
    return False


# ─── Layer 1: Direct VNC RFB PointerEvent ───────────────────────────────────

def _vnc_reverse_bits(b: int) -> int:
    result = 0
    for _ in range(8):
        result = (result << 1) | (b & 1)
        b >>= 1
    return result


def _vnc_des_encrypt(key8: bytes, data16: bytes) -> bytes:
    try:
        from Crypto.Cipher import DES
        return DES.new(key8, DES.MODE_ECB).encrypt(data16)
    except ImportError:
        pass
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        enc = Cipher(algorithms.TripleDES(key8 * 3), modes.ECB(),
                     backend=default_backend()).encryptor()
        return enc.update(data16) + enc.finalize()
    except Exception:
        pass
    r = subprocess.run(
        ["openssl", "enc", "-des-ecb", "-nosalt", "-nopad", "-K", key8.hex()],
        input=data16, capture_output=True, timeout=5, creationflags=CREATE_NO_WINDOW,
    )
    if r.returncode == 0:
        return r.stdout[:16]
    raise RuntimeError("No DES backend (need pycryptodome, cryptography, or openssl)")


def _vnc_connect_and_auth() -> "socket.socket | None":
    """Connect to VNC server and authenticate. Returns socket or None."""
    import socket as _sock
    import struct as _struct
    try:
        sock = _sock.create_connection((VNC_HOST, VNC_PORT), timeout=10)
    except Exception as e:
        _log(f"VNC connect failed: {e}")
        return None
    try:
        server_ver = sock.recv(12)
        if not server_ver.startswith(b"RFB "):
            _log(f"VNC bad handshake: {server_ver!r}")
            sock.close()
            return None
        sock.sendall(b"RFB 003.008\n")

        ntypes = sock.recv(1)[0]
        if ntypes == 0:
            _log("VNC: 0 security types")
            sock.close()
            return None
        sec_types = list(sock.recv(ntypes))
        _log(f"VNC sec types={sec_types}")

        if 1 in sec_types:
            # None authentication — no challenge/response
            sock.sendall(bytes([1]))
            try:
                result_bytes = sock.recv(4)
                if len(result_bytes) == 4:
                    result = _struct.unpack(">I", result_bytes)[0]
                    if result != 0:
                        _log(f"VNC None auth failed (result={result})")
                        sock.close()
                        return None
            except Exception:
                pass  # Some servers skip SecurityResult for None auth
            _log("VNC: None auth OK")
        elif 2 in sec_types:
            sock.sendall(bytes([2]))
            challenge = sock.recv(16)
            pwd_bytes = bytes(_vnc_reverse_bits(ord(c)) for c in (VNC_PASS + "\x00" * 8)[:8])
            response = _vnc_des_encrypt(pwd_bytes, challenge)
            sock.sendall(response)
            result = _struct.unpack(">I", sock.recv(4))[0]
            if result != 0:
                _log(f"VNC auth failed (result={result})")
                sock.close()
                return None
            _log("VNC: VNC auth OK")
        else:
            _log(f"VNC: no supported auth types in {sec_types}")
            sock.close()
            return None

        # ClientInit + read ServerInit
        sock.sendall(bytes([1]))  # shared=1
        _w = _struct.unpack(">H", sock.recv(2))[0]
        _h = _struct.unpack(">H", sock.recv(2))[0]
        sock.recv(16)  # pixel format
        name_len = _struct.unpack(">I", sock.recv(4))[0]
        if name_len > 0:
            sock.recv(name_len)
        _log(f"VNC: desktop {_w}x{_h}")
        return sock
    except Exception as e:
        _log(f"VNC connect/auth error: {e}")
        sock.close()
        return None


def vnc_rfb_click(x: int, y: int) -> bool:
    """Direct VNC RFB PointerEvent — same mechanism as noVNC manual click."""
    import struct as _struct
    _log(f"vnc_rfb_click({x},{y}): connecting to {VNC_HOST}:{VNC_PORT}...")
    sock = _vnc_connect_and_auth()
    if sock is None:
        return False
    try:
        sock.sendall(_struct.pack(">BBHH", 5, 1, x, y))  # button down
        time.sleep(0.15)
        sock.sendall(_struct.pack(">BBHH", 5, 0, x, y))  # button up
        time.sleep(0.1)
        _log(f"vnc_rfb_click({x},{y}): sent OK")
        return True
    except Exception as e:
        _log(f"vnc_rfb_click error: {e}")
        return False
    finally:
        sock.close()


def vnc_type_text(text: str) -> bool:
    """Type text via VNC RFB KeyEvent (hardware-level keyboard input)."""
    import struct as _struct
    _log(f"vnc_type_text({text!r}): connecting to {VNC_HOST}:{VNC_PORT}...")
    sock = _vnc_connect_and_auth()
    if sock is None:
        return False
    try:
        for char in text:
            keysym = ord(char)  # ASCII = X11 keysym for printable ASCII
            sock.sendall(_struct.pack(">BBHI", 4, 1, 0, keysym))  # key down
            time.sleep(0.05)
            sock.sendall(_struct.pack(">BBHI", 4, 0, 0, keysym))  # key up
            time.sleep(0.05)
        _log(f"vnc_type_text: typed {len(text)} chars OK")
        return True
    except Exception as e:
        _log(f"vnc_type_text error: {e}")
        return False
    finally:
        sock.close()


# ─── Layer 2: PostMessage to CEF ────────────────────────────────────────────

def post_click_cef(x_screen: int, y_screen: int) -> bool:
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
        time.sleep(0.1)
        user32.PostMessageW(target_hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lParam)
        time.sleep(0.1)
        user32.PostMessageW(target_hwnd, WM_LBUTTONUP, 0, lParam)
        _log(f"PostMessage sent to hwnd={target_hwnd}, client=({cx},{cy})")
        return True
    return False


# ─── Layer 3: Enter key ──────────────────────────────────────────────────────

def press_enter() -> None:
    ctypes.windll.user32.keybd_event(VK_RETURN, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)
    _log("press_enter()")


# ─── Utilities ───────────────────────────────────────────────────────────────

def paste_text(text: str) -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", f'Set-Clipboard -Value "{text}"'],
        capture_output=True, timeout=5, creationflags=CREATE_NO_WINDOW,
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
    GA_ROOT = 2
    HWND_TOP = ctypes.c_void_p(0)
    SWP_NOMOVE, SWP_NOSIZE = 0x0002, 0x0001
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "$p = Get-Process KabuS -EA SilentlyContinue; "
             "if ($p -and $p.MainWindowHandle -ne 0) { $p.MainWindowHandle } else { '0' }"],
            capture_output=True, text=True, timeout=8,
            encoding="utf-8", errors="replace", creationflags=CREATE_NO_WINDOW,
        )
        hwnd_str = (r.stdout or "").strip()
        _log(f"KabuS MainWindowHandle: {hwnd_str!r}")
        if hwnd_str and hwnd_str.isdigit() and int(hwnd_str) != 0:
            hwnd = int(hwnd_str)
            user32 = ctypes.windll.user32
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            _log(f"KabuS rect: {rect.left},{rect.top},{rect.right},{rect.bottom}")
            user32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.5)
            user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            rc = user32.SetForegroundWindow(hwnd)
            _log(f"SetForegroundWindow({hwnd}) -> rc={rc}")
            time.sleep(1)
            return True, hwnd
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
            shell=True, capture_output=True, text=True, timeout=8,
            encoding="cp932", errors="replace", creationflags=CREATE_NO_WINDOW,
        )
        ok = '"Token"' in (r.stdout or "")
        _log(f"check_api -> {'OK' if ok else 'NOT_READY'} ({(r.stdout or '')[:80]!r})")
        return ok
    except Exception as e:
        _log(f"check_api error: {e}")
        return False


def take_screenshot() -> tuple[int, int] | None:
    """Take screenshot, log pixel grid, return orange button coords if found."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(SCREENSHOT_FILE)
        px = img.getpixel(LOGIN_BTN)
        _log(f"screenshot saved | LOGIN_BTN{LOGIN_BTN}=RGB{px[:3]}")
        # Dump pixel grid around LOGIN_BTN for diagnosis
        for dy in range(-60, 80, 20):
            row = []
            for dx in range(-80, 100, 20):
                p = img.getpixel((LOGIN_BTN[0]+dx, LOGIN_BTN[1]+dy))
                row.append(f"({p[0]},{p[1]},{p[2]})")
            _log(f"  pixels y={LOGIN_BTN[1]+dy}: {' '.join(row)}")
        # Scan for orange button (255,86,0 ± tolerance)
        kabu_left, kabu_top, kabu_right, kabu_bottom = 23, 57, 1001, 662
        orange_hits = []
        for sy in range(kabu_top + 200, kabu_bottom - 50, 5):
            for sx in range(kabu_left + 300, kabu_right - 50, 5):
                p = img.getpixel((sx, sy))
                if p[0] > 200 and p[1] < 150 and p[2] < 100:  # orange-red
                    orange_hits.append((sx, sy))
        if orange_hits:
            mid = orange_hits[len(orange_hits)//2]
            _log(f"Orange button scan: {len(orange_hits)} pixels found, mid={mid}")
            return mid
        _log("Orange button scan: no orange pixels found")
        return None
    except Exception as e:
        _log(f"screenshot error: {e}")
        return None


def check_gmail_diagnostic() -> str:
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

    # Step 1: Ensure KabuStation running
    if not kabu_running():
        _log("KabuS not running — starting...")
        subprocess.Popen([KABU_EXE], creationflags=CREATE_NO_WINDOW)
        for i in range(9):
            time.sleep(10)
            if kabu_running():
                _log(f"KabuS started after {(i+1)*10}s")
                break
        else:
            result["status"] = "FAILED: KabuS did not start"
            result["diagnostics"] = DIAGNOSTICS
            return result
        _log("KabuS started, waiting 90s for login UI to load...")
        time.sleep(90)
    else:
        _log("KabuS already running — waiting 30s for UI...")
        time.sleep(30)

    # Step 2: Check if already logged in
    if check_api():
        result["status"] = "ALREADY_LOGGED_IN"
        _log("Already logged in!")
        result["diagnostics"] = DIAGNOSTICS
        return result

    # Step 3: Bring KabuStation to front + screenshot to find orange button
    bring_kabu_to_front()
    time.sleep(1)
    detected_btn = take_screenshot()  # returns orange button coords or None
    btn_pos = detected_btn if detected_btn else LOGIN_BTN
    _log(f"Using button position: {btn_pos} (detected={detected_btn is not None})")
    result["btn_pos"] = btn_pos

    # Step 4: Click attempts
    login_clicked_at = datetime.now()
    result["login_click_at"] = login_clicked_at.isoformat()

    # Layer 0: Playwright (KabuStation CEF CDP if available)
    _log("[Layer 0] Playwright CDP click...")
    pw_ok = playwright_click_login()
    result["playwright_ok"] = pw_ok
    time.sleep(2)

    # Layer 1: Direct VNC RFB (hardware-level, CEF accepts it)
    _log(f"[Layer 1] vnc_rfb_click{btn_pos}...")
    vnc_ok = vnc_rfb_click(*btn_pos)
    result["vnc_rfb_ok"] = vnc_ok
    time.sleep(1)

    # Layer 2: PostMessage
    _log(f"[Layer 2] post_click_cef{btn_pos}...")
    post_click_cef(*btn_pos)
    time.sleep(0.5)

    # Layer 3: Enter
    _log("[Layer 3] press_enter()...")
    press_enter()
    time.sleep(20)

    # Step 5: Check login
    if check_api():
        result["status"] = "LOGIN_SUCCESS_NO_2FA"
        _log("LOGIN SUCCESS (no 2FA)!")
        result["diagnostics"] = DIAGNOSTICS
        return result

    # Step 6: Gmail 2FA
    _log("Running Gmail diagnostic...")
    gmail_diag = check_gmail_diagnostic()
    _log(f"Gmail diagnostic: {gmail_diag}")
    result["gmail_diagnostic"] = gmail_diag

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

    # Step 7: Enter 2FA
    _log("Taking screenshot of 2FA screen...")
    take_screenshot()
    time.sleep(0.5)

    _log(f"[2FA] Clicking 2FA input {TWO_FA_INPUT}...")
    if not vnc_rfb_click(*TWO_FA_INPUT):
        post_click_cef(*TWO_FA_INPUT)
    time.sleep(1.5)

    _log(f"[2FA] Typing code via VNC keyboard...")
    if not vnc_type_text(code):
        _log("[2FA] VNC type failed, using clipboard paste fallback...")
        paste_text(code)
    time.sleep(1)

    _log(f"[2FA] Clicking submit {TWO_FA_SUBMIT}...")
    if not vnc_rfb_click(*TWO_FA_SUBMIT):
        post_click_cef(*TWO_FA_SUBMIT)
    time.sleep(25)

    # Step 8: Final check
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
