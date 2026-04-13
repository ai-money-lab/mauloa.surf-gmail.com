# -*- coding: utf-8 -*-
"""kabuStation Auto-Login -- VPS内部完結版

Chrome MCP不要。ローカルPC不要。VPS上で全て完結。

方式:
1. TightVNC(localhost:5900) + vncdotool でkabuStation GUI操作
2. Gmail IMAP で2FAコード取得
3. kabuStation API でトークン確認

依存: vncdotool, imaplib(標準ライブラリ)
"""
import email
import imaplib
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ===== 設定 =====
LOG_DIR = Path("C:/cits/logs")
LOG_FILE = LOG_DIR / "kabu_auto_login.log"
SCREENSHOT_DIR = LOG_DIR / "screenshots"

KABU_EXE = r"C:\Users\Administrator\AppData\Local\kabuStation\KabuS.exe"
API_URL = "http://localhost:18080/kabusapi/token"
API_PASSWORD = os.environ.get("KABU_API_PASSWORD", "hiroki0380")

VNC_HOST = "localhost"
VNC_PORT = 5900
VNC_PASSWORD = os.environ.get("CITS_VNC_PASSWORD", "cits2026")
VNCDO = r"C:\cits\venv\Scripts\vncdo.exe"

# Gmail IMAP設定
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

# kabuStationログイン画面の座標（VPS実座標 1024x768）
# noVNC描画領域(590,105)-(1589,752) = 999x647 → VPS 1024x768 にマップ
# 変換式: VPS_X = (noVNC_X - 590) / 999 * 1024, VPS_Y = (noVNC_Y - 105) / 647 * 768
LOGIN_BTN = (779, 475)      # ログインボタン
TWO_FA_INPUT = (769, 455)   # 2FAコード入力フィールド
TWO_FA_SUBMIT = (769, 530)  # 続けるボタン
# スタートメニュー経由の起動座標（タスクバー: VPS Y=748付近）
TASKBAR_START = (20, 750)   # スタートメニュー
TASKBAR_KABU = (449, 750)   # kabuStationタスクバーアイコン（前面化用）

MAX_RETRIES = 2


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
    """kabuStation APIが応答するか確認"""
    try:
        import requests
        r = requests.post(API_URL, json={"APIPassword": API_PASSWORD}, timeout=5)
        if r.status_code == 200:
            log(f"API OK: token={r.json().get('Token','')[:16]}...")
            return True
        log(f"API {r.status_code}: {r.text[:100]}")
        return False
    except Exception as e:
        log(f"API unreachable: {e}")
        return False


def vnc_cmd(cmd: str, timeout: int = 15) -> bool:
    """vncdotoolコマンド実行"""
    full = f'"{VNCDO}" -s {VNC_HOST}::{VNC_PORT} -p {VNC_PASSWORD} {cmd}'
    try:
        result = subprocess.run(
            full, shell=True, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout
        )
        if result.returncode != 0:
            err = (result.stderr or "")[:200]
            log(f"VNC FAIL: {cmd} -> {err}")
            return False
        return True
    except Exception as e:
        log(f"VNC ERROR: {cmd} -> {e}")
        return False


def vnc_click(x: int, y: int) -> bool:
    return vnc_cmd(f"move {x} {y} click 1")


def vnc_type(text: str) -> bool:
    return vnc_cmd(f'type "{text}"')


def vnc_screenshot(name: str) -> bool:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    path = SCREENSHOT_DIR / f"{name}_{ts}.png"
    return vnc_cmd(f"capture {path}")


def kill_kabu():
    """kabuStationプロセスを強制終了"""
    subprocess.run(
        "taskkill /f /im KabuS.exe",
        shell=True, capture_output=True, encoding="utf-8", errors="replace"
    )
    time.sleep(5)
    log("kabuStation killed")


def _kabu_running() -> bool:
    """KabuS.exeがプロセス一覧にあるか確認"""
    r = subprocess.run(
        'tasklist /fi "IMAGENAME eq KabuS.exe" /fo csv /nh',
        shell=True, capture_output=True, text=True,
        encoding="cp932", errors="replace", timeout=5,
    )
    return "KabuS" in (r.stdout or "")


def start_kabu():
    """kabuStationをGUIセッションで起動。
    まず schtasks /IT タスクを試み、起動確認できなければ
    VNC Win+R ダイアログ経由で直接起動する。
    """
    # すでに起動済みならスキップ
    if _kabu_running():
        log("kabuStation already running — skipping start")
        return

    # Method 1: /IT付きタスクスケジューラ
    r = subprocess.run(
        'schtasks /Run /TN "CITS_KabuStart_IT"',
        shell=True, capture_output=True, encoding="cp932", errors="replace", timeout=10,
    )
    log(f"CITS_KabuStart_IT rc={r.returncode} {(r.stdout or '').strip()[:60]}")
    time.sleep(30)  # 起動待ち

    if _kabu_running():
        log("kabuStation process confirmed (schtasks method)")
        return

    log("WARNING: schtasks method failed. Trying VNC Win+R launch...")

    # Method 2: VNC Win+R でKabuS.exeを直接起動
    vnc_cmd("key super-r", timeout=10)
    time.sleep(2)
    vnc_cmd(f'type "{KABU_EXE}"', timeout=15)
    time.sleep(1)
    vnc_cmd("key Return", timeout=10)
    log("VNC Win+R launch sent. Waiting 45s...")
    time.sleep(45)

    if _kabu_running():
        log("kabuStation process confirmed (VNC Win+R method)")
    else:
        log("WARNING: kabuStation process not found after both methods")


def get_2fa_from_gmail(max_wait_sec: int = 180, not_before: datetime | None = None) -> str:
    """Gmail IMAPから2FAコード取得。最大max_wait_sec秒待機。

    Args:
        max_wait_sec: 最大待機秒数
        not_before: この時刻より前に届いたメールは無視する（ログイン操作直前の時刻）
    """
    if not GMAIL_APP_PASSWORD:
        log("ERROR: GMAIL_APP_PASSWORD not set")
        return ""

    if not_before is None:
        # デフォルト: 呼び出し直前の2分前以降のメールを対象
        not_before = datetime.now() - timedelta(minutes=2)

    start_time = datetime.now()
    # IMAP SINCEは日付単位なのでtoday(UTC)で絞り込み
    search_after = datetime.utcnow().strftime("%d-%b-%Y")

    log(f"2FA search: emails after {not_before.strftime('%H:%M:%S')} (max {max_wait_sec}s)")

    while (datetime.now() - start_time).total_seconds() < max_wait_sec:
        try:
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)
            mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            mail.select("INBOX")

            # 本日のkabuStationメールを全て取得（既読・未読問わず）
            _, msg_nums = mail.search(
                None,
                f'(FROM "no-reply@mail.kabu.com" SINCE "{search_after}")'
            )

            if msg_nums[0]:
                # 全候補を新しい順に確認（最大5件）
                candidates = msg_nums[0].split()[-5:]
                for uid in reversed(candidates):
                    _, msg_data = mail.fetch(uid, "(RFC822)")
                    if not msg_data or not msg_data[0]:
                        continue
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)

                    # メール日時チェック: not_before より後か
                    try:
                        mail_date = email.utils.parsedate_to_datetime(msg["Date"])
                        import calendar
                        mail_utc = mail_date.utctimetuple()
                        mail_local_approx = datetime.utcfromtimestamp(calendar.timegm(mail_utc))
                        age_minutes = (datetime.utcnow() - mail_local_approx).total_seconds() / 60
                    except Exception:
                        age_minutes = 999

                    if age_minutes > 10:
                        log(f"2FA code too old (age={age_minutes:.1f}min), skipping")
                        continue

                    # 本文からコード抽出
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                                break
                            elif part.get_content_type() == "text/html":
                                body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    else:
                        body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

                    match = re.search(r"認証コード\s*[\u200B]*\s*(\d{6})", body)
                    if match:
                        code = match.group(1)
                        log(f"2FA code found: {code} (age: {age_minutes:.1f}min)")
                        mail.logout()
                        return code

            mail.logout()
        except Exception as e:
            log(f"IMAP error: {e}")

        log("Waiting for 2FA email... (10s)")
        time.sleep(10)

    log("ERROR: 2FA code not received within timeout")
    return ""


def login_flow() -> bool:
    """kabuStationログインの全フロー"""

    # Step 1: API確認
    if check_api():
        log("Already logged in. Done.")
        return True

    # Step 2: Kill & Restart
    log("API not ready. Restarting kabuStation...")
    kill_kabu()
    start_kabu()

    # Step 3: kabuStationウィンドウを前面に出す（MT5等が前面の可能性）
    log("Bringing kabuStation to front via taskbar click...")
    vnc_click(*TASKBAR_KABU)
    time.sleep(3)
    vnc_screenshot("before_login")

    # Step 4: ログインボタンクリック（パスワードは保持済み）
    log("Clicking login button...")
    login_clicked_at = datetime.now()  # 2FA email はこの後に届く
    vnc_click(*LOGIN_BTN)
    time.sleep(15)

    # Step 5: API確認（2FA不要でログインできた場合）
    if check_api():
        log("LOGIN SUCCESS (no 2FA needed)")
        return True

    vnc_screenshot("need_2fa")

    # Step 6: 2FAコード取得（Gmail IMAP）
    # login_clicked_at より後に届いたメールのみ有効とする
    log("2FA required. Fetching code from Gmail IMAP...")
    code = get_2fa_from_gmail(max_wait_sec=120, not_before=login_clicked_at)
    if not code:
        log("FAILED: Could not get 2FA code")
        return False

    # Step 7: 2FAコード入力
    log(f"Entering 2FA code: {code}")
    vnc_click(*TWO_FA_INPUT)
    time.sleep(1)
    vnc_type(code)
    time.sleep(1)
    vnc_click(*TWO_FA_SUBMIT)
    time.sleep(15)

    vnc_screenshot("after_2fa")

    # Step 8: API確認
    if check_api():
        log("LOGIN SUCCESS (with 2FA)")
        return True

    log("FAILED: API still not ready after 2FA")
    return False


def main():
    log("=" * 60)
    log("kabuStation Auto-Login (VPS Internal)")
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
    vnc_screenshot("final_fail")
    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
