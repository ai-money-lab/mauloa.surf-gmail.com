"""LINE Messaging API 接続テスト.

使い方:
  python scripts/test_line_connection.py
"""

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()


def test_connection():
    """LINE Messaging API の接続テスト."""
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    secret = os.getenv("LINE_CHANNEL_SECRET", "")
    user_id = os.getenv("LINE_USER_ID", "")

    print("=" * 50)
    print("LINE Messaging API 接続テスト")
    print("=" * 50)

    # 1. 環境変数チェック
    print("\n[1] 環境変数チェック")
    checks = {
        "LINE_CHANNEL_SECRET": bool(secret),
        "LINE_CHANNEL_ACCESS_TOKEN": bool(token),
        "LINE_USER_ID": bool(user_id),
    }
    all_ok = True
    for key, ok in checks.items():
        status = "OK" if ok else "MISSING"
        print(f"  {key}: {status}")
        if not ok:
            all_ok = False

    if not token:
        print("\nERROR: LINE_CHANNEL_ACCESS_TOKEN が未設定です")
        return False

    # 2. Bot情報取得テスト
    print("\n[2] Bot情報取得テスト")
    try:
        resp = requests.get(
            "https://api.line.me/v2/bot/info",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            info = resp.json()
            print(f"  Bot名: {info.get('displayName', 'N/A')}")
            print(f"  Bot ID: {info.get('userId', 'N/A')}")
            print(f"  状態: OK")
        else:
            print(f"  ERROR: HTTP {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    # 3. プッシュメッセージ送信テスト
    if user_id:
        print("\n[3] プッシュメッセージ送信テスト")
        try:
            resp = requests.post(
                "https://api.line.me/v2/bot/message/push",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "to": user_id,
                    "messages": [
                        {
                            "type": "text",
                            "text": "HIROKI AI Empire — LINE接続テスト成功!\n\nBot連携が正常に動作しています。",
                        }
                    ],
                },
                timeout=10,
            )
            if resp.status_code == 200:
                print("  メッセージ送信: OK")
                print("  → LINEアプリを確認してください")
            else:
                print(f"  ERROR: HTTP {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            print(f"  ERROR: {e}")
            return False
    else:
        print("\n[3] プッシュメッセージ: SKIP (LINE_USER_ID未設定)")

    print("\n" + "=" * 50)
    print("全テスト完了!")
    print("=" * 50)
    return True


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
