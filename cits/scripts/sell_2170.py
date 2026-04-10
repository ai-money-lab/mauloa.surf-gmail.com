"""One-time: sell 2170 - debug version with full error logging."""
import os
import sys
import json
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

import requests  # noqa: E402

MARKER = Path(__file__).resolve().parent.parent / "logs" / ".sold_2170"
if MARKER.exists():
    print("2170 already sold. Skipping.")
    sys.exit(0)

api_pw = os.environ.get("KABU_API_PASSWORD", "")
order_pw = os.environ.get("KABU_ORDER_PASSWORD", api_pw)
print(f"API_PW set: {bool(api_pw)}, ORDER_PW set: {bool(order_pw)}")
print(f"ORDER_PW value: {order_pw[:4]}***") if order_pw else None

BASE = "http://localhost:18080"

# Get token
try:
    r = requests.post(f"{BASE}/kabusapi/token", json={"APIPassword": api_pw}, timeout=10)
    r.raise_for_status()
    token = r.json().get("Token", "")
    print(f"Token obtained: {token[:8]}...")
except Exception as e:
    print(f"Token failed: {e}")
    sys.exit(1)

headers = {"Content-Type": "application/json", "X-API-KEY": token}

# Try multiple parameter combinations
combinations = [
    {"desc": "AccountType=4 FundType=AA exchange=9", "AccountType": 4, "FundType": "AA", "Exchange": 9},
    {"desc": "AccountType=4 FundType=AA exchange=1", "AccountType": 4, "FundType": "AA", "Exchange": 1},
    {"desc": "AccountType=4 FundType=space exchange=1", "AccountType": 4, "FundType": "  ", "Exchange": 1},
    {"desc": "AccountType=2 no FundType exchange=1", "AccountType": 2, "FundType": None, "Exchange": 1},
    {"desc": "AccountType=4 no FundType exchange=1", "AccountType": 4, "FundType": None, "Exchange": 1},
]

for combo in combinations:
    payload = {
        "Password": order_pw,
        "Symbol": "2170",
        "Exchange": combo["Exchange"],
        "SecurityType": 1,
        "Side": "1",
        "CashMargin": 1,
        "DelivType": 2,
        "AccountType": combo["AccountType"],
        "Qty": 100,
        "FrontOrderType": 10,
        "Price": 0,
        "ExpireDay": 0,
    }
    if combo["FundType"] is not None:
        payload["FundType"] = combo["FundType"]

    print(f"\n--- Trying: {combo['desc']} ---")
    try:
        r = requests.post(f"{BASE}/kabusapi/sendorder", json=payload, headers=headers, timeout=10)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text}")
        if r.status_code == 200:
            data = r.json()
            if "OrderId" in data:
                print(f"SUCCESS! OrderId: {data['OrderId']}")
                MARKER.parent.mkdir(parents=True, exist_ok=True)
                MARKER.write_text(f"Sold 2170. OrderId={data['OrderId']} combo={combo['desc']}")
                print("Marker created. Done.")
                sys.exit(0)
    except Exception as e:
        print(f"Exception: {e}")

print("\nAll combinations failed.")
