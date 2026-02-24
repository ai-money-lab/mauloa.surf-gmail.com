#!/usr/bin/env python3
"""GitHub Secretsを自動設定するスクリプト

使い方:
  # 環境変数で渡す
  GITHUB_TOKEN=ghp_xxx ANTHROPIC_API_KEY=sk-ant-xxx python scripts/set_github_secret.py

  # 対話的に入力
  python scripts/set_github_secret.py
"""

import base64
import json
import os
import sys
import urllib.request

from nacl import encoding, public

REPO_OWNER = "ai-money-lab"
REPO_NAME = "mauloa.surf-gmail.com"
API_BASE = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"


def encrypt_secret(public_key: str, secret_value: str) -> str:
    """GitHub公開鍵でシークレットを暗号化する"""
    pk = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed = public.SealedBox(pk).encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(sealed).decode("utf-8")


def github_api(path: str, token: str, method: str = "GET", data: dict | None = None):
    """GitHub API呼び出し"""
    url = f"{API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def set_secret(token: str, secret_name: str, secret_value: str):
    """GitHub Secretを設定する"""
    # 1. リポジトリの公開鍵を取得
    key_data = github_api("/actions/secrets/public-key", token)
    key_id = key_data["key_id"]
    public_key = key_data["key"]

    # 2. 暗号化
    encrypted = encrypt_secret(public_key, secret_value)

    # 3. Secret登録
    github_api(
        f"/actions/secrets/{secret_name}",
        token,
        method="PUT",
        data={"encrypted_value": encrypted, "key_id": key_id},
    )
    print(f"  {secret_name} -> 設定完了")


def get_input(prompt: str, env_key: str) -> str:
    """環境変数 or 対話入力から値を取得"""
    value = os.environ.get(env_key, "")
    if value:
        print(f"  {env_key}: 環境変数から取得")
        return value
    value = input(f"  {prompt}: ").strip()
    if not value:
        print(f"エラー: {env_key}が必要です", file=sys.stderr)
        sys.exit(1)
    return value


def main():
    print(f"=== GitHub Secrets 自動設定 ({REPO_OWNER}/{REPO_NAME}) ===\n")

    # トークン取得
    print("[1/3] 認証情報")
    token = get_input("GitHub Personal Access Token (repo scope)", "GITHUB_TOKEN")

    # APIキー取得
    print("\n[2/3] シークレット値")
    api_key = get_input("Anthropic API Key", "ANTHROPIC_API_KEY")

    # 設定実行
    print("\n[3/3] GitHub Secretsに登録中...")
    set_secret(token, "ANTHROPIC_API_KEY", api_key)

    print(f"\n完了! 全ワークフローで ANTHROPIC_API_KEY が利用可能です")


if __name__ == "__main__":
    main()
