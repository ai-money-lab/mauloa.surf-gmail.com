"""SNS投稿文・キャプション・ハッシュタグの自動生成."""

import logging
from typing import Optional

from core.claude_client import ClaudeClient

logger = logging.getLogger(__name__)


class CaptionGenerator:
    """プラットフォーム別のキャプション生成."""

    def __init__(self):
        self.claude = ClaudeClient()

    def generate_x_caption(
        self,
        char_name: str,
        personality: str,
        situation: str,
        lang: str = "ja",
        count: int = 1,
    ) -> list[dict]:
        """X（Twitter）投稿文を生成.

        Returns:
            [{"text": str, "hashtags": [str]}]
        """
        lang_instruction = "日本語で" if lang == "ja" else "in English"
        prompt = (
            f"あなたは「{char_name}」というAIバーチャルモデルのSNS担当です。\n"
            f"ペルソナ: {personality}\n\n"
            f"以下のシチュエーションで{lang_instruction}X（Twitter）投稿文を{count}本書いてください。\n"
            f"シチュエーション: {situation}\n\n"
            f"要件:\n"
            f"- 140文字以内（日本語）/ 280文字以内（英語）\n"
            f"- 一人称は「私」「わたし」\n"
            f"- キャラのペルソナに合った口調\n"
            f"- エンゲージメントを誘う内容（質問、共感、日常感）\n"
            f"- ハッシュタグ3-5個\n"
            f"- 絵文字は控えめに（1-2個まで）\n\n"
            f"JSON配列で出力: [{{\"text\": str, \"hashtags\": [str]}}]"
        )
        return self._generate(prompt, count)

    def generate_instagram_caption(
        self,
        char_name: str,
        personality: str,
        situation: str,
        lang: str = "ja",
        count: int = 1,
    ) -> list[dict]:
        """Instagram キャプションを生成."""
        lang_instruction = "日本語と英語の両方で" if lang == "both" else ("日本語で" if lang == "ja" else "in English")
        prompt = (
            f"あなたは「{char_name}」というAIバーチャルモデルのInstagram担当です。\n"
            f"ペルソナ: {personality}\n\n"
            f"以下のシチュエーションで{lang_instruction}Instagramキャプションを{count}本書いてください。\n"
            f"シチュエーション: {situation}\n\n"
            f"要件:\n"
            f"- 改行を入れて読みやすく\n"
            f"- ストーリー性のある内容\n"
            f"- CTA（いいね・コメント誘導）を含める\n"
            f"- ハッシュタグ10-15個（本文と分離）\n"
            f"- グローバルリーチのため英語ハッシュタグも含める\n\n"
            f"JSON配列で出力: [{{\"caption\": str, \"hashtags\": [str]}}]"
        )
        return self._generate(prompt, count)

    def generate_fanvue_caption(
        self,
        char_name: str,
        personality: str,
        content_type: str,
        is_ppv: bool = False,
        count: int = 1,
    ) -> list[dict]:
        """Fanvue投稿キャプションを生成."""
        ppv_note = "これはPPV（有料個別販売）コンテンツです。購入意欲を刺激する文を書いてください。" if is_ppv else ""
        prompt = (
            f"あなたは「{char_name}」というFanvueのAIクリエイターです。\n"
            f"ペルソナ: {personality}\n\n"
            f"コンテンツタイプ「{content_type}」の投稿文を{count}本、英語で書いてください。\n"
            f"{ppv_note}\n\n"
            f"要件:\n"
            f"- 親密で個人的なトーン（ファンに直接話しかけるように）\n"
            f"- ティーザー的な内容（全てを見せない）\n"
            f"- サブスク継続を促す内容\n"
            f"- 絵文字は適度に使用\n\n"
            f"JSON配列で出力: [{{\"caption\": str, \"cta\": str}}]"
        )
        return self._generate(prompt, count)

    def generate_fanza_description(
        self,
        char_name: str,
        situation: str,
        image_count: int,
        price_jpy: int = 770,
    ) -> dict:
        """FANZA同人CG集の作品紹介文を生成."""
        prompt = (
            f"FANZA同人で販売するAI生成CG集の作品紹介文を書いてください。\n\n"
            f"キャラクター: {char_name}\n"
            f"シチュエーション: {situation}\n"
            f"画像枚数: {image_count}枚（差分含む）\n"
            f"価格: ¥{price_jpy}\n\n"
            f"要件:\n"
            f"- 購入意欲を刺激する魅力的な紹介文\n"
            f"- シチュエーションの詳細な説明\n"
            f"- 画像枚数と内容の概要\n"
            f"- 注意書き（AI生成作品であること、全て架空のキャラクター）\n\n"
            f"JSON形式で出力: {{\"title\": str, \"description\": str, \"tags\": [str], \"notice\": str}}"
        )
        try:
            result = self.claude.generate_json(prompt, temperature=0.7)
            return result if isinstance(result, dict) else {"title": "", "description": "", "tags": [], "notice": ""}
        except Exception as e:
            logger.error("FANZA紹介文生成失敗: %s", e)
            return {"title": "", "description": "", "tags": [], "notice": ""}

    def generate_hashtag_set(
        self,
        platform: str,
        category: str = "sfw",
        lang: str = "both",
    ) -> list[str]:
        """プラットフォーム別のハッシュタグセットを生成."""
        base_tags = {
            "x_twitter": {
                "sfw": ["#AI美女", "#AIグラビア", "#AIart", "#AIgirl", "#AI写真",
                         "#StableDiffusion", "#AIbeauty", "#virtualmodel"],
                "nsfw": ["#AIbeauty", "#aigirlfriend", "#virtualmodel", "#fanvue"],
            },
            "instagram": {
                "sfw": ["#AImodel", "#AIgenerated", "#virtualmodel", "#aiinfluencer",
                         "#digitalmodel", "#AIart", "#aibeauty", "#AI美女",
                         "#aiphotography", "#virtualinfluencer"],
            },
            "fanvue": {
                "nsfw": ["#exclusive", "#newcontent", "#justposted", "#subscribenow"],
            },
        }
        return base_tags.get(platform, {}).get(category, [])

    def _generate(self, prompt: str, count: int) -> list[dict]:
        """Claude APIで生成."""
        try:
            results = self.claude.generate_json(prompt, temperature=0.7)
            if isinstance(results, list):
                return results[:count]
            return [results]
        except Exception as e:
            logger.error("キャプション生成失敗: %s", e)
            return [{"text": f"生成エラー: {e}", "hashtags": []}]
