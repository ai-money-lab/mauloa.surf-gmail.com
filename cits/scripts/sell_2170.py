"""One-time: sell 2170 at market open. Delete this file after execution."""
import os
import sys
from pathlib import Path

# .env load
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

MARKER = Path(__file__).resolve().parent.parent / "logs" / ".sold_2170"

if MARKER.exists():
    print("2170 already sold. Skipping.")
    sys.exit(0)

scheduled = os.environ.get("CITS_SCHEDULED_RUN", "")
api_pw = os.environ.get("KABU_API_PASSWORD", "")

if not api_pw:
    print("ERROR: KABU_API_PASSWORD not set")
    sys.exit(1)

from cits.japan.broker.kabu_api import KabuStationAPI  # noqa: E402

try:
    broker = KabuStationAPI()
    broker._ensure_token()
    print("kabuStation connected")

    result = broker.place_order(
        symbol="2170", side="sell", qty=100,
        order_type="market", exchange=9,
    )
    print(f"SELL 2170 x100 @ MARKET: {result}")

    if "error" not in result:
        MARKER.parent.mkdir(parents=True, exist_ok=True)
        MARKER.write_text(f"Sold 2170 at market. OrderId={result.get('OrderId', '?')}")
        print("SUCCESS: 2170 sold. Marker created.")
    else:
        print(f"ERROR: {result['error']}")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
