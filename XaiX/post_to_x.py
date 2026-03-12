#!/usr/bin/env python3
"""
XaiX — X（Twitter）投稿スクリプト
生成した画像をXに投稿する
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import tweepy
from dotenv import load_dotenv

load_dotenv()


def get_twitter_client() -> tweepy.Client:
    """認証済みのTwitter APIクライアントを返す"""
    required_keys = [
        "TWITTER_API_KEY",
        "TWITTER_API_SECRET",
        "TWITTER_ACCESS_TOKEN",
        "TWITTER_ACCESS_TOKEN_SECRET",
        "TWITTER_BEARER_TOKEN",
    ]

    missing = [k for k in required_keys if not os.environ.get(k)]
    if missing:
        print(f"エラー: 以下の環境変数が設定されていません:")
        for k in missing:
            print(f"  {k}")
        sys.exit(1)

    client = tweepy.Client(
        bearer_token=os.environ["TWITTER_BEARER_TOKEN"],
        consumer_key=os.environ["TWITTER_API_KEY"],
        consumer_secret=os.environ["TWITTER_API_SECRET"],
        access_token=os.environ["TWITTER_ACCESS_TOKEN"],
        access_token_secret=os.environ["TWITTER_ACCESS_TOKEN_SECRET"],
    )
    return client


def get_twitter_api_v1() -> tweepy.API:
    """メディアアップロード用のv1 APIを返す"""
    auth = tweepy.OAuth1UserHandler(
        os.environ["TWITTER_API_KEY"],
        os.environ["TWITTER_API_SECRET"],
        os.environ["TWITTER_ACCESS_TOKEN"],
        os.environ["TWITTER_ACCESS_TOKEN_SECRET"],
    )
    return tweepy.API(auth)


def post_with_images(
    text: str,
    image_paths: list[str],
) -> str:
    """画像付きでXに投稿する"""
    client = get_twitter_client()
    api_v1 = get_twitter_api_v1()

    # 画像をアップロード（最大4枚）
    media_ids = []
    for path in image_paths[:4]:
        print(f"  アップロード中: {path}")
        media = api_v1.media_upload(filename=path)
        media_ids.append(media.media_id)

    # ツイート投稿
    response = client.create_tweet(text=text, media_ids=media_ids)
    tweet_id = response.data["id"]
    tweet_url = f"https://x.com/i/status/{tweet_id}"

    print(f"  投稿完了: {tweet_url}")
    return tweet_url


def main():
    parser = argparse.ArgumentParser(description="XaiX — X投稿スクリプト")
    parser.add_argument("--text", "-t", required=True, help="投稿テキスト")
    parser.add_argument("--images", "-i", nargs="+", required=True, help="画像ファイルパス（最大4枚）")
    args = parser.parse_args()

    # 画像ファイルの存在確認
    for path in args.images:
        if not Path(path).exists():
            print(f"エラー: ファイルが見つかりません: {path}")
            sys.exit(1)

    print(f"X投稿中...")
    print(f"  テキスト: {args.text[:50]}...")
    url = post_with_images(args.text, args.images)
    print(f"\n完了: {url}")


if __name__ == "__main__":
    main()
