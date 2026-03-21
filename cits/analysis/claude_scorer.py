"""
Phase 1-B: FOMC声明文のClaude APIスコアリング。
過去のFOMC声明文を取得し、Claudeにハト派/タカ派スコアを付けさせる。
実際の日経反応との相関を検証する。

使用方法:
  ANTHROPIC_API_KEY環境変数を設定してから実行。
  python claude_scorer.py
"""

import json
import os
import sys
import time
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
STATEMENTS_DIR = DATA_DIR / "fomc_statements"
OUTPUT_DIR = DATA_DIR / "market_data"

# Claude APIのモデル
MODEL = "claude-sonnet-4-20250514"

SCORING_PROMPT = """あなたはFOMC声明文の専門アナリストです。
以下のFOMC声明文を分析し、JSON形式で回答してください。

## 現在の声明文
{statement}

## 前回の声明文
{prev_statement}

## 回答形式（JSONのみで回答、他のテキスト不要）
{{
  "hawkish_score": -100〜+100（-100=超ハト派、+100=超タカ派）,
  "surprise_score": 0〜100（市場予想との乖離度）,
  "key_changes": ["変更点1", "変更点2"],
  "removed_words": ["削除された重要単語"],
  "added_words": ["追加された重要単語"],
  "nikkei_direction": "UP" or "DOWN" or "NEUTRAL",
  "nikkei_impact_range": "±○○円",
  "confidence": 0〜100,
  "reasoning": "判断根拠の説明"
}}"""


def get_claude_client():
    """Anthropic APIクライアントを取得する。"""
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    return anthropic.Anthropic(api_key=api_key)


def score_statement(client, statement: str, prev_statement: str) -> dict:
    """Claude APIに声明文を投げてスコアを取得する。"""
    prompt = SCORING_PROMPT.format(
        statement=statement,
        prev_statement=prev_statement if prev_statement else "（前回の声明文なし）",
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # JSON部分を抽出
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"WARNING: Failed to parse JSON: {text[:200]}")
        return {"error": text[:200]}


def load_statements() -> list[dict]:
    """保存済みのFOMC声明文を読み込む。"""
    statements = []
    if not STATEMENTS_DIR.exists():
        print(f"WARNING: {STATEMENTS_DIR} does not exist")
        return statements

    for path in sorted(STATEMENTS_DIR.glob("*.txt")):
        date = path.stem  # YYYY-MM-DD
        with open(path) as f:
            text = f.read()
        statements.append({"date": date, "text": text})

    return statements


def run_scoring(statements: list[dict]) -> list[dict]:
    """全声明文をスコアリングする。"""
    client = get_claude_client()
    results = []

    for i, stmt in enumerate(statements):
        prev_text = statements[i - 1]["text"] if i > 0 else None
        print(f"Scoring {stmt['date']} ({i+1}/{len(statements)})...")

        score = score_statement(client, stmt["text"], prev_text)
        score["date"] = stmt["date"]
        results.append(score)

        # Rate limiting
        if i < len(statements) - 1:
            time.sleep(1)

    return results


def create_sample_statements():
    """サンプル声明文ファイルを作成する（テスト用）。"""
    STATEMENTS_DIR.mkdir(parents=True, exist_ok=True)

    print("FOMC声明文をdata/fomc_statements/に配置してください。")
    print("ファイル名: YYYY-MM-DD.txt（例: 2024-09-18.txt）")
    print()
    print("FRB公式サイト:")
    print("  https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
    print()
    print("各会合の「Statement」リンクからテキストをコピーして保存。")
    print("声明文が配置されたら再度実行してください。")


def main():
    statements = load_statements()

    if not statements:
        print("No FOMC statements found.")
        create_sample_statements()
        return

    print(f"Found {len(statements)} FOMC statements")

    # スコアリング実行
    results = run_scoring(statements)

    # 結果保存
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "claude_scores.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nScores saved to {output_path}")

    # サマリー出力
    print("\n■ スコアリング結果サマリー")
    for r in results:
        if "error" in r:
            print(f"  {r['date']}: ERROR")
        else:
            print(f"  {r['date']}: hawkish={r.get('hawkish_score', '?'):+d}, "
                  f"surprise={r.get('surprise_score', '?')}, "
                  f"direction={r.get('nikkei_direction', '?')}")


if __name__ == "__main__":
    main()
