"""Revenue Tracker — 売上・原価・利益のトラッキングとP&Lダッシュボード."""

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
ORDERS_DIR = BASE_DIR / "data" / "monetize" / "orders"
COSTS_DIR = BASE_DIR / "data" / "monetize" / "costs"
SUBSCRIPTIONS_DIR = BASE_DIR / "data" / "monetize" / "subscriptions"


class RevenueTracker:
    """売上・原価・利益を集計してP&Lレポートを生成."""

    def __init__(self):
        for d in [ORDERS_DIR, COSTS_DIR, SUBSCRIPTIONS_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    def get_daily_summary(self, date: str = "") -> dict:
        """日次サマリー.

        Args:
            date: YYYYMMDD形式。空なら今日。

        Returns:
            {"date": str, "orders": int, "revenue_jpy": int, "cost_jpy": int,
             "profit_jpy": int, "margin_pct": float, "products": dict}
        """
        if not date:
            date = datetime.now(JST).strftime("%Y%m%d")

        month = date[:6]
        orders = self._load_month_orders(month)

        day_orders = [o for o in orders if o.get("created_at", "").replace("-", "").startswith(date)]
        delivered = [o for o in day_orders if o.get("status") == "delivered"]

        revenue = sum(o.get("price_jpy", 0) for o in delivered)
        cost = sum(o.get("cost_jpy", 0) for o in delivered)
        profit = revenue - cost
        margin = (profit / revenue * 100) if revenue > 0 else 0

        # 商品別集計
        products = defaultdict(lambda: {"count": 0, "revenue": 0})
        for o in delivered:
            pid = o.get("product_id", "unknown")
            products[pid]["count"] += 1
            products[pid]["revenue"] += o.get("price_jpy", 0)

        return {
            "date": date,
            "total_orders": len(day_orders),
            "delivered": len(delivered),
            "revenue_jpy": revenue,
            "cost_jpy": cost,
            "profit_jpy": profit,
            "margin_pct": round(margin, 1),
            "products": dict(products),
        }

    def get_monthly_summary(self, month: str = "") -> dict:
        """月次サマリー.

        Args:
            month: YYYYMM形式。空なら今月。

        Returns:
            P&Lレポート形式のdict
        """
        if not month:
            month = datetime.now(JST).strftime("%Y%m")

        orders = self._load_month_orders(month)
        delivered = [o for o in orders if o.get("status") == "delivered"]

        revenue = sum(o.get("price_jpy", 0) for o in delivered)
        cost = sum(o.get("cost_jpy", 0) for o in delivered)

        # 商品別集計
        products = defaultdict(lambda: {"count": 0, "revenue": 0, "cost": 0})
        for o in delivered:
            pid = o.get("product_id", "unknown")
            products[pid]["count"] += 1
            products[pid]["revenue"] += o.get("price_jpy", 0)
            products[pid]["cost"] += o.get("cost_jpy", 0)

        # サブスクリプション収益
        sub_revenue = self._get_subscription_revenue(month)

        # 日別推移
        daily = defaultdict(lambda: {"revenue": 0, "cost": 0, "orders": 0})
        for o in delivered:
            day = o.get("created_at", "")[:10]
            daily[day]["revenue"] += o.get("price_jpy", 0)
            daily[day]["cost"] += o.get("cost_jpy", 0)
            daily[day]["orders"] += 1

        total_revenue = revenue + sub_revenue

        return {
            "month": month,
            "total_orders": len(orders),
            "delivered": len(delivered),
            "instant_revenue_jpy": revenue,
            "subscription_revenue_jpy": sub_revenue,
            "total_revenue_jpy": total_revenue,
            "total_cost_jpy": cost,
            "gross_profit_jpy": total_revenue - cost,
            "margin_pct": round(((total_revenue - cost) / total_revenue * 100) if total_revenue > 0 else 0, 1),
            "products": dict(products),
            "daily_trend": dict(sorted(daily.items())),
            "avg_order_value_jpy": round(revenue / len(delivered)) if delivered else 0,
        }

    def get_pl_report(self, month: str = "") -> str:
        """P&Lレポートをテキスト形式で生成（通知・ログ用）."""
        summary = self.get_monthly_summary(month)
        m = summary["month"]

        lines = [
            f"═══ P&L レポート {m[:4]}年{m[4:]}月 ═══",
            "",
            f"  受注数:       {summary['total_orders']}件",
            f"  納品完了:     {summary['delivered']}件",
            "",
            "─── 売上 ───",
            f"  即時商品:     ¥{summary['instant_revenue_jpy']:>10,}",
            f"  サブスク:     ¥{summary['subscription_revenue_jpy']:>10,}",
            f"  合計売上:     ¥{summary['total_revenue_jpy']:>10,}",
            "",
            "─── 原価 ───",
            f"  API費用:      ¥{summary['total_cost_jpy']:>10,}",
            "",
            "─── 利益 ───",
            f"  粗利:         ¥{summary['gross_profit_jpy']:>10,}",
            f"  粗利率:       {summary['margin_pct']:>9.1f}%",
            "",
            "─── 商品別 ───",
        ]

        for pid, data in summary.get("products", {}).items():
            product_profit = data["revenue"] - data["cost"]
            lines.append(
                f"  {pid}: {data['count']}件 / ¥{data['revenue']:,} (利益¥{product_profit:,})"
            )

        if summary.get("avg_order_value_jpy"):
            lines.extend([
                "",
                f"  平均注文額:   ¥{summary['avg_order_value_jpy']:,}",
            ])

        lines.append("═══════════════════════════════════")
        return "\n".join(lines)

    def record_subscription(
        self,
        customer_id: str,
        subscription_id: str,
        price_jpy: int,
        started_at: str = "",
    ) -> None:
        """サブスクリプション契約を記録."""
        if not started_at:
            started_at = datetime.now(JST).isoformat()

        record = {
            "customer_id": customer_id,
            "subscription_id": subscription_id,
            "price_jpy_monthly": price_jpy,
            "status": "active",
            "started_at": started_at,
        }

        sub_file = SUBSCRIPTIONS_DIR / f"{customer_id}_{subscription_id}.json"
        sub_file.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    def _get_subscription_revenue(self, month: str) -> int:
        """月次サブスクリプション収益を計算."""
        total = 0
        for f in SUBSCRIPTIONS_DIR.glob("*.json"):
            try:
                sub = json.loads(f.read_text(encoding="utf-8"))
                if sub.get("status") != "active":
                    continue
                # 契約開始月以降なら収益として計上
                started = sub.get("started_at", "")[:7].replace("-", "")
                if started <= month:
                    total += sub.get("price_jpy_monthly", 0)
            except Exception:
                continue
        return total

    def _load_month_orders(self, month: str) -> list[dict]:
        """月次注文ログを読み込む."""
        log_file = ORDERS_DIR / f"{month}_orders.jsonl"
        if not log_file.exists():
            return []
        orders = []
        for line in log_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                orders.append(json.loads(line))
            except Exception:
                continue
        return orders
