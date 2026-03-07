"""セットアップ確認スクリプト — 必要な環境変数とパッケージをチェック.

使い方:
  python -m inquiry_bot.check_setup
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()


def check_env_var(name: str, required: bool = True) -> bool:
    value = os.getenv(name, "")
    if value:
        masked = value[:4] + "..." + value[-4:] if len(value) > 12 else "***"
        print(f"  [OK] {name} = {masked}")
        return True
    elif required:
        print(f"  [NG] {name} — 未設定（必須）")
        return False
    else:
        print(f"  [--] {name} — 未設定（任意）")
        return True


def check_package(name: str) -> bool:
    try:
        __import__(name)
        print(f"  [OK] {name}")
        return True
    except ImportError:
        print(f"  [NG] {name} — pip install {name} を実行してください")
        return False


def main():
    print("=" * 55)
    print(" 問い合わせBot セットアップ確認")
    print("=" * 55)

    all_ok = True

    # 1. 必須環境変数
    print("\n1. 環境変数（必須）")
    print("-" * 40)
    for var in ["ANTHROPIC_API_KEY"]:
        if not check_env_var(var):
            all_ok = False

    # 2. LINE環境変数
    print("\n2. LINE Messaging API")
    print("-" * 40)
    for var in ["LINE_CHANNEL_SECRET", "LINE_CHANNEL_ACCESS_TOKEN"]:
        if not check_env_var(var, required=False):
            pass  # LINEは任意（Webチャットのみでも動作）

    # 3. 通知環境変数
    print("\n3. 通知設定")
    print("-" * 40)
    check_env_var("LINE_CHANNEL_ACCESS_TOKEN", required=False)
    check_env_var("LINE_USER_ID", required=False)
    check_env_var("SLACK_WEBHOOK_URL", required=False)

    # 4. Google Sheets
    print("\n4. Google Sheets")
    print("-" * 40)
    check_env_var("INQUIRY_BOT_SHEET_ID", required=False)

    # 5. Pythonパッケージ
    print("\n5. Pythonパッケージ")
    print("-" * 40)
    packages = {
        "anthropic": "anthropic",
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "pydantic": "pydantic",
        "pyyaml": "yaml",
        "requests": "requests",
        "python-dotenv": "dotenv",
    }
    for display_name, import_name in packages.items():
        if not check_package(import_name):
            all_ok = False

    # 6. ファイル確認
    print("\n6. 設定ファイル")
    print("-" * 40)
    base = os.path.dirname(os.path.abspath(__file__))
    files = {
        "config.yaml": os.path.join(base, "config.yaml"),
        "faq_data.yaml": os.path.join(base, "faq_data.yaml"),
        "web_widget/index.html": os.path.join(base, "web_widget", "index.html"),
        "n8n_workflow.json": os.path.join(base, "n8n_workflow.json"),
    }
    for name, path in files.items():
        if os.path.exists(path):
            print(f"  [OK] {name}")
        else:
            print(f"  [NG] {name} — ファイルが見つかりません")
            all_ok = False

    prompt_path = os.path.join(base, "..", "prompts", "inquiry_bot_system.txt")
    if os.path.exists(prompt_path):
        print("  [OK] prompts/inquiry_bot_system.txt")
    else:
        print("  [NG] prompts/inquiry_bot_system.txt — ファイルが見つかりません")
        all_ok = False

    # 結果
    print()
    print("=" * 55)
    if all_ok:
        print(" 全てOK！Botを起動できます。")
        print()
        print(" 起動コマンド:")
        print("   uvicorn inquiry_bot.server:app --host 0.0.0.0 --port 8080 --reload")
        print()
        print(" ローカルテスト:")
        print("   python -m inquiry_bot.test_local")
        print()
        print(" Webチャットデモ:")
        print("   http://localhost:8080/chat")
    else:
        print(" 上記 [NG] の項目を修正してください。")
        print()
        print(" 詳細: docs/SETUP_LINE_BOT.md")
    print("=" * 55)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
