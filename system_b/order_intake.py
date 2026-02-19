"""Order intake module — detects new orders from email/webhook."""

import logging
from datetime import datetime, timezone, timedelta

from core.notifier import Notifier
from system_b.process_order import OrderProcessor

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


class OrderIntake:
    """Detect and route incoming orders."""

    def __init__(self):
        self.processor = OrderProcessor()
        self.notifier = Notifier()

    def handle_webhook(self, payload: dict) -> dict:
        """Handle incoming order webhook.

        Args:
            payload: Webhook payload with order details.

        Returns:
            Processing result.
        """
        order = {
            "order_id": payload.get("order_id", self._generate_order_id()),
            "product_id": payload.get("product_id", ""),
            "client_name": payload.get("client_name", ""),
            "parameters": payload.get("parameters", {}),
            "deadline": payload.get("deadline", ""),
            "platform": payload.get("platform", "direct"),
        }

        logger.info("New order received: %s", order["order_id"])
        self.notifier.send_line(
            f"新規案件受注: {order['order_id']}\n"
            f"商品: {order['product_id']}\n"
            f"クライアント: {order['client_name']}\n"
            f"納期: {order['deadline']}"
        )

        return self.processor.process(order)

    def _generate_order_id(self) -> str:
        now = datetime.now(JST)
        return f"ORD-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"

    def handle_email_order(self, email_data: dict) -> dict:
        """Parse order from email and process."""
        # Extract order details from email body using Claude
        from core.claude_client import ClaudeClient

        claude = ClaudeClient()
        prompt = (
            "以下のメール本文から案件情報を抽出してください。\n"
            "JSON形式で出力: order_id, product_id, client_name, parameters, deadline, platform\n\n"
            f"件名: {email_data.get('subject', '')}\n"
            f"本文: {email_data.get('body', '')}"
        )

        try:
            parsed = claude.generate_json(prompt, temperature=0.2)
            return self.handle_webhook(parsed)
        except Exception as e:
            logger.error("Email order parsing failed: %s", e)
            self.notifier.send_line(f"メール案件の解析に失敗: {e}")
            return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
