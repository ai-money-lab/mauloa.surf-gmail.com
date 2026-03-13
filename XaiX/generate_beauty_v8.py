#!/usr/bin/env python3
"""
XaiX — AI美女画像生成パイプライン v8
fal.ai FLUX LoRA Realism を使ったフォトリアル画像生成
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import fal_client
import yaml
from dotenv import load_dotenv

# .envを読み込み
load_dotenv()

# デフォルト出力先
DEFAULT_OUTPUT_DIR = os.path.expanduser("~/Pictures/AILAB")
SCENES_DIR = Path(__file__).parent / "scenes"
ENGINES_DIR = Path(__file__).parent / "engines"


def load_yaml(path: Path) -> dict:
    """YAMLファイルを読み込む"""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_scene(scene_name: str) -> dict:
    """シーン設定を読み込む"""
    scene_path = SCENES_DIR / f"{scene_name}.yaml"
    if not scene_path.exists():
        # シーン一覧を表示
        available = [f.stem for f in SCENES_DIR.glob("*.yaml")]
        print(f"エラー: シーン '{scene_name}' が見つかりません")
        print(f"利用可能なシーン: {', '.join(available)}")
        sys.exit(1)
    return load_yaml(scene_path)


def load_engine(engine_name: str) -> dict:
    """エンジン設定を読み込む"""
    engine_path = ENGINES_DIR / f"{engine_name}.yaml"
    if not engine_path.exists():
        available = [f.stem for f in ENGINES_DIR.glob("*.yaml")]
        print(f"エラー: エンジン '{engine_name}' が見つかりません")
        print(f"利用可能なエンジン: {', '.join(available)}")
        sys.exit(1)
    return load_yaml(engine_path)


def generate_image(
    engine: dict,
    scene: dict,
    seed: int | None = None,
    num_images: int = 1,
    custom_prompt: str | None = None,
) -> list[dict]:
    """fal.ai APIで画像を生成する"""
    # FAL_KEY チェック
    if not os.environ.get("FAL_KEY"):
        print("エラー: FAL_KEY が設定されていません")
        print("  export FAL_KEY='your-fal-api-key'")
        print("  または .env ファイルに FAL_KEY=... を記述してください")
        sys.exit(1)

    endpoint = engine["endpoint"]
    defaults = engine.get("defaults", {})
    api_type = engine.get("api_type", "standard")

    # プロンプト構築
    prompt = custom_prompt or scene["prompt_template"]

    # APIタイプ別にパラメータを構築
    if api_type == "flux-pro":
        # FLUX Pro / Ultra 系: aspect_ratio ベース、num_inference_steps なし
        aspect_map = {
            "portrait_4_3": "3:4",
            "landscape_4_3": "4:3",
            "square": "1:1",
            "portrait_3_2": "2:3",
            "landscape_3_2": "3:2",
        }
        img_size = scene.get("image_size", defaults.get("image_size", "portrait_4_3"))
        arguments = {
            "prompt": prompt,
            "aspect_ratio": aspect_map.get(img_size, "3:4"),
            "num_images": num_images,
            "safety_tolerance": defaults.get("safety_tolerance", "5"),
            "output_format": "png",
        }
        # raw mode（Ultra Raw用）
        if defaults.get("raw"):
            arguments["raw"] = True
    else:
        # 標準API: image_size, num_inference_steps, guidance_scale 等
        arguments = {
            "prompt": prompt,
            "image_size": scene.get("image_size", defaults.get("image_size", "portrait_4_3")),
            "num_inference_steps": scene.get(
                "num_inference_steps", defaults.get("num_inference_steps", 40)
            ),
            "guidance_scale": scene.get("guidance_scale", defaults.get("guidance_scale", 7.5)),
            "num_images": num_images,
        }
        # ネガティブプロンプト
        if scene.get("negative_prompt"):
            arguments["negative_prompt"] = scene["negative_prompt"]
        # エンジン固有パラメータ
        for key in ["raw", "enable_safety_checker", "safety_tolerance"]:
            if key in defaults:
                arguments[key] = defaults[key]

    # シード
    if seed is not None:
        arguments["seed"] = seed

    print(f"生成中... エンジン: {engine['name']}, シーン: {scene['name']}")
    print(f"  エンドポイント: {endpoint}")
    print(f"  APIタイプ: {api_type}")
    if seed is not None:
        print(f"  シード: {seed}")

    def on_queue_update(update):
        if isinstance(update, fal_client.InProgress):
            for log in update.logs:
                print(f"  [{log.get('message', '')}]")

    max_retries = 3
    endpoints_to_try = [endpoint]
    fallback = engine.get("fallback_endpoint")
    if fallback:
        endpoints_to_try.append(fallback)

    last_error = None
    for ep in endpoints_to_try:
        for attempt in range(1, max_retries + 1):
            try:
                if ep != endpoint or attempt > 1:
                    label = f"フォールバック {ep}" if ep != endpoint else f"リトライ {attempt}/{max_retries}"
                    print(f"  {label}")
                result = fal_client.subscribe(
                    ep,
                    arguments=arguments,
                    with_logs=True,
                    on_queue_update=on_queue_update,
                )
                return result.get("images", [])
            except Exception as e:
                last_error = e
                print(f"  エラー (attempt {attempt}): {e}")
                if attempt < max_retries:
                    wait = 2 ** attempt
                    print(f"  {wait}秒後にリトライ...")
                    time.sleep(wait)

    raise last_error


def save_images(
    images: list[dict],
    output_dir: str,
    engine_name: str,
    scene_name: str,
    seed: int | None,
) -> list[str]:
    """生成された画像をダウンロードして保存する"""
    import urllib.request

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_paths = []

    for i, img in enumerate(images):
        url = img["url"]
        # ファイル名: エンジン_シーン_タイムスタンプ_シード_連番.png
        seed_str = f"_s{seed}" if seed is not None else ""
        filename = f"{engine_name}_{scene_name}_{timestamp}{seed_str}_{i:02d}.png"
        filepath = output_path / filename

        print(f"  保存中: {filepath}")
        urllib.request.urlretrieve(url, filepath)
        saved_paths.append(str(filepath))

    return saved_paths


def save_metadata(
    saved_paths: list[str],
    engine: dict,
    scene: dict,
    seed: int | None,
    output_dir: str,
) -> str:
    """生成メタデータをJSONLで保存する"""
    log_path = Path(output_dir) / "generation_log.jsonl"
    timestamp = datetime.now().isoformat()

    for path in saved_paths:
        entry = {
            "timestamp": timestamp,
            "engine": engine["name"],
            "scene": scene["name"],
            "seed": seed,
            "file": path,
            "prompt": scene["prompt_template"],
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return str(log_path)


def main():
    parser = argparse.ArgumentParser(
        description="XaiX — AI美女画像生成パイプライン v8",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python generate_beauty_v8.py --engine lora-realism --scene night_1 --seed 1234
  python generate_beauty_v8.py --engine lora-realism --scene cafe_1 --num 4
  python generate_beauty_v8.py --engine lora-artistic --scene beach_1 --prompt "custom prompt"
  python generate_beauty_v8.py --list-scenes
  python generate_beauty_v8.py --list-engines
        """,
    )

    parser.add_argument("--engine", "-e", default="lora-realism", help="エンジン名 (default: lora-realism)")
    parser.add_argument("--scene", "-s", help="シーン名")
    parser.add_argument("--seed", type=int, default=None, help="ランダムシード")
    parser.add_argument("--num", "-n", type=int, default=1, help="生成枚数 (default: 1)")
    parser.add_argument("--prompt", "-p", help="カスタムプロンプト（シーンのプロンプトを上書き）")
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT_DIR, help=f"出力先 (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--list-scenes", action="store_true", help="利用可能なシーン一覧を表示")
    parser.add_argument("--list-engines", action="store_true", help="利用可能なエンジン一覧を表示")
    parser.add_argument("--dry-run", action="store_true", help="実際に生成せずパラメータを表示")

    args = parser.parse_args()

    # 一覧表示
    if args.list_scenes:
        print("利用可能なシーン:")
        for f in sorted(SCENES_DIR.glob("*.yaml")):
            scene = load_yaml(f)
            print(f"  {f.stem:15s} — {scene.get('description', '')}")
        return

    if args.list_engines:
        print("利用可能なエンジン:")
        for f in sorted(ENGINES_DIR.glob("*.yaml")):
            eng = load_yaml(f)
            print(f"  {f.stem:15s} — {eng.get('description', '')}")
        return

    # シーン必須チェック
    if not args.scene:
        parser.error("--scene を指定してください。--list-scenes で一覧を確認できます。")

    # 設定を読み込み
    engine = load_engine(args.engine)
    scene = load_scene(args.scene)

    print("=" * 60)
    print(f"XaiX v8 — AI美女画像生成")
    print(f"  エンジン: {engine['name']} ({engine['description']})")
    print(f"  シーン:   {scene['name']} ({scene['description']})")
    print(f"  出力先:   {args.output}")
    print(f"  枚数:     {args.num}")
    print("=" * 60)

    if args.dry_run:
        print("\n[dry-run] 実際の生成はスキップされました")
        return

    # 画像生成
    start = time.time()
    images = generate_image(
        engine=engine,
        scene=scene,
        seed=args.seed,
        num_images=args.num,
        custom_prompt=args.prompt,
    )
    elapsed = time.time() - start

    if not images:
        print("エラー: 画像が生成されませんでした")
        sys.exit(1)

    print(f"\n{len(images)} 枚生成完了 ({elapsed:.1f}秒)")

    # 画像保存
    saved = save_images(images, args.output, engine["name"], scene["name"], args.seed)

    # メタデータ保存
    log_path = save_metadata(saved, engine, scene, args.seed, args.output)

    print(f"\n保存先:")
    for p in saved:
        print(f"  {p}")
    print(f"ログ: {log_path}")
    print("完了!")


if __name__ == "__main__":
    main()
