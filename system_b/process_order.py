"""System B - TASK B-3: 案件処理パイプライン

受注→データ収集→レポート生成→品質チェック→PDF→納品の完全自動フロー。
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env", override=True)

import yaml

from core.claude_client import ClaudeClient
from core.quality_checker import QualityChecker
from core.sheets_client import SheetsClient
from core.notifier import Notifier
from core.pdf_generator import PDFGenerator
from system_c.agents.realestate_data_agent import RealEstateDataAgent
from system_c.agents.market_analysis_agent import MarketAnalysisAgent
from system_c.agents.regulation_watch_agent import RegulationWatchAgent
from system_c.agents.tech_trend_agent import TechTrendAgent

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
PRODUCTS_PATH = BASE_DIR / "system_b" / "products.yaml"
DELIVERABLES_DIR = BASE_DIR / "data" / "system_b" / "deliverables"


def load_products() -> dict:
    with open(PRODUCTS_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {p["id"]: p for p in data.get("products", [])}


class OrderProcessor:
    """案件処理パイプライン"""

    def __init__(self):
        self.products = load_products()
        self.claude = ClaudeClient()
        self.quality_checker = QualityChecker()
        self.sheets = SheetsClient()
        self.notifier = Notifier()
        self.pdf_gen = PDFGenerator()

    def process(self, order: dict) -> dict:
        """案件を完全自動処理"""
        order_id = order["order_id"]
        product_id = order["product_id"]
        logger.info(f"Processing order: {order_id} (product: {product_id})")

        product = self.products.get(product_id)
        if not product:
            raise ValueError(f"Unknown product: {product_id}")

        result = {
            "order_id": order_id,
            "product_id": product_id,
            "status": "processing",
            "started_at": datetime.now(JST).isoformat(),
        }

        # Step 1: 案件登録
        if self.sheets.available:
            self.sheets.append_order_record(order)

        # Step 2: データ収集（System C呼び出し）
        collected_data = self._collect_data(order, product)

        # Step 3: データ品質チェック
        if collected_data:
            data_quality = self.quality_checker.check(
                profile="data_collection",
                content=json.dumps(collected_data, ensure_ascii=False),
                context=f"order_{order_id}",
            )
            if data_quality.result != "auto_approved":
                logger.warning(f"Data quality low: {data_quality.total_score}")

        # Step 4: レポート生成
        report_md = self._generate_report(order, product, collected_data)

        # Step 5: プロフェッショナル所見生成
        insight = self._generate_insight(order, collected_data, report_md)
        report_md += f"\n\n## プロフェッショナル所見\n\n{insight}"

        # Step 6: レポート品質チェック（リトライ付き）
        quality_result, final_report = self.quality_checker.check_with_retry(
            profile="report",
            content=report_md,
            context=f"order_{order_id}_report",
            regenerate_fn=lambda content, suggestions: self._improve_report(
                content, suggestions, order, product, collected_data
            ),
        )

        if quality_result.result == "escalated":
            self.notifier.notify(
                f"⚠️ 案件 {order_id} のレポート品質が基準未達です。手動確認してください。",
                urgent=True,
            )
            result["status"] = "escalated"
            return result

        # Step 7: PDF生成
        output_path = self._generate_pdf(order, product, final_report)
        result["deliverable_path"] = output_path

        # Step 8: ステータス更新
        result["status"] = "delivered"
        result["completed_at"] = datetime.now(JST).isoformat()
        result["quality_score"] = quality_result.total_score

        if self.sheets.available:
            self.sheets.update_order_status(order_id, "delivered")

        # Step 9: 通知
        self.notifier.notify(
            f"案件 {order_id} の納品が完了しました\n"
            f"商品: {product['name']}\n"
            f"品質スコア: {quality_result.total_score}"
        )

        logger.info(f"Order {order_id} completed successfully")
        return result

    def _collect_data(self, order: dict, product: dict) -> dict:
        """System Cのエージェントにデータ収集を依頼（リアルタイムAPI経由）"""
        crew_tasks = product.get("crew_tasks", [])
        if not crew_tasks:
            return {}

        params = order.get("parameters", {})
        product_id = product["id"]
        collected = {}

        try:
            # エリア情報を抽出（住所から）
            area = params.get("property_address", "") or params.get("area", "東京都")

            # ── 商品別に適切なエージェントを呼び出し ──

            if product_id in ("tier1_area_analysis", "tier2_sell_strategy"):
                # エリア分析 / 売却戦略 → 不動産データエージェント + 市場分析エージェント
                logger.info(f"[System C] エリア分析データ収集: {area}")
                re_agent = RealEstateDataAgent()
                collected["area_data"] = re_agent.collect_area_data(area, params)

                market_agent = MarketAnalysisAgent()
                collected["market_analysis"] = market_agent.analyze_market(
                    area, collected["area_data"]
                )

            elif product_id == "tier2_rental_valuation":
                # 賃料査定 → 不動産データエージェント（賃料特化）
                logger.info(f"[System C] 賃料データ収集: {area}")
                re_agent = RealEstateDataAgent()
                collected["rental_data"] = re_agent.collect_rental_data(
                    area,
                    property_type=params.get("property_type", ""),
                    params=params,
                )
                # 地価データも補完
                collected["area_data"] = re_agent.collect_area_data(area, params)

            elif product_id == "tier2_renovation_cost":
                # リフォーム費用 → 不動産データエージェント（リフォーム特化）
                logger.info(f"[System C] リフォーム費用データ収集")
                re_agent = RealEstateDataAgent()
                work_type = params.get("work_type", "全般")
                collected["renovation_data"] = re_agent.collect_renovation_costs(
                    work_type, area, params
                )

            elif product_id == "tier1_dx_consulting":
                # DXコンサル → テックトレンドエージェント
                logger.info("[System C] テクノロジートレンド収集")
                tech_agent = TechTrendAgent()
                collected["tech_trends"] = tech_agent.collect_weekly_trends()
                collected["matterport"] = tech_agent.collect_matterport_updates()

            elif product_id == "tier3_market_newsletter":
                # ニュースレター → 市場分析 + 法規制 + テックトレンド
                logger.info("[System C] ニュースレターデータ収集")
                market_agent = MarketAnalysisAgent()
                collected["daily_market"] = market_agent.daily_market_watch()

                reg_agent = RegulationWatchAgent()
                collected["regulations"] = reg_agent.check_regulations()

                tech_agent = TechTrendAgent()
                collected["tech_trends"] = tech_agent.collect_weekly_trends()

            else:
                # その他 → Claude APIフォールバック
                logger.info(f"[System C] フォールバック: Claude APIでデータ生成")
                prompt = (
                    f"以下のパラメータに基づき、{product['name']}に必要なデータを"
                    f"JSON形式で生成してください。\n\n"
                    f"パラメータ: {json.dumps(params, ensure_ascii=False)}\n"
                    f"必要データ: {json.dumps(product.get('deliverables', []), ensure_ascii=False)}"
                )
                collected = self.claude.generate_json(prompt, max_tokens=4096)

            # メタ情報を付加
            collected["_meta"] = {
                "collection_method": "system_c_realtime_api",
                "collected_at": datetime.now(JST).isoformat(),
                "product_id": product_id,
                "crew_tasks": crew_tasks,
            }

            logger.info(f"Data collection completed for {product_id}")
            return collected

        except Exception as e:
            logger.error(f"Data collection failed: {e}")
            # フォールバック: Claude APIで補完
            logger.info("Falling back to Claude API for data generation")
            try:
                fallback_prompt = (
                    f"以下のパラメータに基づき、{product['name']}に必要なデータを"
                    f"JSON形式で生成してください。\n"
                    f"最新の市場データに基づいてください。\n\n"
                    f"パラメータ: {json.dumps(params, ensure_ascii=False)}"
                )
                return self.claude.generate_json(fallback_prompt, max_tokens=4096)
            except Exception as fallback_err:
                logger.error(f"Fallback also failed: {fallback_err}")
                return {}

    def _generate_report(self, order: dict, product: dict, data: dict) -> str:
        """レポート本文を生成"""
        prompt = self.claude.load_prompt(
            "generate_report.txt",
            report_type=product["name"],
            template_name=product["template"],
            client_name=order.get("client_name", ""),
            collected_data=json.dumps(data, ensure_ascii=False, indent=2),
        )

        return self.claude.generate(prompt, max_tokens=8192, temperature=0.5)

    def _generate_insight(self, order: dict, data: dict, report: str) -> str:
        """プロフェッショナル所見を生成"""
        prompt = self.claude.load_prompt(
            "professional_insight.txt",
            report_summary=report[:2000],
            analysis_data=json.dumps(data, ensure_ascii=False)[:3000],
        )

        return self.claude.generate(prompt, max_tokens=2048, temperature=0.6)

    def _improve_report(
        self, content: str, suggestions: list[str], order: dict, product: dict, data: dict
    ) -> str:
        """品質不足時にレポートを改善"""
        suggestions_text = "\n".join(f"- {s}" for s in suggestions)
        prompt = (
            f"以下のレポートを改善してください。\n\n"
            f"## 改善提案:\n{suggestions_text}\n\n"
            f"## 現在のレポート:\n{content}"
        )
        return self.claude.generate(prompt, max_tokens=8192, temperature=0.5)

    def _generate_pdf(self, order: dict, product: dict, report_md: str) -> str:
        """PDF生成"""
        DELIVERABLES_DIR.mkdir(parents=True, exist_ok=True)
        order_id = order["order_id"]
        date_str = datetime.now(JST).strftime("%Y%m%d")
        output_path = DELIVERABLES_DIR / f"{order_id}_{date_str}.pdf"

        return self.pdf_gen.generate_pdf(report_md, str(output_path))


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--order", required=True, help="Path to order JSON file")
    args = parser.parse_args()

    with open(args.order, "r", encoding="utf-8") as f:
        order = json.load(f)

    processor = OrderProcessor()
    result = processor.process(order)
    print(f"Order processed: {json.dumps(result, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
