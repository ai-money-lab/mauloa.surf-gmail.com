"""Sell 2170 at market (stop loss discipline: sell regardless of profit/loss)."""
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        try:
            load_dotenv(env_path, override=True)
        except UnicodeDecodeError:
            load_dotenv(env_path, override=True, encoding="cp932")
except ImportError:
    pass

import os  # noqa: E402
import sys  # noqa: E402

MARKER = Path(__file__).resolve().parent.parent / "logs" / ".sold_2170"
if MARKER.exists():
    print("2170 already sold. Skipping.")
    sys.exit(0)

api_pw = os.environ.get("KABU_API_PASSWORD", "")
if not api_pw:
    print("ERROR: KABU_API_PASSWORD not set")
    sys.exit(1)

from cits.japan.broker.kabu_api import KabuStationAPI  # noqa: E402

ENTRY_PRICE = 580

try:
    broker = KabuStationAPI()
    broker._ensure_token()
    print("kabuStation connected")

    board = broker.get_board("2170", exchange=1)
    price = board.get("CurrentPrice", 0)
    pnl = (price - ENTRY_PRICE) if price > 0 else 0
    print(f"Current price: {price}  Entry: {ENTRY_PRICE}  PnL: {pnl:+} yen")

    if price <= 0:
        print("ERROR: Cannot get current price. ABORT.")
        sys.exit(1)

    # ストップロス規律: 損益に関わらず成行売り
    print("Selling at market (stop loss discipline: execute regardless of PnL)")

    result = broker.place_order(
        symbol="2170", side="sell", qty=100,
        order_type="market", exchange=9,
    )
    print(f"SELL 2170 x100 @ MARKET: {result}")

    if "error" not in result:
        MARKER.parent.mkdir(parents=True, exist_ok=True)
        MARKER.write_text(
            f"Sold 2170 at price={price} pnl={pnl:+}. OrderId={result.get('OrderId', '?')}"
        )
        print("SUCCESS: 2170 sold.")
    else:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
