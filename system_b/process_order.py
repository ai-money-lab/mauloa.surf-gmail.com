"""Order processing pipeline for System B.

Handles the full flow from order intake to delivery:
order → data collection → report generation → quality check → PDF → delivery.
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv

from core.claude_client import ClaudeClient
from core.quality_checker import QualityChecker
from core.pdf_generator import PDFGenerator
from core.sheets_client import SheetsClient
from core.notifier import Notifier

load_dotenv()

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
PRODUCTS_PATH = Path(__file__).parent / "products.yaml"
DELIVERABLES_DIR = BASE_DIR / "data" / "system_b" / "deliverables"
PROMPTS_DIR = BASE_DIR / "prompts"


class OrderProcessor:
    """Process orders end-to-end."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.quality_checker = QualityChecker(self.claude)
        self.pdf_gen = PDFGenerator()
        self.sheets = SheetsClient()
        self.notifier = Notifier()
        self._load_products()

    def _load_products(self):
        with open(PRODUCTS_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.products = {p["id"]: p for p in data.get("products", [])}

    def _get_product(self, product_id: str) -> dict:
        if product_id not in self.products:
            raise ValueError(f"Unknown product: {product_id}")
        return self.products[product_id]

    def _collect_data(self, product: dict, params: dict) -> dict:
        """Trigger System C agents to collect required data."""
        crew_tasks = product.get("crew_tasks", [])
        collected = {}

        for task_name in crew_tasks:
            data_dir = BASE_DIR / "data" / "system_c"
            # Look for existing data or trigger collection
            for subdir in ["reports", "daily", "weekly", "valuations", "costs"]:
                task_dir = data_dir / subdir
                if task_dir.exists():
                    files = sorted(task_dir.glob(f"{task_name}*.json"), reverse=True)
                    if files:
                        try:
                            collected[task_name] = json.loads(
                                files[0].read_text(encoding="utf-8")
                            )
                        except Exception as e:
                            logger.warning("Failed to load %s data: %s", task_name, e)

        # If no data from System C, generate via Claude
        if not collected:
            logger.info("No System C data available, generating via Claude API")
            prompt = (
                f"指定された条件に基づき、レポート用のデータを生成してください。\n"
                f"商品: {product['name']}\n"
                f"パラメータ: {json.dumps(params, ensure_ascii=False)}\n"
                f"JSON形式で出力してください。"
            )
            try:
                collected["ai_generated"] = self.claude.generate_json(prompt)
            except Exception as e:
                logger.error("Data generation failed: %s", e)

        # Quality check collected data
        for key, data in collected.items():
            result = self.quality_checker.check(
                profile="data_collection",
                content=json.dumps(data, ensure_ascii=False),
                context=f"Order data collection: {key}",
            )
            if result.get("result") != "auto_approved":
                logger.warning("Data quality check failed for %s: %s", key, result)

        return collected

    def _generate_report(self, product: dict, params: dict, data: dict) -> str:
        """Generate report content from template and data."""
        report_prompt_path = PROMPTS_DIR / "generate_report.txt"
        report_prompt = report_prompt_path.read_text(encoding="utf-8")

        prompt = report_prompt.replace(
            "{report_type}", product["name"]
        ).replace(
            "{variables}", json.dumps(params, ensure_ascii=False)
        ).replace(
            "{collected_data}", json.dumps(data, ensure_ascii=False)
        )

        report_content = self.claude.generate(prompt, temperature=0.5)
        return report_content

    def _generate_insight(self, report_summary: str, params: dict) -> str:
        """Generate professional insight section."""
        insight_prompt_path = PROMPTS_DIR / "professional_insight.txt"
        insight_prompt = insight_prompt_path.read_text(encoding="utf-8")

        prompt = insight_prompt.replace(
            "{report_summary}", report_summary[:2000]
        ).replace(
            "{target}", json.dumps(params, ensure_ascii=False)
        ).replace(
            "{key_data}", ""
        )

        return self.claude.generate(prompt, temperature=0.6)

    def process(self, order: dict) -> dict:
        """Process a single order end-to-end.

        Args:
            order: Dict with order_id, product_id, client_name,
                   parameters, deadline, platform.

        Returns:
            Dict with delivery status and file path.
        """
        order_id = order["order_id"]
        product_id = order["product_id"]
        params = order.get("parameters", {})
        product = self._get_product(product_id)

        logger.info("Processing order %s: %s", order_id, product["name"])

        # Step 1: Register order
        try:
            self.sheets.record_order({
                **order,
                "status": "processing",
                "created_at": datetime.now(JST).isoformat(),
            })
        except Exception as e:
            logger.warning("Failed to record order to Sheets: %s", e)

        # Step 2: Collect data
        logger.info("[%s] Collecting data...", order_id)
        collected_data = self._collect_data(product, params)

        # Step 3: Generate report
        logger.info("[%s] Generating report...", order_id)
        report_content = self._generate_report(product, params, collected_data)

        # Step 4: Generate professional insight
        logger.info("[%s] Generating professional insight...", order_id)
        insight = self._generate_insight(report_content[:2000], params)
        full_report = f"{report_content}\n\n## プロフェッショナル所見\n\n{insight}"

        # Step 5: Quality check report
        logger.info("[%s] Quality checking report...", order_id)
        report_text, quality_result = self.quality_checker.check_with_retry(
            profile="report",
            content=full_report,
            context=f"Order {order_id}: {product['name']}",
        )

        if quality_result.get("result") == "escalated":
            self.notifier.send_line(
                f"案件 {order_id} の品質チェックが失敗しました。手動確認が必要です。"
            )
            return {"order_id": order_id, "status": "escalated"}

        # Step 6: Generate PDF
        logger.info("[%s] Generating PDF...", order_id)
        output_dir = DELIVERABLES_DIR / order_id
        output_dir.mkdir(parents=True, exist_ok=True)

        template_name = product.get("template", "area_analysis_report.md")
        template_vars = {
            "report_title": product["name"],
            "client_name": order.get("client_name", ""),
            "date": datetime.now(JST).strftime("%Y年%m月%d日"),
            "content": report_text,
            **params,
        }

        pdf_path = str(output_dir / f"{order_id}_report.pdf")
        try:
            self.pdf_gen.generate_pdf(template_name, template_vars, pdf_path)
        except Exception as e:
            logger.error("PDF generation failed: %s", e)
            # Save as markdown instead
            md_path = output_dir / f"{order_id}_report.md"
            md_path.write_text(report_text, encoding="utf-8")
            pdf_path = str(md_path)

        # Step 7: Update status
        try:
            self.sheets.update_order_status(order_id, "delivered")
        except Exception as e:
            logger.warning("Failed to update order status: %s", e)

        # Step 8: Notify
        self.notifier.send_line(f"案件 {order_id} の納品が完了しました。")

        result = {
            "order_id": order_id,
            "status": "delivered",
            "file_path": pdf_path,
            "quality_score": quality_result.get("total_score", 0),
        }

        logger.info("Order %s completed: %s", order_id, result)
        return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    processor = OrderProcessor()
    # Example:
    # processor.process({
    #     "order_id": "ORD-20260216-001",
    #     "product_id": "tier1_area_analysis",
    #     "client_name": "田中太郎",
    #     "parameters": {"area": "港区赤坂", "budget": "1億円"},
    #     "deadline": "2026-02-23",
    #     "platform": "lancers",
    # })
