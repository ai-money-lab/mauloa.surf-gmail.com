# -*- coding: utf-8 -*-
"""kabuStation Auto-Login via VNC (vncdotool)

This is the WORKING solution. Previous approaches (SendKeys, pyautogui via
Task Scheduler) all failed because Task Scheduler cannot access the console
desktop GUI. VNC bypasses this limitation completely.

Flow:
1. Kill existing kabuStation
2. Start kabuStation via VNC (Win+R -> path)
3. Wait for login window
4. Type password via VNC
5. Handle 2FA if needed (requires Gmail API - done externally)
6. Verify API token
"""
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

LOG_FILE = Path("C:/cits/logs/kabu_vnc_login.log")
KABU_PATH = r"C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe"
API_PASSWORD = "hiroki0380"
VNC_PASSWORD = "cits2026"
VNCDO = r"C:\cits\venv\Scripts\vncdo.exe"


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("utf-8", errors="replace").decode("ascii", errors="replace"))
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def vnc(cmd: str):
    """Execute a vncdo command."""
    full = f"{VNCDO} -s localhost -p {VNC_PASSWORD} {cmd}"
    result = subprocess.run(full, shell=True, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=30)
    if result.returncode != 0:
        err = (result.stderr or "")[:200]
        log(f"VNC command failed: {cmd} -> {err}")
    return result.returncode == 0


def vnc_screenshot(name: str):
    path = f"C:/cits/logs/screenshots/{name}_{datetime.now().strftime('%H%M%S')}.png"
    vnc(f"capture {path}")
    log(f"Screenshot: {path}")


def check_api() -> bool:
    import requests
    try:
        r = requests.post(
            "http://localhost:18080/kabusapi/token",
            json={"APIPassword": API_PASSWORD}, timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def kill_kabu():
    subprocess.run("taskkill /f /im KabuS.exe", shell=True,
                   capture_output=True, encoding="utf-8")
    time.sleep(5)
    log("kabuStation killed")


def start_kabu_via_vnc():
    """Start kabuStation using VNC keyboard shortcut Win+R -> path -> Enter."""
    # Press Win+R to open Run dialog
    vnc("key super_l-r")
    time.sleep(2)
    # Type kabuStation path
    # vncdotool type command sends each character
    vnc(f'type "{KABU_PATH}"')
    time.sleep(1)
    # Press Enter
    vnc("key enter")
    log("kabuStation start command sent via VNC")
    time.sleep(60)  # Wait for kabuStation to load


def login_via_vnc():
    """Type password into kabuStation login window via VNC."""
    vnc_screenshot("before_login")

    # kabuStation login window should have focus
    # Tab to password field (user ID is pre-filled)
    vnc("key tab")
    time.sleep(0.5)
    # Type password
    vnc(f'type "{API_PASSWORD}"')
    time.sleep(0.5)
    # Press Enter
    vnc("key enter")
    log("Password entered via VNC")
    time.sleep(15)

    vnc_screenshot("after_password")


def enter_2fa_code(code: str):
    """Enter 2FA code into kabuStation via VNC."""
    vnc(f'type "{code}"')
    time.sleep(0.5)
    vnc("key enter")
    log(f"2FA code entered: {code}")
    time.sleep(15)
    vnc_screenshot("after_2fa")


def main():
    log("=" * 50)
    log("kabuStation VNC Login")
    log("=" * 50)

    # Step 1: Already logged in?
    if check_api():
        log("API already OK. Done.")
        return True

    # Step 2: Kill and restart
    log("API not ready. Restarting kabuStation...")
    kill_kabu()
    start_kabu_via_vnc()

    # Step 3: Login
    login_via_vnc()

    # Step 4: Check if 2FA is needed
    if check_api():
        log("LOGIN SUCCESS (no 2FA needed)")
        return True

    log("API still 401. 2FA code likely needed.")
    vnc_screenshot("need_2fa")

    # Step 5: 2FA code must be provided externally
    # Check if a code file exists (written by Claude scheduled task)
    code_file = Path("C:/cits/data/2fa_code.txt")
    if code_file.exists():
        code = code_file.read_text(encoding="utf-8").strip()
        if len(code) == 6 and code.isdigit():
            log(f"Found 2FA code: {code}")
            enter_2fa_code(code)
            code_file.unlink()  # Delete after use

            if check_api():
                log("LOGIN SUCCESS (with 2FA)")
                return True

    # Step 6: Wait for code (polling)
    log("Waiting for 2FA code file at C:/cits/data/2fa_code.txt ...")
    for i in range(30):  # Wait up to 5 minutes
        time.sleep(10)
        if code_file.exists():
            code = code_file.read_text(encoding="utf-8").strip()
            if len(code) == 6 and code.isdigit():
                log(f"2FA code received: {code}")
                enter_2fa_code(code)
                code_file.unlink()
                if check_api():
                    log("LOGIN SUCCESS (with 2FA)")
                    return True
                break

    if check_api():
        log("LOGIN SUCCESS")
        return True

    log("FAILED: All methods exhausted")
    vnc_screenshot("failed")
    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
