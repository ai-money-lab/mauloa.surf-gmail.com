"""UTF-16 BOM付き .env ファイルにも対応した dotenv ローダー."""
from __future__ import annotations

import io
import os

from dotenv import load_dotenv

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def safe_load_dotenv(env_path: str | None = None) -> None:
    """BOMを検出し、UTF-16の場合はStringIO経由でload_dotenvに渡す."""
    if env_path is None:
        env_path = os.path.join(_ROOT, ".env")
    if not os.path.isfile(env_path):
        load_dotenv()
        return
    with open(env_path, "rb") as f:
        bom = f.read(2)
    if bom in (b"\xff\xfe", b"\xfe\xff"):
        with open(env_path, "r", encoding="utf-16") as f:
            text = f.read()
        load_dotenv(stream=io.StringIO(text))
    else:
        load_dotenv(env_path)
