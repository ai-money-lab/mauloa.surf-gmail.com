"""X API 接続テスト

実際にXに投稿してAPI接続を確認する。
テスト後は手動でツイートを削除してください。

Usage:
    python system_a/test_post.py              # 単一ツイートテスト
    python system_a/test_post.py --thread     # スレッドテスト
    python system_a/test_post.py --dry-run    # 投稿せずに接続確認のみ
"""

import argparse
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# プロジェクトルートをパスに追加
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(override=True)

from system_a.x_poster import XPoster

JST = timezone(timedelta(hours=9))


def test_connection():
    """X API接続テスト（投稿なし）"""
    print("=== X API Connection Test ===")
    try:
        poster = XPoster()
        print("[OK] XPoster initialized successfully")
        print(f"     Client: {type(poster.client).__name__}")

        # 認証テスト: 自分のユーザー情報を取得
        me = poster.client.get_me()
        if me and me.data:
            print(f"[OK] Authenticated as: @{me.data.username} ({me.data.name})")
            print(f"     User ID: {me.data.id}")
            return True
        else:
            print("[NG] Authentication failed: could not get user info")
            return False
    except Exception as e:
        print(f"[NG] Connection failed: {e}")
        return False


def test_single_post():
    """単一ツイートの投稿テスト"""
    print("\n=== Single Tweet Test ===")
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    poster = XPoster()
    test_text = (
        f"System A test ({now})\n\n"
        f"Auto-analysis pipeline connection test.\n"
        f"This tweet will be manually deleted shortly."
    )

    print(f"Posting: {test_text[:80]}...")
    tweet_id = poster.post_single(test_text)

    if tweet_id:
        print(f"[OK] Single tweet posted: {tweet_id}")
        print(f"     URL: https://x.com/i/status/{tweet_id}")
        print(f"     NOTE: Delete this tweet manually after confirming")
        return True
    else:
        print("[NG] Single tweet failed")
        return False


def test_thread_post():
    """スレッド投稿テスト"""
    print("\n=== Thread Test ===")
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    poster = XPoster()
    thread_texts = [
        f"System A thread test 1/3 ({now})\n\n"
        f"Auto-analysis pipeline thread posting test.",
        f"Thread test 2/3\n\n"
        f"Thread-style posting for step-by-step analysis results.",
        f"Thread test 3/3\n\n"
        f"Thread posting connection test complete. Delete manually.",
    ]

    print(f"Posting thread ({len(thread_texts)} tweets)...")
    tweet_ids = poster.post_thread(thread_texts)

    if tweet_ids:
        print(f"[OK] Thread posted: {len(tweet_ids)} tweets")
        for i, tid in enumerate(tweet_ids):
            print(f"     [{i + 1}] https://x.com/i/status/{tid}")
        print(f"     NOTE: Delete this thread manually after confirming")
        return True
    else:
        print("[NG] Thread post failed")
        return False


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="X API connection test")
    parser.add_argument("--thread", action="store_true", help="Test thread posting")
    parser.add_argument(
        "--dry-run", action="store_true", help="Connection check only (no posting)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("X API Connection & Posting Test")
    print("=" * 60)

    # 接続テスト
    connected = test_connection()
    if not connected:
        print("\n[NG] Connection failed. Check your .env credentials.")
        sys.exit(1)

    if args.dry_run:
        print("\n[OK] Dry-run complete. Connection is working.")
        return

    # 投稿テスト
    if args.thread:
        success = test_thread_post()
    else:
        success = test_single_post()

    print("\n" + "=" * 60)
    if success:
        print("[OK] All tests passed!")
    else:
        print("[NG] Test failed. Check logs above.")
    print("=" * 60)


if __name__ == "__main__":
    main()
