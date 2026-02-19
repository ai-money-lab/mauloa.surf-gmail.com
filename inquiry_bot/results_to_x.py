"""実績 → X投稿変換 — System D連携.

問い合わせBotの運用実績をX投稿用のコンテンツに変換する。
System D (generate_results_content.py) から呼び出される。

使い方:
  python -m inquiry_bot.results_to_x
"""

import logging
from inquiry_bot.analytics import InquiryAnalytics

logger = logging.getLogger(__name__)


def generate_bot_results_posts() -> list[dict]:
    """Bot運用実績からX投稿案を生成.

    System D のresults_to_post.txtプロンプトに渡すための
    実績データを構造化して返す。
    """
    analytics = InquiryAnalytics()
    logs = analytics.load_logs(30)

    if not logs:
        return []

    total = len(logs)
    auto_resolved = sum(1 for entry in logs if not entry.get("escalated", False))
    auto_rate = (auto_resolved / total * 100) if total > 0 else 0
    saved_hours = (auto_resolved * analytics.HUMAN_RESPONSE_MINUTES) / 60

    posts = []

    # パターン1: 自動応答率の実績
    if auto_rate >= 80:
        posts.append({
            "theme": "テクノロジー×不動産",
            "pillar": 5,
            "data": {
                "auto_rate": f"{auto_rate:.0f}%",
                "total_inquiries": total,
                "period": "過去30日間",
            },
            "draft": (
                f"自社の問い合わせ対応にAIを導入して1ヶ月。\n\n"
                f"結果:\n"
                f"・自動応答率 {auto_rate:.0f}%\n"
                f"・月{total}件の問い合わせを処理\n"
                f"・対応時間 約{saved_hours:.0f}時間削減\n\n"
                f"「空いてますか？」「賃料いくら？」みたいな定型質問は\n"
                f"ほぼ100%AIが即答してくれる。\n\n"
                f"人間は本当に判断が必要な案件だけに集中できるようになった。\n\n"
                f"管理会社にとっての「DX」って、\n"
                f"こういう地味だけど確実な改善の積み重ねだと思う。"
            ),
        })

    # パターン2: 時間削減の実績
    if saved_hours >= 10:
        posts.append({
            "theme": "経営者の日常",
            "pillar": 4,
            "data": {
                "saved_hours": f"{saved_hours:.0f}時間/月",
                "equivalent_cost": f"約{int(saved_hours * 2000):,}円",
            },
            "draft": (
                f"問い合わせBot導入後、月{saved_hours:.0f}時間の対応時間を削減。\n\n"
                f"時給2,000円のスタッフ換算で約{int(saved_hours * 2000):,}円分。\n\n"
                f"浮いた時間で何をしているかというと、\n"
                f"・入居者さんとの丁寧なコミュニケーション\n"
                f"・物件の定期巡回（以前は後回しになりがちだった）\n"
                f"・新しい管理受託の営業\n\n"
                f"「効率化」の目的は人を減らすことじゃなくて、\n"
                f"本来やるべきことに時間を使えるようにすること。\n\n"
                f"管理会社の仕事って結局「人と物件の信頼関係」だから。"
            ),
        })

    # パターン3: 24時間対応の実績
    night_inquiries = sum(1 for entry in logs
                         if entry.get("hour", 12) < 9 or entry.get("hour", 12) >= 18)
    if night_inquiries > 0:
        night_rate = (night_inquiries / total * 100) if total > 0 else 0
        posts.append({
            "theme": "不動産の裏側",
            "pillar": 1,
            "data": {
                "night_inquiries": night_inquiries,
                "night_rate": f"{night_rate:.0f}%",
            },
            "draft": (
                f"うちのAI問い合わせBotのデータを見たら、\n"
                f"全問い合わせの{night_rate:.0f}%が営業時間外だった。\n\n"
                f"つまり{night_inquiries}件の問い合わせは、\n"
                f"以前なら翌朝まで放置されていたということ。\n\n"
                f"物件探しって仕事終わりの夜にやる人が多い。\n"
                f"その瞬間に「空いてます。内見は〇日いかがですか？」\n"
                f"と返せるかどうかで、成約率が変わる。\n\n"
                f"不動産管理会社にとっての24時間対応は、\n"
                f"サービスの質じゃなくて、もはやインフラだと思う。"
            ),
        })

    return posts


def main():
    """テスト実行."""
    posts = generate_bot_results_posts()
    if not posts:
        print("投稿データなし（運用データが蓄積されてから実行してください）")
        return

    for i, post in enumerate(posts, 1):
        print(f"\n{'='*50}")
        print(f"投稿案 {i} | ピラー: {post['pillar']} ({post['theme']})")
        print(f"{'='*50}")
        print(post["draft"])
        print(f"\nデータ: {post['data']}")


if __name__ == "__main__":
    main()
