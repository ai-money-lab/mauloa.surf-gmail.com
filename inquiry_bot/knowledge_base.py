"""ナレッジベース管理 — FAQ検索・物件データ管理."""

import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

FAQ_DATA_PATH = Path(__file__).parent / "faq_data.yaml"


class KnowledgeBase:
    """FAQデータと物件情報を管理し、問い合わせに適した回答を検索する."""

    def __init__(self, faq_path: Optional[Path] = None, property_data: Optional[dict] = None):
        self.faq_path = faq_path or FAQ_DATA_PATH
        self.faq_data = self._load_faq()
        self.company = self.faq_data.get("company", {})
        self.faqs = self.faq_data.get("faq", [])
        # 物件データ（外部DB/スプレッドシートから取得する想定）
        self.property_data = property_data or {}

    def _load_faq(self) -> dict:
        try:
            return yaml.safe_load(self.faq_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("FAQ data load failed: %s", e)
            return {"company": {}, "faq": []}

    def search_faq(self, query: str) -> list[dict]:
        """クエリに一致するFAQを検索（パターンマッチング）."""
        query_lower = query.lower()
        results = []
        for faq in self.faqs:
            score = 0
            for pattern in faq.get("patterns", []):
                if pattern in query_lower:
                    score += 10  # 完全一致
                elif any(char in query_lower for char in pattern if len(char) > 1):
                    score += 3  # 部分一致
            if score > 0:
                results.append({"faq": faq, "score": score})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def get_faq_context(self, category: Optional[str] = None) -> str:
        """AI用にFAQデータをコンテキスト文字列として整形."""
        faqs = self.faqs
        if category:
            faqs = [f for f in faqs if f.get("category") == category]

        lines = []
        for faq in faqs:
            lines.append(f"### {faq['id']} ({faq['category']})")
            lines.append(f"質問パターン: {', '.join(faq['patterns'])}")
            lines.append(f"回答テンプレート:\n{faq['answer']}")
            lines.append("")
        return "\n".join(lines)

    def get_property_info(self, property_id: str) -> dict:
        """物件IDから物件情報を取得."""
        return self.property_data.get(property_id, {})

    def get_all_properties_summary(self) -> str:
        """全物件の概要をテキストで返す（AIコンテキスト用）."""
        if not self.property_data:
            return "※ 物件データが未登録です。具体的な物件情報は担当者に確認してください。"

        lines = []
        for pid, info in self.property_data.items():
            name = info.get("name", pid)
            rent = info.get("rent", "未設定")
            status = info.get("vacancy_status", "不明")
            lines.append(f"- {name} (ID: {pid}): 賃料 {rent}円, 空室: {status}")
        return "\n".join(lines)

    def fill_template(self, template: str, data: dict) -> str:
        """テンプレート内の変数を実データで置換."""
        result = template
        # 会社情報で置換
        for key, value in self.company.items():
            result = result.replace(f"{{{key}}}", str(value))
            result = result.replace(f"{{company_{key}}}", str(value))
        # 物件データで置換
        for key, value in data.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    def update_property_data(self, property_id: str, data: dict) -> None:
        """物件データを更新（外部連携用）."""
        self.property_data[property_id] = data
        logger.info("Property data updated: %s", property_id)

    def load_properties_from_yaml(self, path: Path) -> None:
        """YAMLファイルから物件データを読み込み."""
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.property_data = data.get("properties", {})
            logger.info("Loaded %d properties from %s", len(self.property_data), path)
        except Exception as e:
            logger.error("Property data load failed: %s", e)
