"""Analyze 2170 chart and decide whether to sell."""
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

from cits.japan.broker.kabu_api import KabuStationAPI  # noqa: E402

api = KabuStationAPI()
api._ensure_token()
board = api.get_board("2170", exchange=1)

price = board.get("CurrentPrice", 0)
prev = board.get("PreviousClose", 0)
opn = board.get("OpeningPrice", 0)
high = board.get("HighPrice", 0)
low = board.get("LowPrice", 0)
vol = board.get("TradingVolume", 0)

print("=" * 50)
print("2170 Link and Motivation - Board Info")
print("=" * 50)
print(f"  Current:    {price}")
print(f"  PrevClose:  {prev}")
print(f"  Open:       {opn}")
print(f"  High:       {high}")
print(f"  Low:        {low}")
print(f"  Volume:     {vol}")

if prev and price:
    change_pct = (price - prev) / prev * 100
    print(f"  Change:     {change_pct:+.2f}%")

# Analysis
print()
print("=" * 50)
print("Analysis")
print("=" * 50)

STOP_LEVEL = 610
ENTRY_APPROX = 580  # approximate entry

if price:
    pnl_pct = (price - ENTRY_APPROX) / ENTRY_APPROX * 100
    print(f"  Entry (approx): {ENTRY_APPROX}")
    print(f"  Stop level:     {STOP_LEVEL}")
    print(f"  PnL:            {pnl_pct:+.1f}%")

    if price > STOP_LEVEL:
        print(f"  STATUS: ABOVE STOP ({price} > {STOP_LEVEL})")
        print("  RECOMMENDATION: HOLD - stop not breached")
    elif price > ENTRY_APPROX:
        print("  STATUS: BELOW STOP but still in profit")
        print("  RECOMMENDATION: SELL - stop breached, take remaining profit")
    else:
        print("  STATUS: BELOW ENTRY - in loss")
        print("  RECOMMENDATION: SELL - cut loss")

print()
print("Run sell_2170.py only if recommendation is SELL")
