# -*- coding: utf-8 -*-
"""kabuStation Auto-Login v2 -- VPS内部完結（pyautogui + IMAP）

pyautoguiでGUI操作（座標変換不要）、Gmail IMAPで2FA取得。
ローカルPC不要。VPS上で全て完結。

前提:
- kabuStationはパスワード保持済み（口座番号02210320）
- TightVNCでコンソールセッション維持
- Gmail IMAPアプリパスワード設定済み
"""
import email
import imaplib
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ===== 設定 =====
LOG_DIR = Path("C:/cits/logs")
LOG_FILE = LOG_DIR / "kabu_auto_login.log"

API_URL = "http://localhost:18080/kabusapi/token"
API_PASSWORD = "hiroki0380"

GMAIL_USER = "mauloa.surf@gmail.com"
IMAP_SERVER = "imap.gmail.com"

# .envから読み込み
_env_path = Path("C:/cits/repo/cits/.env")
GMAIL_APP_PASSWORD = ""
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("GMAIL_APP_PASSWORD="):
            GMAIL_APP_PASSWORD = line.split("=", 1)[1].strip()
if not GMAIL_APP_PASSWORD:
    GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

MAX_RETRIES = 3


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} {msg}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode("ascii", errors="replace").decode(), flush=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def check_api() -> bool:
    try:
        import requests
        r = requests.post(API_URL, json={"APIPassword": API_PASSWORD}, timeout=5)
        if r.status_code == 200:
            log(f"API OK: token={r.json().get('Token','')[:16]}...")
            return True
        log(f"API {r.status_code}: {r.text[:100]}")
        return False
    except Exception as e:
        log(f"API unreachable: {type(e).__name__}")
        return False


def kill_kabu():
    subprocess.run("taskkill /f /im KabuS.exe", shell=True,
                   capture_output=True, encoding="utf-8", errors="replace")
    time.sleep(5)
    log("kabuStation killed")


def start_kabu():
    """kabuStationを/IT付きタスクスケジューラで起動"""
    subprocess.run(
        'schtasks /Run /TN "CITS_KabuStart_IT"',
        shell=True, capture_output=True, encoding="utf-8", errors="replace"
    )
    log("kabuStation start via IT task")
    time.sleep(30)
    # プロセス確認
    r = subprocess.run("tasklist | findstr KabuS", shell=True,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if "KabuS" in (r.stdout or ""):
        log("kabuStation process confirmed")
        return True
    log("WARNING: kabuStation process not found")
    return False


def find_and_click_button(button_text: str, timeout: int = 10) -> bool:
    """pyautoguiで画面上のボタンを画像認識でクリック（フォールバック: 座標クリック）"""
    try:
        import pyautogui
        pyautogui.FAILSAFE = False

        # 画像認識ではなく、locateOnScreenが使えない環境なので座標方式
        # kabuStationのログインウィンドウは画面中央右に表示される
        # 1024x768解像度
        screen_w, screen_h = pyautogui.size()
        log(f"Screen: {screen_w}x{screen_h}")

        if button_text == "login":
            # ログインボタン: 画面右半分の中央下
            x, y = int(screen_w * 0.69), int(screen_h * 0.62)
            log(f"Clicking login at ({x}, {y})")
            pyautogui.click(x, y)
            return True
        elif button_text == "2fa_input":
            # 2FAコード入力フィールド
            x, y = int(screen_w * 0.69), int(screen_h * 0.57)
            log(f"Clicking 2FA input at ({x}, {y})")
            pyautogui.click(x, y)
            return True
        elif button_text == "2fa_submit":
            # 続けるボタン
            x, y = int(screen_w * 0.69), int(screen_h * 0.70)
            log(f"Clicking 2FA submit at ({x}, {y})")
            pyautogui.click(x, y)
            return True
        elif button_text == "taskbar_kabu":
            # タスクバーのkabuStationアイコン（前面化）
            x, y = int(screen_w * 0.44), int(screen_h * 0.98)
            log(f"Clicking taskbar at ({x}, {y})")
            pyautogui.click(x, y)
            return True
    except Exception as e:
        log(f"pyautogui error: {e}")
        return False


def type_text(text: str) -> bool:
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        pyautogui.typewrite(text, interval=0.05)
        return True
    except Exception as e:
        log(f"type error: {e}")
        return False


def get_2fa_from_gmail(max_wait_sec: int = 120) -> str:
    if not GMAIL_APP_PASSWORD:
        log("ERROR: GMAIL_APP_PASSWORD not set")
        return ""

    start_time = datetime.now()
    now_utc = datetime.now(timezone.utc)
    search_after = (now_utc - timedelta(minutes=5)).strftime("%d-%b-%Y")

    while (datetime.now() - start_time).total_seconds() < max_wait_sec:
        try:
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)
            mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            mail.select("INBOX")

            _, msg_nums = mail.search(
                None, f'(FROM "no-reply@mail.kabu.com" SINCE "{search_after}")'
            )

            if msg_nums[0]:
                latest = msg_nums[0].split()[-1]
                _, msg_data = mail.fetch(latest, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        ct = part.get_content_type()
                        if ct in ("text/plain", "text/html"):
                            body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                            break
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

                match = re.search(r"認証コード\s*[\u200B]*\s*(\d{6})", body)
                if match:
                    code = match.group(1)
                    mail_date = email.utils.parsedate_to_datetime(msg["Date"])
                    age = (datetime.now(timezone.utc) - mail_date).total_seconds() / 60
                    if age < 5:
                        log(f"2FA code: {code} (age: {age:.1f}min)")
                        mail.logout()
                        return code
                    else:
                        log(f"2FA code too old: {code} ({age:.1f}min)")

            mail.logout()
        except Exception as e:
            log(f"IMAP error: {e}")

        log("Waiting for 2FA... (10s)")
        time.sleep(10)

    log("ERROR: 2FA timeout")
    return ""


def login_flow() -> bool:
    # Step 1: API check
    if check_api():
        log("Already logged in.")
        return True

    # Step 2: Kill & Restart
    log("Restarting kabuStation...")
    kill_kabu()
    if not start_kabu():
        log("kabuStation failed to start")
        return False

    # Step 3: 自分のcmdウィンドウを最小化してkabuStationを前面に出す
    log("Minimizing own window and bringing kabuStation to front...")
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
            time.sleep(1)
    except Exception:
        pass
    find_and_click_button("taskbar_kabu")
    time.sleep(3)

    # Step 4: Click login
    log("Clicking login...")
    find_and_click_button("login")
    time.sleep(15)

    # Step 5: Check API (maybe no 2FA needed)
    if check_api():
        log("LOGIN SUCCESS (no 2FA)")
        return True

    # Step 6: Get 2FA
    log("2FA required. Fetching from Gmail...")
    code = get_2fa_from_gmail(max_wait_sec=120)
    if not code:
        return False

    # Step 7: Enter 2FA
    log(f"Entering 2FA: {code}")
    find_and_click_button("2fa_input")
    time.sleep(1)
    type_text(code)
    time.sleep(1)
    find_and_click_button("2fa_submit")
    time.sleep(15)

    # Step 8: Verify
    if check_api():
        log("LOGIN SUCCESS (with 2FA)")
        return True

    log("FAILED: API not ready after 2FA")
    return False


def main():
    log("=" * 60)
    log("kabuStation Auto-Login v2 (pyautogui + IMAP)")
    log(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)

    for attempt in range(1, MAX_RETRIES + 1):
        log(f"Attempt {attempt}/{MAX_RETRIES}")
        if login_flow():
            log("SUCCESS")
            return True
        log(f"Attempt {attempt} failed")
        time.sleep(10)

    log("ALL ATTEMPTS FAILED")
    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
