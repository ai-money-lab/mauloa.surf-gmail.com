"""ローカルテスト用スクリプト — ターミナルから対話テスト.

使い方:
  python -m inquiry_bot.test_local

LINE/Webサーバーなしで、ターミナル上でBotの応答をテストできます。
"""

import sys
import uuid

from dotenv import load_dotenv

load_dotenv()


def main():
    print("=" * 50)
    print("問い合わせ自動対応Bot — ローカルテスト")
    print("=" * 50)
    print()

    # BotEngine初期化
    try:
        from inquiry_bot.bot_engine import BotEngine
        bot = BotEngine()
        print("[OK] BotEngine 初期化成功")
    except Exception as e:
        print(f"[ERROR] BotEngine 初期化失敗: {e}")
        print()
        print("確認事項:")
        print("  1. ANTHROPIC_API_KEY が .env に設定されているか")
        print("  2. pip install -r requirements.txt を実行したか")
        sys.exit(1)

    session_id = f"test_{uuid.uuid4().hex[:8]}"
    print(f"[INFO] セッションID: {session_id}")
    print()
    print("メッセージを入力してください（quit で終了）")
    print("-" * 50)

    while True:
        try:
            user_input = input("\nあなた > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n終了します。")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("\n終了します。")
            break

        # Bot応答生成
        try:
            response = bot.handle_message(
                user_message=user_input,
                session_id=session_id,
                channel="test",
                user_id="test_user",
            )

            print(f"\nBot > {response['reply']}")
            print(f"  [カテゴリ: {response.get('category', '-')} | "
                  f"信頼度: {response.get('confidence', 0):.0%} | "
                  f"エスカレーション: {'はい' if response.get('escalated') else 'いいえ'}]")

        except Exception as e:
            print(f"\n[ERROR] 応答生成失敗: {e}")

    # セッション統計
    stats = bot.conversation.get_session_stats(session_id)
    if stats:
        print()
        print("=" * 50)
        print("セッション統計:")
        print(f"  メッセージ数: {stats.get('message_count', 0)}")
        print(f"  ユーザー発言: {stats.get('user_messages', 0)}")
        print(f"  エスカレーション: {'あり' if stats.get('escalated') else 'なし'}")
        print(f"  所要時間: {stats.get('duration_seconds', 0):.0f}秒")
        print("=" * 50)


if __name__ == "__main__":
    main()
