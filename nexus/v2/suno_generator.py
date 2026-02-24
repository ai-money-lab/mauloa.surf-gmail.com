"""
Suno音楽生成モジュール — AIML API経由

音楽仕様JSON（music_90s_rnb_piano.json等）を読み込み、
AIML APIのSuno AI v2エンドポイントで楽曲を自動生成する。

フロー:
1. 音楽仕様JSONからトラック情報を読み込む
2. 各トラックの suno_prompt → tags + lyrics生成
3. POST /v2/generate/audio/suno-ai/clip でクリップ生成
4. ポーリングで完了を待つ
5. 結果（audio_url等）をJSONに保存
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

logger = logging.getLogger("nexus.suno")

# ─── 設定 ───

AIMLAPI_KEY = os.getenv("AIMLAPI_KEY", "")
AIMLAPI_BASE = "https://api.aimlapi.com"

CLIP_GENERATE_URL = f"{AIMLAPI_BASE}/v2/generate/audio/suno-ai/clip"
CLIP_FETCH_URL = f"{AIMLAPI_BASE}/v2/generate/audio/suno-ai/clip"
LYRIC_GENERATE_URL = f"{AIMLAPI_BASE}/v2/generate/audio/suno-ai/lyric"

POLL_INTERVAL = 15          # 秒
POLL_MAX_ATTEMPTS = 80      # 最大20分待機
REQUEST_TIMEOUT = 30        # HTTPリクエストタイムアウト

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "v2"
CONTENT_DIR = DATA_DIR / "content"
GENERATION_DIR = DATA_DIR / "suno_generations"


@dataclass
class ClipResult:
    """Suno生成結果"""
    clip_id: str
    track_title: str
    album_name: str
    status: str = "queued"
    audio_url: str = ""
    tags: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "clip_id": self.clip_id,
            "track_title": self.track_title,
            "album_name": self.album_name,
            "status": self.status,
            "audio_url": self.audio_url,
            "tags": self.tags,
            "error": self.error,
        }


def _headers() -> dict[str, str]:
    key = AIMLAPI_KEY
    if not key:
        raise RuntimeError(
            "AIMLAPI_KEY が設定されていません。.env に AIMLAPI_KEY=your_key を追加してください。"
        )
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _extract_tags(track: dict) -> str:
    """トラック情報からSunoのtagsフィールド用文字列を生成する。

    suno_prompt全体をtagsにそのまま使う（Sunoはタグにスタイル記述を受け取れる）。
    """
    parts: list[str] = []

    # ジャンル
    if genre := track.get("genre"):
        parts.append(genre)

    # ムード
    if mood := track.get("mood"):
        parts.append(mood)

    # キー
    if key := track.get("key"):
        parts.append(f"key of {key}")

    # BPM
    if bpm := track.get("tempo_bpm"):
        parts.append(f"{bpm} BPM")

    # ボーカル指定（suno_promptから推定）
    prompt = track.get("suno_prompt", "")
    if "female vocal" in prompt.lower():
        parts.append("female vocals")
    elif "male vocal" in prompt.lower():
        parts.append("male vocals")

    # ピアノ種類
    for piano_type in ["Rhodes", "Wurlitzer", "Korg M1", "grand piano", "acoustic piano"]:
        if piano_type.lower() in prompt.lower():
            parts.append(piano_type)
            break

    return ", ".join(parts)


def generate_lyrics(prompt: str) -> dict:
    """AIML API経由でSunoの歌詞を自動生成する。

    Returns:
        {"title": str, "text": str} — 生成された歌詞
    """
    resp = requests.post(
        LYRIC_GENERATE_URL,
        headers=_headers(),
        json={"prompt": prompt},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def generate_clip(
    *,
    title: str,
    tags: str,
    prompt: str = "",
    gpt_description_prompt: str = "",
) -> list[str]:
    """Sunoクリップ生成をリクエストする。

    Args:
        title: 曲タイトル
        tags: スタイル/ジャンルキーワード
        prompt: 歌詞（カスタム生成時）
        gpt_description_prompt: 説明プロンプト（自動生成時）

    Returns:
        clip_idのリスト（通常2つ）
    """
    body: dict = {"title": title, "tags": tags}

    if prompt:
        body["prompt"] = prompt
    if gpt_description_prompt:
        body["gpt_description_prompt"] = gpt_description_prompt

    logger.info("Generating clip: %s (tags: %s)", title, tags[:60])

    resp = requests.post(
        CLIP_GENERATE_URL,
        headers=_headers(),
        json=body,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    clip_ids = data.get("clip_ids", [])
    if not clip_ids:
        raise RuntimeError(f"クリップIDが返されませんでした: {data}")

    logger.info("Clip IDs: %s", clip_ids)
    return clip_ids


def fetch_clip(clip_id: str) -> dict:
    """クリップのステータスと情報を取得する。"""
    resp = requests.get(
        CLIP_FETCH_URL,
        headers=_headers(),
        params={"clip_id": clip_id},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def wait_for_clip(clip_id: str) -> dict:
    """クリップ生成の完了をポーリングで待つ。"""
    for attempt in range(POLL_MAX_ATTEMPTS):
        data = fetch_clip(clip_id)

        status = data.get("status", "unknown")
        logger.info(
            "  [%d/%d] clip=%s status=%s",
            attempt + 1, POLL_MAX_ATTEMPTS, clip_id[:8], status,
        )

        if status == "complete":
            return data
        if status == "error":
            raise RuntimeError(f"クリップ生成エラー: {data}")

        time.sleep(POLL_INTERVAL)

    raise TimeoutError(f"クリップ生成タイムアウト ({POLL_MAX_ATTEMPTS * POLL_INTERVAL}秒): {clip_id}")


def load_music_spec(filename: str) -> dict:
    """音楽仕様JSONを読み込む。"""
    path = CONTENT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"音楽仕様が見つかりません: {path}")
    with open(path) as f:
        return json.load(f)


def save_generation_result(album_name: str, results: list[dict]) -> Path:
    """生成結果をJSONに保存する。"""
    GENERATION_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = album_name.lower().replace(" ", "_").replace("—", "").replace(":", "")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    path = GENERATION_DIR / f"suno_{safe_name}_{timestamp}.json"

    with open(path, "w") as f:
        json.dump({
            "album_name": album_name,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "total_clips": len(results),
            "clips": results,
        }, f, indent=2, ensure_ascii=False)

    logger.info("結果保存: %s", path)
    return path


def generate_album(
    spec_filename: str,
    *,
    use_lyrics_api: bool = True,
    wait: bool = True,
    dry_run: bool = False,
) -> list[ClipResult]:
    """アルバム仕様から全トラックを生成する。

    Args:
        spec_filename: 音楽仕様JSONのファイル名
        use_lyrics_api: Trueなら歌詞APIで歌詞を自動生成してから使う
        wait: Trueならクリップ完了までポーリングで待つ
        dry_run: Trueなら実際のAPI呼び出しをスキップ（デバッグ用）

    Returns:
        ClipResultのリスト
    """
    spec = load_music_spec(spec_filename)
    album_name = spec.get("album_name", "Unknown Album")
    tracks = spec.get("tracks", [])

    if not tracks:
        raise ValueError(f"トラックが見つかりません: {spec_filename}")

    logger.info("=== アルバム生成開始: %s (%d曲) ===", album_name, len(tracks))
    results: list[ClipResult] = []

    for i, track in enumerate(tracks):
        title = track.get("title", f"Track {i + 1}")
        suno_prompt = track.get("suno_prompt", "")
        tags = _extract_tags(track)

        logger.info("[%d/%d] %s", i + 1, len(tracks), title)

        if dry_run:
            result = ClipResult(
                clip_id=f"dry_run_{i}",
                track_title=title,
                album_name=album_name,
                status="dry_run",
                tags=tags,
            )
            results.append(result)
            logger.info("  (dry run) tags: %s", tags[:80])
            continue

        # 歌詞生成（オプション）
        lyrics = ""
        if use_lyrics_api:
            try:
                lyric_data = generate_lyrics(suno_prompt)
                lyrics = lyric_data.get("text", "")
                logger.info("  歌詞生成完了 (%d文字)", len(lyrics))
            except Exception as e:
                logger.warning("  歌詞生成失敗、説明プロンプトで続行: %s", e)

        # クリップ生成
        try:
            if lyrics:
                clip_ids = generate_clip(title=title, tags=tags, prompt=lyrics)
            else:
                clip_ids = generate_clip(
                    title=title,
                    tags=tags,
                    gpt_description_prompt=suno_prompt,
                )
        except Exception as e:
            logger.error("  クリップ生成失敗: %s", e)
            results.append(ClipResult(
                clip_id="",
                track_title=title,
                album_name=album_name,
                status="error",
                tags=tags,
                error=str(e),
            ))
            continue

        # 結果を記録（各リクエストで2クリップ生成される）
        for clip_id in clip_ids:
            result = ClipResult(
                clip_id=clip_id,
                track_title=title,
                album_name=album_name,
                status="submitted",
                tags=tags,
            )

            if wait:
                try:
                    clip_data = wait_for_clip(clip_id)
                    result.status = clip_data.get("status", "unknown")
                    result.audio_url = clip_data.get("audio_url", "")
                    logger.info("  完了: %s → %s", clip_id[:8], result.audio_url[:60] if result.audio_url else "(no url)")
                except Exception as e:
                    result.status = "error"
                    result.error = str(e)
                    logger.error("  ポーリング失敗: %s", e)

            results.append(result)

    # 結果保存
    save_generation_result(album_name, [r.to_dict() for r in results])

    complete_count = sum(1 for r in results if r.status == "complete")
    error_count = sum(1 for r in results if r.status == "error")
    logger.info(
        "=== 完了: %s — %d complete, %d error, %d total ===",
        album_name, complete_count, error_count, len(results),
    )

    return results


# ─── CLI ───

def main() -> None:
    """コマンドライン実行用"""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Suno音楽生成")
    parser.add_argument(
        "spec",
        help="音楽仕様JSONファイル名 (例: music_90s_rnb_piano.json)",
    )
    parser.add_argument(
        "--no-lyrics", action="store_true",
        help="歌詞APIを使わず、suno_promptを直接渡す",
    )
    parser.add_argument(
        "--no-wait", action="store_true",
        help="生成完了を待たない（クリップIDだけ取得）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="APIを呼ばずにパラメータだけ確認",
    )
    parser.add_argument(
        "--track", type=int, default=None,
        help="特定のトラック番号だけ生成 (0始まり)",
    )

    args = parser.parse_args()

    # 単一トラック指定の場合、仕様を絞り込む
    if args.track is not None:
        spec = load_music_spec(args.spec)
        tracks = spec.get("tracks", [])
        if args.track < 0 or args.track >= len(tracks):
            print(f"エラー: トラック番号 {args.track} は範囲外 (0-{len(tracks) - 1})")
            return
        spec["tracks"] = [tracks[args.track]]
        # 一時的に絞り込んだ仕様を書き出し
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", dir=CONTENT_DIR, delete=False,
        ) as tmp:
            json.dump(spec, tmp, ensure_ascii=False, indent=2)
            tmp_name = Path(tmp.name).name

        try:
            generate_album(
                tmp_name,
                use_lyrics_api=not args.no_lyrics,
                wait=not args.no_wait,
                dry_run=args.dry_run,
            )
        finally:
            (CONTENT_DIR / tmp_name).unlink(missing_ok=True)
    else:
        generate_album(
            args.spec,
            use_lyrics_api=not args.no_lyrics,
            wait=not args.no_wait,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
