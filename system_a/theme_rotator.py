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
            "name": "売却・相続の判断と進め方",
            "target": "物件を売りたい人、相続してどうすればいいかわからない人、売却せざるを得ない人",
            "ratio": 35,
            "sub_themes": [
                "相続した不動産、まず何をすべきか",
                "売却の流れと一般的なスケジュール",
                "査定額と実際の売却価格のギャップ",
                "売却時の不動産会社の選び方",
                "仲介と買取の違いと判断基準",
                "相続登記の義務化で知っておくべきこと",
                "空き家を持ち続けるリスクと選択肢",
                "売却時の税金の基礎知識",
                "築古物件・古家付き土地の売り方",
                "離婚・転勤など売却せざるを得ないときの進め方",
                "共有名義の不動産の売却方法",
                "売却前にリフォームすべきかの判断基準",
                "相続放棄すべきかの判断ポイント",
                "遠方の実家を相続したときの現実的な選択肢",
            ],
        },
        "2": {
            "name": "賃貸オーナーの物件管理",
            "target": "物件を持っている人、賃貸経営をしている人",
            "ratio": 25,
            "sub_themes": [
                "空室が埋まらないときの具体的な打ち手",
                "管理会社の選び方と変更の判断基準",
                "適正家賃の設定方法",
                "入居審査で見るべきポイント",
                "リフォーム投資で回収できる工事とできない工事",
                "物件の防犯対策が入居率に与える影響",
                "防犯カメラ導入で変わった管理の現場",
                "孤独死・事故物件になったときの現実的な対応",
                "特殊清掃が必要になったときの手順と費用感",
                "遺品整理の流れとオーナーが知っておくべきこと",
                "原状回復とクリーニングの判断基準",
                "MATTERPORT等テクノロジーで管理を効率化する方法",
            ],
        },
        "3": {
            "name": "部屋探し・住まいの知恵",
            "target": "部屋を探している人、今の住まいで困っている人",
            "ratio": 20,
            "sub_themes": [
                "おとり物件の見分け方",
                "内見で本当に確認すべきポイント",
                "退去費用の相場とぼったくり防止",
                "仲介手数料の仕組みと相場",
                "騒音問題の相談先と現実的な解決策",
                "結露・カビの原因と根本的な対策",
                "一人暮らしの防犯対策で本当に効果があること",
                "原状回復ガイドラインの読み方",
                "良い不動産会社・担当者の見分け方",
                "管理会社が動いてくれないときの対処法",
            ],
        },
        "4": {
            "name": "住まいとお金の判断軸",
            "target": "住宅購入・不動産投資を検討している人",
            "ratio": 10,
            "sub_themes": [
                "賃貸vs持ち家の判断基準",
                "不動産投資の利回りの正しい読み方",
                "エリア選びで失敗しないためのチェックポイント",
                "住宅ローンの基礎と無理のない返済計画",
                "売却タイミングの見極め方",
                "築古物件のリスクと見極め方",
                "中古マンション選びで後悔しないポイント",
            ],
        },
        "5": {
            "name": "現場から見える景色",
            "target": "HIROKIの人となりを知りたい人、不動産業界に興味がある人",
            "ratio": 10,
            "sub_themes": [
                "不動産の仕事の中で気づいたこと",
                "サーフィンが教えてくれる仕事との向き合い方",
                "愛犬KOAとの日常",
                "B.A.D GYMの立ち上げで学んでいること",
                "MATTERPORTやAIを現場で使ってみた実感",
                "施工コーディネーターという仕事の裏側",
                "経営者として大事にしていること",
                "コーデックス栽培と時間の使い方",
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
