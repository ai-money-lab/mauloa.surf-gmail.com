"""
NEXUS 共通基盤 — 全エンジンが使うユーティリティ

提供:
- APIクライアント共有（シングルトン）
- リトライ付きAPI呼び出し（レートリミット対応）
- 堅牢なJSONパーサー
- 共通設定（モデル名、タイムアウト等）
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from anthropic import Anthropic, APIError, RateLimitError, APITimeoutError

logger = logging.getLogger("nexus.common")

# ─── 設定 ───

DEFAULT_MODEL = os.getenv("NEXUS_MODEL", "claude-sonnet-4-20250514")
DEFAULT_TIMEOUT = int(os.getenv("NEXUS_TIMEOUT", "120"))
MAX_RETRIES = int(os.getenv("NEXUS_MAX_RETRIES", "3"))


# ─── シングルトン Anthropic クライアント ───

_client: Anthropic | None = None


def get_client() -> Anthropic:
    """共有Anthropicクライアントを取得する（シングルトン）"""
    global _client
    if _client is None:
        _client = Anthropic(timeout=DEFAULT_TIMEOUT)
    return _client


def reset_client() -> None:
    """テスト等でクライアントをリセットする"""
    global _client
    _client = None


# ─── リトライ付きAPI呼び出し ───


def call_api(
    *,
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int = 4096,
    model: str = "",
    temperature: float | None = None,
    max_retries: int = MAX_RETRIES,
) -> str:
    """Claude APIをリトライ付きで呼び出し、テキストを返す。

    レートリミット・タイムアウト・サーバーエラー時に
    エクスポネンシャルバックオフでリトライする。
    """
    client = get_client()
    used_model = model or DEFAULT_MODEL

    kwargs: dict[str, Any] = {
        "model": used_model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature

    if max_retries < 1:
        max_retries = 1
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = client.messages.create(**kwargs)
            return response.content[0].text
        except RateLimitError as e:
            wait = 2 ** attempt
            logger.warning("Rate limited (attempt %d/%d). Waiting %ds...", attempt + 1, max_retries, wait)
            time.sleep(wait)
            last_error = e
        except APITimeoutError as e:
            wait = 2 ** attempt
            logger.warning("API timeout (attempt %d/%d). Waiting %ds...", attempt + 1, max_retries, wait)
            time.sleep(wait)
            last_error = e
        except APIError as e:
            if e.status_code and e.status_code >= 500:
                wait = 2 ** attempt
                logger.warning("Server error %s (attempt %d/%d). Waiting %ds...", e.status_code, attempt + 1, max_retries, wait)
                time.sleep(wait)
                last_error = e
            else:
                raise

    raise last_error  # type: ignore[misc]


# ─── 堅牢なJSONパーサー ───


def parse_json(text: str, default: dict | None = None) -> dict[str, Any]:
    """テキストからJSONを安全に抽出する。

    1. まずテキスト全体をパース
    2. 失敗したら ```json ... ``` ブロックを探す
    3. 失敗したら最外側の { ... } を抽出
    4. すべて失敗したらdefaultを返す
    """
    if default is None:
        default = {}

    text = text.strip()

    # 1. 全体パース
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. ```json ... ``` ブロック
    if "```" in text:
        try:
            start = text.index("```")
            # skip language identifier line
            first_newline = text.index("\n", start)
            end = text.index("```", first_newline)
            block = text[first_newline + 1:end].strip()
            result = json.loads(block)
            if isinstance(result, dict):
                return result
        except (ValueError, json.JSONDecodeError):
            pass

    # 3. 最外側 { ... } 抽出（ネスト対応）
    json_start = text.find("{")
    if json_start >= 0:
        depth = 0
        in_string = False
        escape_next = False
        for i in range(json_start, len(text)):
            ch = text[i]
            if escape_next:
                escape_next = False
                continue
            if ch == "\\":
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[json_start:i + 1])
                    except json.JSONDecodeError:
                        break

    logger.debug("JSON parse failed, returning default")
    return default


def parse_json_list(text: str, key: str, default: list | None = None) -> list[Any]:
    """テキストからJSON内の特定キーのリストを抽出する。"""
    if default is None:
        default = []
    parsed = parse_json(text)
    result = parsed.get(key, default)
    return result if isinstance(result, list) else default
