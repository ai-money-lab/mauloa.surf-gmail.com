"""Asset Generator — nano-banana + Claude を統合してデジタル資産を自動生成."""

import json
import logging
import subprocess
import shutil
import zipfile
from datetime import timezone, timedelta
from pathlib import Path
from typing import Optional

from core.claude_client import ClaudeClient
from core.quality_checker import QualityChecker

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
DELIVERABLES_DIR = BASE_DIR / "data" / "system_e" / "deliverables"
PROMPTS_DIR = BASE_DIR / "prompts"


def _find_nano_banana() -> str:
    """nano-banana CLI のパスを探す."""
    which = shutil.which("nano-banana")
    if which:
        return which
    local = BASE_DIR / "tools" / "nano-banana-2" / "node_modules" / ".bin" / "nano-banana"
    if local.exists():
        return str(local)
    return "nano-banana"


NANO_BANANA_CMD = _find_nano_banana()


class AssetGenerator:
    """AI資産の生成エンジン."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.quality_checker = QualityChecker(self.claude)

    def generate_image(
        self,
        prompt: str,
        output_dir: Path,
        filename: str = "image",
        model: str = "flash",
        size: str = "1K",
        aspect_ratio: str = "1:1",
        transparent: bool = False,
        reference_image: Optional[str] = None,
    ) -> Optional[Path]:
        """nano-banana で画像を1枚生成.

        Returns:
            生成されたファイルのパス or None
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            NANO_BANANA_CMD,
            prompt,
            "-s", size,
            "-a", aspect_ratio,
            "-o", filename,
            "-d", str(output_dir),
        ]

        if model == "pro":
            cmd.extend(["-m", "pro"])
        if transparent:
            cmd.append("-t")
        if reference_image:
            cmd.extend(["-r", reference_image])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(BASE_DIR),
            )
            if result.returncode != 0:
                logger.error("nano-banana failed: %s", result.stderr)
                return None

            # 生成されたファイルを探す
            for ext in [".png", ".jpg", ".jpeg", ".webp"]:
                candidate = output_dir / f"{filename}{ext}"
                if candidate.exists():
                    return candidate

            # ファイル名にサフィックスが付く場合
            for f in sorted(output_dir.glob(f"{filename}*")):
                if f.suffix in (".png", ".jpg", ".jpeg", ".webp"):
                    return f

            logger.warning("Image file not found after generation")
            return None

        except subprocess.TimeoutExpired:
            logger.error("nano-banana timed out")
            return None
        except Exception as e:
            logger.error("Image generation error: %s", e)
            return None

    def generate_image_pack(
        self,
        base_prompt: str,
        count: int,
        output_dir: Path,
        model: str = "flash",
        size: str = "1K",
        aspect_ratio: str = "1:1",
        transparent: bool = False,
    ) -> list[Path]:
        """統一テーマで複数画像を生成.

        プロンプトをバリエーション展開してから個別生成。
        """
        # Claude でプロンプトバリエーションを生成
        variation_prompt = (
            f"以下のベースプロンプトから、{count}個の異なるバリエーションプロンプトを生成してください。\n"
            f"各プロンプトは統一感を保ちつつ、構図・色合い・要素を変化させてください。\n"
            f"JSON配列で出力してください。\n\n"
            f"ベースプロンプト: {base_prompt}"
        )

        try:
            prompts = self.claude.generate_json(variation_prompt)
            if not isinstance(prompts, list):
                prompts = [base_prompt] * count
        except Exception:
            prompts = [f"{base_prompt}, variation {i+1}" for i in range(count)]

        # 各プロンプトで画像生成
        generated = []
        for i, prompt in enumerate(prompts[:count]):
            if isinstance(prompt, dict):
                prompt = prompt.get("prompt", base_prompt)
            path = self.generate_image(
                prompt=str(prompt),
                output_dir=output_dir,
                filename=f"image_{i+1:02d}",
                model=model,
                size=size,
                aspect_ratio=aspect_ratio,
                transparent=transparent,
            )
            if path:
                generated.append(path)

        return generated

    def generate_text_content(
        self,
        content_type: str,
        topic: str,
        count: int = 1,
        style: str = "",
    ) -> list[dict]:
        """テキストコンテンツを生成（SNS投稿文、キャッチコピー等）.

        Returns:
            [{"text": str, "hashtags": list[str]}]
        """
        if content_type == "sns_post":
            prompt = (
                f"以下のトピックについて、SNS投稿文を{count}本生成してください。\n"
                f"各投稿は140文字以内で、エンゲージメントを最大化する内容にしてください。\n"
                f"ハッシュタグも3-5個含めてください。\n"
                f"JSON配列で出力: [{{'text': str, 'hashtags': [str]}}]\n\n"
                f"トピック: {topic}\n"
                f"スタイル: {style or '専門的だが親しみやすい'}"
            )
        elif content_type == "copy":
            prompt = (
                f"以下の情報からキャッチコピーと説明文を{count}パターン生成してください。\n"
                f"JSON配列で出力: [{{'headline': str, 'body': str}}]\n\n"
                f"情報: {topic}"
            )
        elif content_type == "listing":
            prompt = (
                f"以下の物件情報から、魅力的な物件紹介文を{count}パターン生成してください。\n"
                f"JSON配列で出力: [{{'title': str, 'description': str, 'highlights': [str]}}]\n\n"
                f"物件情報: {topic}"
            )
        else:
            prompt = (
                f"{content_type}を{count}件生成してください。\n"
                f"JSON配列で出力してください。\n\n"
                f"トピック: {topic}"
            )

        try:
            results = self.claude.generate_json(prompt, temperature=0.7)
            if isinstance(results, list):
                return results[:count]
            return [results]
        except Exception as e:
            logger.error("Text generation failed: %s", e)
            return [{"text": f"生成エラー: {e}", "hashtags": []}]

    def generate_report(
        self,
        topic: str,
        pages: int = 5,
        output_dir: Optional[Path] = None,
    ) -> str:
        """AIミニレポートを生成.

        Returns:
            Markdown形式のレポート本文
        """
        prompt = (
            f"以下のトピックについて、{pages}ページ相当のプロフェッショナルなレポートを作成してください。\n\n"
            f"## 要件:\n"
            f"- Markdown形式で出力\n"
            f"- 表紙（タイトル・日付）、目次、本文、まとめの構成\n"
            f"- データや数値を含めて信頼性を高める\n"
            f"- 実用的な洞察と提言を含める\n"
            f"- 1ページ≒800文字として{pages}ページ分\n\n"
            f"トピック: {topic}"
        )

        report_text = self.claude.generate(prompt, temperature=0.5, max_tokens=8000)

        # 品質チェック
        result = self.quality_checker.check(
            profile="report",
            content=report_text,
            context=f"AI Mini Report: {topic}",
        )
        if result.get("result") == "rejected":
            logger.warning("Report quality check failed, regenerating...")
            report_text = self.claude.generate(prompt, temperature=0.4, max_tokens=8000)

        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            report_path = output_dir / "report.md"
            report_path.write_text(report_text, encoding="utf-8")

        return report_text

    def generate_brand_kit(
        self,
        brand_info: str,
        output_dir: Path,
        model: str = "pro",
        size: str = "2K",
    ) -> dict:
        """ブランドキットを生成（ロゴ+バナー+アイコン+カラーパレット）.

        Returns:
            {"logos": [Path], "banners": [Path], "icons": [Path], "palette": dict}
        """
        # まずブランドコンセプトを生成
        concept_prompt = (
            f"以下のブランド情報からビジュアルコンセプトを提案してください。\n"
            f"JSON形式で出力: {{'style': str, 'colors': {{'primary': str, 'secondary': str, "
            f"'accent': str, 'background': str}}, 'mood': str, 'logo_prompt': str, "
            f"'banner_prompt': str, 'icon_prompt': str}}\n\n"
            f"ブランド情報: {brand_info}"
        )

        try:
            concept = self.claude.generate_json(concept_prompt)
        except Exception:
            concept = {
                "style": "modern minimalist",
                "colors": {"primary": "#1a1a2e", "secondary": "#16213e",
                           "accent": "#e94560", "background": "#f5f5f5"},
                "logo_prompt": f"minimalist logo for {brand_info}",
                "banner_prompt": f"professional banner for {brand_info}",
                "icon_prompt": f"simple icon set for {brand_info}",
            }

        result = {"logos": [], "banners": [], "icons": [], "palette": concept.get("colors", {})}

        # ロゴ生成（3案）
        logo_dir = output_dir / "logos"
        for i in range(3):
            logo_prompt = f"{concept.get('logo_prompt', brand_info)}, variation {i+1}, " \
                          f"clean white background, vector style"
            path = self.generate_image(
                prompt=logo_prompt,
                output_dir=logo_dir,
                filename=f"logo_{i+1:02d}",
                model=model,
                size=size,
                aspect_ratio="1:1",
                transparent=True,
            )
            if path:
                result["logos"].append(path)

        # バナー生成（2枚）
        banner_dir = output_dir / "banners"
        for i in range(2):
            banner_prompt = f"{concept.get('banner_prompt', brand_info)}, " \
                            f"{'web header' if i == 0 else 'social media cover'}"
            ratio = "16:9" if i == 0 else "3:1"
            path = self.generate_image(
                prompt=banner_prompt,
                output_dir=banner_dir,
                filename=f"banner_{i+1:02d}",
                model=model,
                size=size,
                aspect_ratio=ratio,
            )
            if path:
                result["banners"].append(path)

        # アイコン生成（5枚）
        icon_dir = output_dir / "icons"
        icon_types = ["home", "contact", "service", "about", "search"]
        for i, icon_type in enumerate(icon_types):
            icon_prompt = f"{concept.get('icon_prompt', 'simple icon')}, " \
                          f"{icon_type} icon, flat design, {concept.get('style', 'minimal')}"
            path = self.generate_image(
                prompt=icon_prompt,
                output_dir=icon_dir,
                filename=f"icon_{icon_type}",
                model="flash",  # アイコンはFlashで十分
                size="512",
                aspect_ratio="1:1",
                transparent=True,
            )
            if path:
                result["icons"].append(path)

        # カラーパレットをJSON保存
        palette_path = output_dir / "brand_palette.json"
        palette_path.write_text(
            json.dumps(concept, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return result

    def package_deliverables(self, order_id: str, output_dir: Path) -> Path:
        """納品物をZIPにパッケージング.

        Returns:
            ZIPファイルのパス
        """
        zip_path = output_dir.parent / f"{order_id}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(output_dir)
                    zf.write(file_path, arcname)

        logger.info("Packaged deliverables: %s (%.1f KB)", zip_path, zip_path.stat().st_size / 1024)
        return zip_path
