"""Sell 2170 ONLY if still in profit. Absolute rule: never sell at loss."""
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

# ABSOLUTE RULE: NEVER SELL AT A LOSS
ENTRY_PRICE = 580
MIN_PROFIT_PRICE = ENTRY_PRICE + 5  # +5円以上の利益で売る（手数料・スリッページ考慮）

try:
    broker = KabuStationAPI()
    broker._ensure_token()
    print("kabuStation connected")

    # Check current price FIRST
    board = broker.get_board("2170", exchange=1)
    price = board.get("CurrentPrice", 0)
    print(f"Current price: {price}")
    print(f"Entry price: {ENTRY_PRICE}")
    print(f"Min profit price: {MIN_PROFIT_PRICE}")

    if price <= 0:
        print("ERROR: Cannot get current price. ABORT.")
        sys.exit(1)

    if price < MIN_PROFIT_PRICE:
        pnl = price - ENTRY_PRICE
        print(f"PRICE TOO LOW: {price} < {MIN_PROFIT_PRICE} (would be {pnl:+} yen)")
        print("RULE VIOLATION AVOIDED: Never sell at loss. HOLD.")
        sys.exit(0)

    print(f"Price OK: selling at market (profit: {price - ENTRY_PRICE:+} yen)")

    result = broker.place_order(
        symbol="2170", side="sell", qty=100,
        order_type="market", exchange=9,
    )
    print(f"SELL 2170 x100 @ MARKET: {result}")

    if "error" not in result:
        MARKER.parent.mkdir(parents=True, exist_ok=True)
        MARKER.write_text(
            f"Sold 2170 at price={price}. OrderId={result.get('OrderId', '?')}"
        )
        print("SUCCESS: 2170 sold.")
    else:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
