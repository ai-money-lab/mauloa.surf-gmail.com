"""Theme rotation engine for Pipeline 3.

Manages sub-themes across 5 pillars, tracks usage history,
and ensures no repetition within configurable windows.
"""

import json
import logging
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "system_a"
THEME_DB_PATH = DATA_DIR / "theme_db.json"
POST_HISTORY_PATH = DATA_DIR / "post_history.json"
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"

DEFAULT_THEME_DB = {
    "pillars": {
        "1": {
            "name": "不動産の裏側",
            "sub_themes": [
                "仲介手数料の仕組み", "広告料の闇", "おとり物件の実態",
                "重説で見落とされがちなポイント", "事故物件の告知義務",
                "管理会社の選び方", "大家と管理会社の力関係",
                "内見で見るべきポイント", "築年数の本当の意味",
                "特殊清掃の現場から見える賃貸の現実",
                "孤独死が起きた物件のその後",
                "遺品整理で大家が知っておくべきこと",
                "原状回復と特殊清掃の境界線",
                "施工コーディネーターという仕事",
                "職人と依頼主の間で見えること",
            ],
        },
        "2": {
            "name": "住環境・暮らしの知恵",
            "sub_themes": [
                "間取りの読み方", "リフォームで価値が上がる工事ベスト5",
                "引っ越しの裏技", "賃貸の退去費用トラブル",
                "防音対策", "結露対策", "収納の最適化",
                "住宅設備のコスパランキング",
                "プロが見る退去時クリーニングの基準",
                "ハウスクリーニングの適正相場",
                "防犯カメラの選び方と設置のポイント",
                "一人暮らしの防犯対策",
            ],
        },
        "3": {
            "name": "お金・資産・不動産投資",
            "sub_themes": [
                "利回りの罠", "空室リスクの計算方法",
                "築古vs新築の投資効率", "エリア選定の鉄則",
                "ローンの組み方", "繰り上げ返済の判断基準",
                "売却タイミングの見極め",
            ],
        },
        "4": {
            "name": "経営者の日常",
            "sub_themes": [
                "平日サーフィンのルーティン", "サーフィンと経営の共通点",
                "3kgの犬との生活", "コーデックス栽培の哲学",
                "ジム立ち上げの裏側",
                "ベンチプレス世界チャンピオンから学んだこと",
                "46歳の体づくり", "経営者の時間管理",
            ],
        },
        "5": {
            "name": "テクノロジー×不動産",
            "sub_themes": [
                "MATTERPORTの活用事例", "VR内見の成約率データ",
                "AI×不動産の未来予測", "不動産DXの現在地",
                "ChatGPTを業務で使ってみた結果",
                "自動化で変わった仕事",
                "AI防犯カメラの最前線",
                "顔認証・動体検知・クラウド録画の進化",
                "AI防犯カメラ×不動産管理の可能性",
                "空き家管理へのテック活用",
            ],
        },
    }
}


class ThemeRotator:
    """Manage theme rotation across 5 pillars with dedup."""

    def __init__(self):
        self._load_config()
        self._load_theme_db()
        self._load_post_history()

    def _load_config(self):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            p3_cfg = cfg.get("system_a", {}).get("pipeline3", {})
            self.overlap_check_days = p3_cfg.get("theme_overlap_check_days", 30)
            self.max_same_per_month = p3_cfg.get("max_same_sub_theme_per_month", 2)
        except Exception:
            self.overlap_check_days = 30
            self.max_same_per_month = 2

    def _load_theme_db(self):
        if THEME_DB_PATH.exists():
            self.theme_db = json.loads(THEME_DB_PATH.read_text(encoding="utf-8"))
        else:
            self.theme_db = DEFAULT_THEME_DB
            self._save_theme_db()

    def _save_theme_db(self):
        THEME_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        THEME_DB_PATH.write_text(
            json.dumps(self.theme_db, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_post_history(self):
        if POST_HISTORY_PATH.exists():
            self.post_history = json.loads(POST_HISTORY_PATH.read_text(encoding="utf-8"))
        else:
            self.post_history = []
            self._save_post_history()

    def _save_post_history(self):
        POST_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        POST_HISTORY_PATH.write_text(
            json.dumps(self.post_history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_recent_themes(self) -> set:
        """Get themes used within the overlap check window."""
        cutoff = datetime.now(JST) - timedelta(days=self.overlap_check_days)
        cutoff_str = cutoff.isoformat()
        recent = set()
        for entry in self.post_history:
            if entry.get("date", "") >= cutoff_str:
                recent.add(entry.get("sub_theme", ""))
        return recent

    def select_theme(self, target_pillar: int = None) -> dict:
        """Select next theme avoiding recent duplicates.

        Args:
            target_pillar: If specified, select from this pillar only.

        Returns:
            Dict with pillar_number, pillar_name, sub_theme.
        """
        recent = self.get_recent_themes()
        pillars = self.theme_db.get("pillars", {})

        candidates = []
        for p_num, p_data in pillars.items():
            if target_pillar and int(p_num) != target_pillar:
                continue
            for theme in p_data["sub_themes"]:
                if theme not in recent:
                    candidates.append({
                        "pillar_number": int(p_num),
                        "pillar_name": p_data["name"],
                        "sub_theme": theme,
                    })

        if not candidates:
            # All themes used recently, reset and pick any
            logger.warning("All themes used recently, selecting from full pool")
            for p_num, p_data in pillars.items():
                if target_pillar and int(p_num) != target_pillar:
                    continue
                for theme in p_data["sub_themes"]:
                    candidates.append({
                        "pillar_number": int(p_num),
                        "pillar_name": p_data["name"],
                        "sub_theme": theme,
                    })

        selected = random.choice(candidates) if candidates else None
        return selected

    def record_usage(self, pillar_number: int, sub_theme: str) -> None:
        """Record that a theme was used."""
        self.post_history.append({
            "date": datetime.now(JST).isoformat(),
            "pillar_number": pillar_number,
            "sub_theme": sub_theme,
        })
        self._save_post_history()

    def prioritize_winning_themes(self, winning_patterns: list) -> None:
        """Boost themes related to winning patterns."""
        # This adjusts the theme DB to prioritize adjacent themes
        # to those that performed well
        pass  # Extended in analyze_performance.py feedback loop


def initialize_theme_db():
    """Create the initial theme DB file."""
    THEME_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    THEME_DB_PATH.write_text(
        json.dumps(DEFAULT_THEME_DB, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    POST_HISTORY_PATH.write_text("[]", encoding="utf-8")
    logger.info("Theme DB initialized at %s", THEME_DB_PATH)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    initialize_theme_db()
