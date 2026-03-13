"""HIROKIMIYAO X投稿用まとめカード自動生成.

投稿テキストを解析し、nano-banana 2で保存したくなるビジュアルカードを生成する。

Usage:
    # 単体テスト
    python tools/generate_x_card.py --text "不動産購入前に確認すべき5つのポイント..."

    # バッチ投稿JSONから生成
    python tools/generate_x_card.py --batch data/system_a/x_post_batch_v4.json --ids hm_01 hm_03

    # 全バッチ投稿にカード生成
    python tools/generate_x_card.py --batch data/system_a/x_post_batch_v4.json --all
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
NANO_BANANA_DIR = BASE_DIR / "tools" / "nano-banana-2"
OUTPUT_DIR = BASE_DIR / "data" / "x_cards"

# --- カードタイプ判定 ---

CARD_TYPES = {
    "checklist": {
        "keywords": ["確認", "チェック", "ポイント", "注意", "項目", "条件", "必須"],
        "description": "チェックリスト形式のまとめカード",
    },
    "ranking": {
        "keywords": ["ランキング", "TOP", "順位", "位", "ベスト", "ワースト"],
        "description": "ランキング・順位表示カード",
    },
    "comparison": {
        "keywords": ["比較", "VS", "vs", "違い", "差", "メリット", "デメリット"],
        "description": "比較表カード",
    },
    "stats": {
        "keywords": ["%", "万円", "件", "倍", "割", "円", "平均", "相場"],
        "description": "数字・統計ハイライトカード",
    },
    "steps": {
        "keywords": ["ステップ", "手順", "流れ", "まず", "次に", "最後"],
        "description": "ステップ・フロー図カード",
    },
    "tips": {
        "keywords": ["コツ", "秘訣", "方法", "テクニック", "知恵", "裏技"],
        "description": "Tips・ノウハウまとめカード",
    },
}

# --- ブランドスタイル ---

BRAND_STYLE = """
Design style rules (MUST follow exactly):
- Background: clean white (#FFFFFF) or very light warm gray (#F8F6F3)
- Primary accent color: deep navy (#1a1a2e) for headings and borders
- Secondary color: warm charcoal (#333333) for body text
- Accent highlight: subtle gold or warm orange for key numbers/stats
- Typography feel: modern Japanese sans-serif (clean, professional)
- Layout: generous whitespace, clear hierarchy, no clutter
- Bottom strip: thin dark navy bar with "HIROKI MIYAO | 不動産のプロ" in small white text
- No stock photo backgrounds, no gradients, no 3D effects
- Flat, editorial, magazine-quality infographic style
- All text MUST be in Japanese
"""


def detect_card_type(text: str) -> str:
    """投稿テキストからカードタイプを判定."""
    scores = {}
    for card_type, info in CARD_TYPES.items():
        score = sum(1 for kw in info["keywords"] if kw in text)
        scores[card_type] = score

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "stats"  # デフォルト: 数字カード
    return best


def extract_key_points(text: str) -> list[str]:
    """投稿テキストからキーポイントを抽出."""
    # スレッドの場合はリスト
    if isinstance(text, list):
        text = "\n".join(text)

    # 数字を含む文を優先抽出
    sentences = re.split(r"[。\n]", text)
    points = []
    for s in sentences:
        s = s.strip()
        if not s or len(s) < 5:
            continue
        # 数字・%・万円を含む文を優先
        if re.search(r"\d", s):
            points.insert(0, s)
        elif len(points) < 5:
            points.append(s)

    return points[:5]


def build_card_prompt(text: str, card_type: str) -> str:
    """nano-banana用のプロンプトを構築."""
    points = extract_key_points(text)
    points_text = "\n".join(f"  - {p}" for p in points)

    type_instructions = {
        "checklist": (
            "Create a clean CHECKLIST card with checkmark icons (✓) next to each item. "
            "Each item should be on its own row with clear spacing. "
            "Use a numbered or bullet format."
        ),
        "ranking": (
            "Create a RANKING card with numbered items (1st, 2nd, 3rd...). "
            "Use medal or trophy icons for top items. "
            "Show clear visual hierarchy with the #1 item largest."
        ),
        "comparison": (
            "Create a COMPARISON card with two columns side by side. "
            "Use contrasting subtle colors for each column. "
            "Show clear labels for each side being compared."
        ),
        "stats": (
            "Create a STATISTICS highlight card with large bold numbers as the focal point. "
            "Each key number should be prominently displayed with its context below. "
            "Use 2-4 key statistics in a grid or vertical layout."
        ),
        "steps": (
            "Create a STEP-BY-STEP flow card with numbered steps connected by arrows or lines. "
            "Each step should have a short title and optional one-line description. "
            "Show clear progression from start to finish."
        ),
        "tips": (
            "Create a TIPS card with lightbulb or star icons next to each tip. "
            "Use clean card-within-card design for each tip. "
            "Keep each tip to one short line."
        ),
    }

    instruction = type_instructions.get(card_type, type_instructions["stats"])

    prompt = f"""Generate a professional Japanese infographic summary card for a social media post.

{instruction}

Content to visualize (extract key information from this Japanese text):
{points_text}

{BRAND_STYLE}

CRITICAL: All text on the card must be written in Japanese (日本語). The card should look like a professional editorial infographic that someone would want to bookmark/save. Make it clean, minimal, and information-dense but not cluttered. The card should be readable at mobile phone size."""

    return prompt


def _build_short_prompt(text: str, card_type: str) -> str:
    """Windowsコマンドライン制限に収まる短縮プロンプト."""
    if isinstance(text, list):
        text = " ".join(text)

    # テキストを150文字に短縮
    content = text[:150]

    type_map = {
        "checklist": "checklist with checkmarks",
        "ranking": "ranking with numbered items",
        "comparison": "two-column comparison table",
        "stats": "statistics card with large bold numbers",
        "steps": "step-by-step flow diagram",
        "tips": "tips card with icon bullets",
    }
    layout = type_map.get(card_type, "statistics card")

    return (
        f"Professional Japanese infographic card, {layout}. "
        f"Content: {content}. "
        f"White background, navy (#1a1a2e) headings, warm charcoal text, "
        f"gold accent for numbers. Clean minimal editorial style. "
        f"Bottom bar: HIROKI MIYAO | 不動産のプロ. "
        f"All text in Japanese. Mobile-readable size."
    )


def generate_card(
    text: str,
    output_name: str = "card",
    output_dir: Path | None = None,
    card_type: str | None = None,
) -> Path | None:
    """投稿テキストからまとめカードを生成.

    Returns:
        生成された画像のパス or None
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    if card_type is None:
        if isinstance(text, list):
            card_type = detect_card_type(" ".join(text))
        else:
            card_type = detect_card_type(text)

    prompt = build_card_prompt(text, card_type)

    # nano-banana実行（Windowsではbun.cmdを使う）
    bun_cmd = os.path.join(os.environ.get("APPDATA", ""), "npm", "bun.cmd")
    if not os.path.exists(bun_cmd):
        bun_cmd = "bun"

    # プロンプトが長いのでファイル経由で渡す（Windowsコマンドライン制限回避）
    prompt_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(prompt)
            prompt_file = f.name

        # nano-banana CLIにはファイル読み込み機能がないのでプロンプトを短縮して渡す
        # 短縮版プロンプト: 核心部分だけ渡し、スタイルは最小限に
        short_prompt = _build_short_prompt(text, card_type)

        cmd = [
            bun_cmd, "run", str(NANO_BANANA_DIR / "src" / "cli.ts"),
            short_prompt,
            "-s", "1K",
            "-a", "4:5",
            "-o", output_name,
            "-d", str(output_dir),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(BASE_DIR),
            encoding="utf-8",
        )
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr}", file=sys.stderr)
            return None

        # 生成ファイルを探す
        for ext in [".png", ".jpg", ".jpeg", ".webp"]:
            candidate = output_dir / f"{output_name}{ext}"
            if candidate.exists():
                print(f"  OK: {candidate} ({card_type})")
                return candidate

        for f in sorted(output_dir.glob(f"{output_name}*")):
            if f.suffix in (".png", ".jpg", ".jpeg", ".webp"):
                print(f"  OK: {f} ({card_type})")
                return f

        print("  WARNING: file not found after generation", file=sys.stderr)
        return None

    except subprocess.TimeoutExpired:
        print("  ERROR: timeout", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return None
    finally:
        if prompt_file and os.path.exists(prompt_file):
            os.unlink(prompt_file)


def process_batch(batch_path: str, ids: list[str] | None = None, all_posts: bool = False):
    """バッチJSONからカードを生成."""
    with open(batch_path, "r", encoding="utf-8") as f:
        posts = json.load(f)

    results = {}
    for post in posts:
        post_id = post.get("id", "unknown")

        # フィルタ
        if not all_posts and ids and post_id not in ids:
            continue

        text = post.get("body", post.get("text", ""))
        thread = post.get("thread", [])
        if thread:
            full_text = text + "\n" + "\n".join(thread)
        else:
            full_text = text

        if not full_text.strip():
            continue

        print(f"[{post_id}] カード生成中...")
        path = generate_card(full_text, output_name=post_id)
        if path:
            results[post_id] = str(path)

    # 結果をJSONで保存
    if results:
        manifest_path = OUTPUT_DIR / "card_manifest.json"
        existing = {}
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.update(results)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print(f"\n生成完了: {len(results)}枚 → {manifest_path}")

    return results


def main():
    parser = argparse.ArgumentParser(description="HIROKIMIYAO X投稿まとめカード生成")
    parser.add_argument("--text", type=str, help="投稿テキスト（直接指定）")
    parser.add_argument("--batch", type=str, help="バッチJSONファイルパス")
    parser.add_argument("--ids", nargs="+", help="生成対象のポストID")
    parser.add_argument("--all", action="store_true", help="全ポスト対象")
    parser.add_argument("--type", choices=list(CARD_TYPES.keys()), help="カードタイプ強制指定")
    parser.add_argument("--output", type=str, default="card", help="出力ファイル名")

    args = parser.parse_args()

    if args.text:
        print(f"カードタイプ: {args.type or detect_card_type(args.text)}")
        generate_card(args.text, output_name=args.output, card_type=args.type)
    elif args.batch:
        process_batch(args.batch, ids=args.ids, all_posts=args.all)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
