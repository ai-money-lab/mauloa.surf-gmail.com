"""AI美女コンテンツ生成パイプライン — Claudeから指示して運用する.

使い方（Claudeへの指示例）:
  「Mioのカフェ写真を5枚生成して」
  「Fanvue用のコンテンツを今週分まとめて作って」
  「FANZA用のCG集を50枚、OLシチュで作って」
  「Mioの投稿スケジュールを見せて」
  「新キャラを追加して」
"""

import json
import logging
import subprocess
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent.parent
BEAUTY_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "ai_beauty"


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _save_yaml(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


class CharacterManager:
    """キャラクター定義の管理."""

    def __init__(self):
        self.config_path = BEAUTY_DIR / "characters.yaml"
        self.config = _load_yaml(self.config_path)

    def list_characters(self) -> list[dict]:
        """登録済みキャラ一覧を返す."""
        chars = []
        for char_id, char in self.config.get("characters", {}).items():
            chars.append({
                "id": char_id,
                "name": char.get("name", char_id),
                "age": char.get("age"),
                "personality": char.get("personality", ""),
                "platforms": list(char.get("platforms", {}).keys()),
                "has_lora": bool(char.get("lora", {}).get("model_path")),
                "has_reference": bool(char.get("ip_adapter", {}).get("reference_image")),
            })
        return chars

    def get_character(self, char_id: str) -> Optional[dict]:
        """指定キャラの詳細を返す."""
        chars = self.config.get("characters", {})
        char = chars.get(char_id)
        if char:
            char["id"] = char_id
        return char

    def build_visual_prompt(self, char_id: str) -> str:
        """キャラのビジュアル情報をプロンプト文字列に変換."""
        char = self.get_character(char_id)
        if not char:
            return ""
        visual = char.get("visual", {})
        parts = []
        if visual.get("ethnicity"):
            parts.append(f"{visual['ethnicity']} woman")
        if char.get("age"):
            parts.append(f"{char['age']} years old")
        if visual.get("hair"):
            parts.append(visual["hair"])
        if visual.get("eyes"):
            parts.append(visual["eyes"])
        if visual.get("body_type"):
            parts.append(visual["body_type"])
        if visual.get("distinguishing"):
            parts.append(visual["distinguishing"])
        return ", ".join(parts)

    def add_character(self, char_id: str, char_data: dict):
        """新キャラを追加."""
        if "characters" not in self.config:
            self.config["characters"] = {}
        self.config["characters"][char_id] = char_data
        _save_yaml(self.config_path, self.config)
        logger.info("キャラクター '%s' を追加しました", char_id)

    def update_character(self, char_id: str, updates: dict):
        """既存キャラの設定を更新."""
        if char_id in self.config.get("characters", {}):
            self.config["characters"][char_id].update(updates)
            _save_yaml(self.config_path, self.config)
            logger.info("キャラクター '%s' を更新しました", char_id)


class PromptBuilder:
    """プロンプトテンプレートの組み立て."""

    def __init__(self):
        self.prompts_config = _load_yaml(BEAUTY_DIR / "prompts.yaml")
        self.char_manager = CharacterManager()

    def list_templates(self, category: Optional[str] = None) -> list[dict]:
        """利用可能なテンプレート一覧."""
        templates = []
        for tmpl_id, tmpl in self.prompts_config.get("templates", {}).items():
            if category and tmpl.get("category") != category:
                continue
            templates.append({
                "id": tmpl_id,
                "category": tmpl.get("category"),
                "description": tmpl.get("description"),
                "platforms": tmpl.get("platforms", []),
            })
        return templates

    def build_prompt(
        self,
        char_id: str,
        template_id: str,
        situation: str = "",
        extra: str = "",
    ) -> dict:
        """キャラ×テンプレートで完成プロンプトを生成.

        Returns:
            {"positive": str, "negative": str, "aspect_ratio": str}
        """
        quality = self.prompts_config.get("quality_base", {})
        template = self.prompts_config.get("templates", {}).get(template_id, {})
        char_visual = self.char_manager.build_visual_prompt(char_id)
        char = self.char_manager.get_character(char_id)
        char_style = char.get("default_style", "") if char else ""

        # テンプレートのプロンプトにキャラ情報を注入
        positive = template.get("positive", "").format(
            character_visual=char_visual,
            character_style=char_style,
            situation=situation,
        )

        # 品質ベース + テンプレート + 追加指定
        full_positive = f"{quality.get('positive', '')}, {positive}"
        if extra:
            full_positive += f", {extra}"

        return {
            "positive": full_positive.strip(", "),
            "negative": quality.get("negative", ""),
            "aspect_ratio": template.get("aspect_ratio", "3:4"),
        }

    def build_variations(
        self,
        char_id: str,
        template_id: str,
        count: int = 5,
        situation: str = "",
    ) -> list[dict]:
        """差分バリエーション付きプロンプトを複数生成."""
        variations_config = self.prompts_config.get("variations", {})
        expressions = variations_config.get("expressions", [])
        angles = variations_config.get("camera_angles", [])

        prompts = []
        for i in range(count):
            expr = expressions[i % len(expressions)] if expressions else ""
            angle = angles[i % len(angles)] if angles else ""
            extra = f"{expr}, {angle}".strip(", ")
            prompt = self.build_prompt(char_id, template_id, situation, extra)
            prompt["variation_index"] = i + 1
            prompts.append(prompt)
        return prompts


class ContentPipeline:
    """コンテンツ生成・管理パイプライン."""

    def __init__(self):
        self.char_manager = CharacterManager()
        self.prompt_builder = PromptBuilder()
        self.comfyui_config = _load_yaml(BEAUTY_DIR / "characters.yaml").get("comfyui", {})

    def generate_content(
        self,
        char_id: str,
        template_id: str,
        count: int = 1,
        situation: str = "",
        output_name: Optional[str] = None,
    ) -> dict:
        """コンテンツを生成.

        Returns:
            {"batch_id": str, "output_dir": str, "prompts": list, "status": str}
        """
        batch_id = f"{char_id}_{datetime.now(JST).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        output_dir = DATA_DIR / "generated" / char_id / batch_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # プロンプト生成
        if count == 1:
            prompts = [self.prompt_builder.build_prompt(char_id, template_id, situation)]
        else:
            prompts = self.prompt_builder.build_variations(char_id, template_id, count, situation)

        # プロンプトをJSONで保存（再現性のため）
        prompts_file = output_dir / "prompts.json"
        prompts_file.write_text(
            json.dumps(prompts, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # ComfyUI APIで生成を試みる
        generated = self._generate_via_comfyui(prompts, output_dir)

        if not generated:
            # フォールバック: nano-banana で生成
            generated = self._generate_via_nano_banana(prompts, output_dir)

        # バッチ記録を保存
        record = {
            "batch_id": batch_id,
            "character": char_id,
            "template": template_id,
            "count": count,
            "generated_count": len(generated),
            "output_dir": str(output_dir),
            "created_at": datetime.now(JST).isoformat(),
            "prompts": prompts,
            "files": [str(f) for f in generated],
            "status": "completed" if generated else "failed",
        }

        record_file = output_dir / "batch_record.json"
        record_file.write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # ログ追記
        self._append_log(record)

        return record

    def _generate_via_comfyui(self, prompts: list[dict], output_dir: Path) -> list[Path]:
        """ComfyUI API経由で画像生成."""
        host = self.comfyui_config.get("host", "127.0.0.1")
        port = self.comfyui_config.get("port", 8188)

        # ComfyUIが起動しているかチェック
        try:
            import urllib.request
            url = f"http://{host}:{port}/system_stats"
            req = urllib.request.Request(url, method="GET")
            urllib.request.urlopen(req, timeout=3)
        except Exception:
            logger.info("ComfyUI未起動。nano-bananaにフォールバック")
            return []

        # TODO: ComfyUI APIワークフロー実行の実装
        # 現時点ではプロンプトとワークフローJSONをキューに入れる仕組みを構築予定
        logger.info("ComfyUI APIでの生成は今後実装予定")
        return []

    def _generate_via_nano_banana(self, prompts: list[dict], output_dir: Path) -> list[Path]:
        """nano-banana CLI経由で画像生成（フォールバック）."""
        from monetize.asset_generator import AssetGenerator

        generator = AssetGenerator()
        generated = []

        for i, prompt_data in enumerate(prompts):
            positive = prompt_data.get("positive", "")
            aspect_ratio = prompt_data.get("aspect_ratio", "3:4")

            path = generator.generate_image(
                prompt=positive,
                output_dir=output_dir,
                filename=f"img_{i+1:03d}",
                model="flash",
                size="1K",
                aspect_ratio=aspect_ratio,
            )
            if path:
                generated.append(path)

        return generated

    def generate_fanvue_set(
        self,
        char_id: str,
        theme: str = "casual",
        count: int = 10,
    ) -> dict:
        """Fanvue投稿用のコンテンツセットを生成.

        SFWティーザー3枚 + NSFW本体を生成。
        """
        # テーマからテンプレートを自動選択
        template_map = {
            "casual": "street_snap",
            "cafe": "cafe",
            "morning": "morning_selfie",
            "bikini": "bikini_beach",
            "lingerie": "lingerie_bedroom",
            "fitness": "fitness",
            "office": "office",
        }
        template_id = template_map.get(theme, "cafe")

        return self.generate_content(
            char_id=char_id,
            template_id=template_id,
            count=count,
        )

    def generate_fanza_cg_set(
        self,
        char_id: str,
        situation: str,
        cover_count: int = 3,
        scene_count: int = 50,
    ) -> dict:
        """FANZA同人CG集を生成.

        表紙候補（cover_count枚）+ 本文シーン（scene_count枚）
        """
        batch_id = f"fanza_{char_id}_{datetime.now(JST).strftime('%Y%m%d_%H%M%S')}"
        output_dir = DATA_DIR / "generated" / char_id / batch_id
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {"covers": [], "scenes": [], "batch_id": batch_id, "output_dir": str(output_dir)}

        # 表紙候補を生成
        cover_prompts = self.prompt_builder.build_variations(
            char_id, "fanza_cover", cover_count, situation,
        )
        for i, p in enumerate(cover_prompts):
            p_file = output_dir / "covers"
            p_file.mkdir(exist_ok=True)
            # 保存のみ（実際の生成はComfyUI/nano-banana）
            results["covers"].append(p)

        # 本文シーンを生成
        scene_prompts = self.prompt_builder.build_variations(
            char_id, "fanza_scene", scene_count, situation,
        )
        for i, p in enumerate(scene_prompts):
            results["scenes"].append(p)

        # プロンプトを保存
        prompts_file = output_dir / "all_prompts.json"
        prompts_file.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return results

    def _append_log(self, record: dict):
        """生成ログをJSONLで追記."""
        log_dir = DATA_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{datetime.now(JST).strftime('%Y-%m')}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


class PostScheduler:
    """投稿スケジュール管理."""

    def __init__(self):
        self.schedule_dir = DATA_DIR / "schedules"
        self.schedule_dir.mkdir(parents=True, exist_ok=True)

    def create_weekly_schedule(
        self,
        char_id: str,
        platform: str,
        posts_per_day: int = 3,
    ) -> dict:
        """週間投稿スケジュールを生成.

        Returns:
            {"week": str, "schedule": [{"day": str, "posts": [...]}]}
        """
        days = ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"]
        # プラットフォーム別の投稿時間
        post_times = {
            "x_twitter": ["07:30", "12:15", "20:30", "22:00"],
            "instagram": ["08:00", "12:00", "19:00"],
            "fanvue": ["10:00", "15:00", "21:00"],
        }
        times = post_times.get(platform, ["09:00", "15:00", "21:00"])

        # テンプレートのローテーション
        sfw_templates = ["cafe", "street_snap", "morning_selfie", "office", "fitness"]
        nsfw_templates = ["bikini_beach", "lingerie_bedroom"]

        schedule = []
        template_idx = 0
        for day in days:
            day_posts = []
            for i in range(min(posts_per_day, len(times))):
                if platform in ("x_twitter", "instagram"):
                    tmpl = sfw_templates[template_idx % len(sfw_templates)]
                else:
                    tmpl = nsfw_templates[template_idx % len(nsfw_templates)]
                template_idx += 1

                day_posts.append({
                    "time": times[i],
                    "template": tmpl,
                    "type": "image_set" if i == 0 else "single",
                    "count": 4 if i == 0 else 1,
                })
            schedule.append({"day": day, "posts": day_posts})

        week_str = datetime.now(JST).strftime("%Y-W%W")
        result = {
            "character": char_id,
            "platform": platform,
            "week": week_str,
            "schedule": schedule,
        }

        # 保存
        schedule_file = self.schedule_dir / f"{char_id}_{platform}_{week_str}.json"
        schedule_file.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return result

    def get_today_tasks(self, char_id: str) -> list[dict]:
        """今日のタスク一覧を返す."""
        today = datetime.now(JST)
        day_names = ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"]
        today_name = day_names[today.weekday()]

        tasks = []
        for f in sorted(self.schedule_dir.glob(f"{char_id}_*.json")):
            schedule_data = json.loads(f.read_text(encoding="utf-8"))
            for day_entry in schedule_data.get("schedule", []):
                if day_entry["day"] == today_name:
                    for post in day_entry.get("posts", []):
                        tasks.append({
                            "character": char_id,
                            "platform": schedule_data["platform"],
                            **post,
                        })
        return tasks


# ─── Claudeから呼び出すための簡易インターフェース ───

def show_characters() -> str:
    """キャラ一覧を表示."""
    mgr = CharacterManager()
    chars = mgr.list_characters()
    if not chars:
        return "キャラクターが未登録です。characters.yaml にキャラを追加してください。"
    lines = ["## 登録キャラクター一覧\n"]
    for c in chars:
        lora_status = "LoRA済" if c["has_lora"] else "未学習"
        ref_status = "参照画像あり" if c["has_reference"] else "なし"
        lines.append(
            f"- **{c['name']}** (id: `{c['id']}`) | "
            f"年齢: {c['age']} | {lora_status} | {ref_status} | "
            f"プラットフォーム: {', '.join(c['platforms'])}"
        )
    return "\n".join(lines)


def show_templates(category: Optional[str] = None) -> str:
    """テンプレート一覧を表示."""
    builder = PromptBuilder()
    templates = builder.list_templates(category)
    lines = ["## プロンプトテンプレート一覧\n"]
    for t in templates:
        lines.append(
            f"- **{t['id']}** [{t['category']}] | "
            f"{t['description']} | "
            f"対象: {', '.join(t['platforms'])}"
        )
    return "\n".join(lines)


def generate(
    char_id: str,
    template_id: str,
    count: int = 1,
    situation: str = "",
) -> str:
    """コンテンツを生成して結果を返す."""
    pipeline = ContentPipeline()
    result = pipeline.generate_content(char_id, template_id, count, situation)
    return (
        f"## 生成完了\n\n"
        f"- バッチID: `{result['batch_id']}`\n"
        f"- キャラ: {char_id}\n"
        f"- テンプレート: {template_id}\n"
        f"- 生成数: {result['generated_count']}/{count}\n"
        f"- 出力先: `{result['output_dir']}`\n"
        f"- ステータス: {result['status']}"
    )


def generate_fanvue(char_id: str, theme: str = "casual", count: int = 10) -> str:
    """Fanvue用コンテンツセットを生成."""
    pipeline = ContentPipeline()
    result = pipeline.generate_fanvue_set(char_id, theme, count)
    return (
        f"## Fanvueコンテンツ生成完了\n\n"
        f"- バッチID: `{result['batch_id']}`\n"
        f"- テーマ: {theme}\n"
        f"- 生成数: {result['generated_count']}/{count}\n"
        f"- 出力先: `{result['output_dir']}`"
    )


def generate_fanza(char_id: str, situation: str, scene_count: int = 50) -> str:
    """FANZA CG集を生成."""
    pipeline = ContentPipeline()
    result = pipeline.generate_fanza_cg_set(char_id, situation, scene_count=scene_count)
    return (
        f"## FANZA CG集プロンプト生成完了\n\n"
        f"- バッチID: `{result['batch_id']}`\n"
        f"- シチュエーション: {situation}\n"
        f"- 表紙候補: {len(result['covers'])}枚\n"
        f"- 本文シーン: {len(result['scenes'])}枚\n"
        f"- 出力先: `{result['output_dir']}`\n\n"
        f"ComfyUIでワークフローを実行してください。"
    )


def show_schedule(char_id: str) -> str:
    """今日のタスクを表示."""
    scheduler = PostScheduler()
    tasks = scheduler.get_today_tasks(char_id)
    if not tasks:
        return f"{char_id}の今日のスケジュールはありません。`create_schedule`で作成してください。"
    lines = [f"## {char_id} の今日のタスク\n"]
    for t in tasks:
        lines.append(f"- {t['time']} | {t['platform']} | {t['template']} | {t['type']}（{t.get('count', 1)}枚）")
    return "\n".join(lines)


def create_schedule(char_id: str, platform: str, posts_per_day: int = 3) -> str:
    """週間スケジュールを作成."""
    scheduler = PostScheduler()
    result = scheduler.create_weekly_schedule(char_id, platform, posts_per_day)
    return (
        f"## 週間スケジュール作成完了\n\n"
        f"- キャラ: {char_id}\n"
        f"- プラットフォーム: {platform}\n"
        f"- 週: {result['week']}\n"
        f"- 投稿数/日: {posts_per_day}"
    )
