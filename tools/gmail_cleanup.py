#!/usr/bin/env python3
"""Gmail クリーンアップツール

プロモーション・SNS通知メールを一括削除する。
OAuth 2.0 認証を使用し、個人Gmailアカウントに対応。

使い方:
  1. Google Cloud Console で OAuth 2.0 クライアントID を作成
     - アプリの種類: デスクトップアプリ
     - credentials.json をダウンロード
  2. credentials.json を config/gmail_credentials.json に配置
  3. python tools/gmail_cleanup.py を実行
     - 初回はブラウザで認証を求められる
     - トークンは config/gmail_token.json に保存される
"""

import argparse
import sys
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Gmail APIのスコープ（メール変更権限）
SCOPES = ["https://mail.google.com/"]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / "config" / "gmail_credentials.json"
TOKEN_PATH = PROJECT_ROOT / "config" / "gmail_token.json"

# Gmail検索クエリ: プロモーションとSNS通知
CATEGORY_QUERIES = {
    "promotions": "category:promotions",
    "social": "category:social",
}


def authenticate() -> Credentials:
    """OAuth 2.0 認証を行い、credentialsを返す"""
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("トークンを更新中...")
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                print(f"エラー: {CREDENTIALS_PATH} が見つかりません。")
                print("Google Cloud Console で OAuth クライアントID を作成し、")
                print(f"ダウンロードした credentials.json を {CREDENTIALS_PATH} に配置してください。")
                sys.exit(1)

            print("ブラウザで Google 認証を行ってください...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())
        print("認証トークンを保存しました。")

    return creds


def get_message_ids(service, query: str, max_results: int = 500) -> list[str]:
    """検索クエリに一致するメッセージIDのリストを取得"""
    message_ids = []
    page_token = None

    while len(message_ids) < max_results:
        result = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=min(500, max_results - len(message_ids)),
                pageToken=page_token,
            )
            .execute()
        )

        messages = result.get("messages", [])
        if not messages:
            break

        message_ids.extend(msg["id"] for msg in messages)
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return message_ids


def batch_delete(service, message_ids: list[str]) -> int:
    """メッセージをバッチ削除（ゴミ箱へ移動）"""
    deleted = 0
    batch_size = 1000  # Gmail API の上限

    for i in range(0, len(message_ids), batch_size):
        batch = message_ids[i : i + batch_size]
        service.users().messages().batchModify(
            userId="me",
            body={"ids": batch, "addLabelIds": ["TRASH"]},
        ).execute()
        deleted += len(batch)
        print(f"  {deleted}/{len(message_ids)} 件をゴミ箱へ移動...")

        # レートリミット対策
        if i + batch_size < len(message_ids):
            time.sleep(1)

    return deleted


def batch_permanent_delete(service, message_ids: list[str]) -> int:
    """メッセージを完全削除（復元不可）"""
    deleted = 0
    batch_size = 1000

    for i in range(0, len(message_ids), batch_size):
        batch = message_ids[i : i + batch_size]
        service.users().messages().batchDelete(
            userId="me",
            body={"ids": batch},
        ).execute()
        deleted += len(batch)
        print(f"  {deleted}/{len(message_ids)} 件を完全削除...")

        if i + batch_size < len(message_ids):
            time.sleep(1)

    return deleted


def main():
    parser = argparse.ArgumentParser(description="Gmail プロモーション・SNS通知メール削除ツール")
    parser.add_argument(
        "--category",
        choices=["promotions", "social", "all"],
        default="all",
        help="削除対象カテゴリ (default: all)",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="カスタム検索クエリ (例: 'older_than:6m category:promotions')",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=5000,
        help="最大削除件数 (default: 5000)",
    )
    parser.add_argument(
        "--permanent",
        action="store_true",
        help="完全削除（ゴミ箱を経由せず復元不可）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際には削除せず件数のみ表示",
    )
    args = parser.parse_args()

    # 認証
    creds = authenticate()
    service = build("gmail", "v1", credentials=creds)

    # 検索クエリの決定
    if args.query:
        queries = {"custom": args.query}
    elif args.category == "all":
        queries = CATEGORY_QUERIES
    else:
        queries = {args.category: CATEGORY_QUERIES[args.category]}

    total_deleted = 0

    for name, query in queries.items():
        print(f"\n--- {name} ---")
        print(f"検索クエリ: {query}")

        message_ids = get_message_ids(service, query, max_results=args.max)
        print(f"対象メール: {len(message_ids)} 件")

        if not message_ids:
            print("削除対象なし。スキップ。")
            continue

        if args.dry_run:
            print("(dry-run: 削除はスキップ)")
            continue

        if args.permanent:
            count = batch_permanent_delete(service, message_ids)
            print(f"完全削除完了: {count} 件")
        else:
            count = batch_delete(service, message_ids)
            print(f"ゴミ箱へ移動完了: {count} 件")

        total_deleted += count

    print(f"\n合計: {total_deleted} 件処理しました。")


if __name__ == "__main__":
    main()
