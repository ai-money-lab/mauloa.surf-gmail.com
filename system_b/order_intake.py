"""System B - 受注検知

メール/Webhookから案件を検知し、process_order.pyに渡す。
"""

import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env", override=True)

from core.notifier import Notifier

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent


class OrderIntake:
    """案件受注検知"""

    def __init__(self):
        self.notifier = Notifier()

    def create_order(
        self,
        product_id: str,
        client_name: str,
        parameters: dict,
        deadline: str,
        platform: str = "direct",
        price: int = 0,
    ) -> dict:
        """案件JSONを作成"""
        now = datetime.now(JST)
        order_id = f"ORD-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"

        order = {
            "order_id": order_id,
            "product_id": product_id,
            "client_name": client_name,
            "parameters": parameters,
            "deadline": deadline,
            "platform": platform,
            "price": price,
            "created_at": now.isoformat(),
            "status": "received",
        }

        logger.info(f"New order created: {order_id}")
        return order

    def save_order(self, order: dict) -> str:
        """案件JSONを保存"""
        orders_dir = BASE_DIR / "data" / "system_b" / "orders"
        orders_dir.mkdir(parents=True, exist_ok=True)

        output_path = orders_dir / f"{order['order_id']}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(order, f, ensure_ascii=False, indent=2)

        return str(output_path)

    def process_webhook(self, payload: dict) -> dict:
        """Webhook受信時の処理"""
        platform = payload.get("platform", "direct")
        product_id = payload.get("product_id", "")
        client_name = payload.get("client_name", "")
        parameters = payload.get("parameters", {})
        deadline = payload.get("deadline", "")
        price = payload.get("price", 0)

        order = self.create_order(
            product_id=product_id,
            client_name=client_name,
            parameters=parameters,
            deadline=deadline,
            platform=platform,
            price=price,
        )

        path = self.save_order(order)

        self.notifier.notify(
            f"新規案件を受注しました\n"
            f"案件ID: {order['order_id']}\n"
            f"商品: {product_id}\n"
            f"クライアント: {client_name}\n"
            f"プラットフォーム: {platform}\n"
            f"納期: {deadline}"
        )

        return order


def main():
    logging.basicConfig(level=logging.INFO)

    intake = OrderIntake()
    order = intake.create_order(
        product_id="tier1_area_analysis",
        client_name="サンプル太郎",
        parameters={"area": "港区赤坂", "budget": "1億円"},
        deadline="2026-02-23",
        platform="lancers",
        price=400000,
    )
    path = intake.save_order(order)
    print(f"Sample order created: {path}")
    print(json.dumps(order, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
