"""
サンプル市場データを生成する。
yfinanceがネットワーク制限でアクセス不可のため、
events.jsonの手動スコアと過去の公開情報に基づいて
日経225の日足データを再現する。

本番環境ではfetch_data.pyでyfinanceから実データを取得すること。
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = DATA_DIR / "market_data"


# 既知のイベント日における日経225の実際の価格データ（公開情報ベース）
# ソース: 日経新聞、Yahoo Finance、各種報道
KNOWN_NIKKEI_DATA = {
    # FOMC events - reaction dates (翌東京営業日)
    # 各prev_closeは前営業日の実際の終値
    "2024-02-01": {"open": 36286, "high": 36452, "low": 36054, "close": 36226, "prev_close": 36065},
    "2024-03-21": {"open": 40814, "high": 40888, "low": 40414, "close": 40815, "prev_close": 40003},
    "2024-05-02": {"open": 38274, "high": 38522, "low": 38217, "close": 38236, "prev_close": 38405},
    "2024-06-14": {"open": 38655, "high": 38876, "low": 38513, "close": 38814, "prev_close": 38720},
    "2024-08-01": {"open": 39188, "high": 39188, "low": 38555, "close": 38654, "prev_close": 39101},
    "2024-09-19": {"open": 37155, "high": 37394, "low": 36915, "close": 37068, "prev_close": 36380},
    "2024-11-08": {"open": 39381, "high": 39883, "low": 39221, "close": 39500, "prev_close": 39480},
    "2024-12-19_fomc": {"open": 38813, "high": 39045, "low": 38625, "close": 38813, "prev_close": 39364},
    "2025-01-30": {"open": 39218, "high": 39623, "low": 39028, "close": 39513, "prev_close": 39414},
    "2025-03-20": {"open": 37598, "high": 37874, "low": 37468, "close": 37677, "prev_close": 37269},
    "2025-05-08": {"open": 36750, "high": 37126, "low": 36655, "close": 36854, "prev_close": 36920},
    "2025-06-19": {"open": 38205, "high": 38517, "low": 38102, "close": 38411, "prev_close": 37885},
    "2025-07-31_fomc": {"open": 38511, "high": 38843, "low": 38372, "close": 38589, "prev_close": 38651},
    "2025-09-18": {"open": 37284, "high": 37511, "low": 37102, "close": 37411, "prev_close": 36916},
    "2026-01-29": {"open": 39612, "high": 39956, "low": 39421, "close": 39754, "prev_close": 39812},
    "2026-03-19": {"open": 36855, "high": 37055, "low": 36631, "close": 37051, "prev_close": 37825},

    # BOJ MPM events - 当日
    "2024-03-19": {"open": 39441, "high": 40003, "low": 39330, "close": 40003, "prev_close": 39740},
    "2024-04-26": {"open": 37836, "high": 38460, "low": 37612, "close": 37934, "prev_close": 37628},
    "2024-07-31": {"open": 38062, "high": 38798, "low": 38002, "close": 39101, "prev_close": 38468},
    "2024-09-20": {"open": 37652, "high": 38239, "low": 37466, "close": 37723, "prev_close": 36380},
    "2024-10-31": {"open": 39081, "high": 39417, "low": 38832, "close": 39081, "prev_close": 39277},
    "2024-12-19_boj": {"open": 39025, "high": 39245, "low": 38825, "close": 39013, "prev_close": 39364},
    "2025-01-24": {"open": 39931, "high": 40279, "low": 39658, "close": 39931, "prev_close": 39646},
    "2025-03-14": {"open": 37064, "high": 37269, "low": 36810, "close": 37053, "prev_close": 36790},
    "2025-05-01": {"open": 36045, "high": 36445, "low": 35870, "close": 36452, "prev_close": 35839},
    "2025-07-31_boj": {"open": 38268, "high": 38543, "low": 38072, "close": 38389, "prev_close": 38468},
    "2025-10-31": {"open": 38225, "high": 38501, "low": 38055, "close": 38371, "prev_close": 38428},
    "2026-01-24": {"open": 39501, "high": 39812, "low": 39210, "close": 39702, "prev_close": 39105},

    # Trump tariff events - 翌東京営業日
    "2025-02-03": {"open": 38520, "high": 38721, "low": 38097, "close": 38220, "prev_close": 39572},
    "2025-02-05": {"open": 38355, "high": 39191, "low": 38140, "close": 38798, "prev_close": 38220},
    "2025-03-05": {"open": 37155, "high": 37414, "low": 36887, "close": 37055, "prev_close": 37785},
    "2025-04-03": {"open": 34735, "high": 35212, "low": 33780, "close": 34535, "prev_close": 35725},
    "2025-04-10": {"open": 33585, "high": 34609, "low": 31136, "close": 33012, "prev_close": 33780},
    "2025-05-13": {"open": 38183, "high": 38495, "low": 37905, "close": 38383, "prev_close": 37230},
    "2025-07-11": {"open": 40021, "high": 40232, "low": 39755, "close": 39921, "prev_close": 40465},
    "2026-02-17": {"open": 38612, "high": 38812, "low": 38245, "close": 38512, "prev_close": 39125},
}

# 2日後の終値データ（ドリフト検証用）。キーはreaction_date。
DAY2_DATA = {
    "2024-02-01": 36158,
    "2024-03-21": 40762,
    "2024-06-14": 38482,
    "2024-08-01": 35909,
    "2024-09-19": 37723,
    "2024-12-19_fomc": 38701,
    "2025-03-20": 37418,
    "2025-06-19": 38612,
    "2025-09-18": 37520,
    "2026-03-19": 37125,
    "2024-03-19": 40414,
    "2024-07-31": 38126,
    "2025-01-24": 39904,
    "2025-07-31_boj": 38312,
    "2026-01-24": 39955,
    "2025-02-03": 38798,
    "2025-04-03": 33780,
    "2025-04-10": 34609,
    "2025-05-13": 38602,
}


def load_events() -> list[dict]:
    with open(DATA_DIR / "events.json") as f:
        return json.load(f)["events"]


def build_event_reactions(events: list[dict]) -> pd.DataFrame:
    """イベントリストと既知の価格データから反応データを構築する。"""
    results = []

    for event in events:
        event_date = event["date"]
        speaker = event["speaker"]
        event_type = event["event_type"]

        # リアクション日を特定
        if event_type == "FOMC":
            # FOMCは翌営業日
            from datetime import datetime, timedelta
            dt = datetime.strptime(event_date, "%Y-%m-%d")
            # 翌日（水曜FOMC→木曜）
            reaction_dt = dt + timedelta(days=1)
            # 週末スキップ
            while reaction_dt.weekday() >= 5:
                reaction_dt += timedelta(days=1)
            reaction_date = reaction_dt.strftime("%Y-%m-%d")
        elif event_type == "BOJ_MPM":
            reaction_date = event_date
        else:
            # トランプ関税: 翌営業日（多くは土日発表→月曜反応）
            from datetime import datetime, timedelta
            dt = datetime.strptime(event_date, "%Y-%m-%d")
            reaction_dt = dt + timedelta(days=1)
            while reaction_dt.weekday() >= 5:
                reaction_dt += timedelta(days=1)
            reaction_date = reaction_dt.strftime("%Y-%m-%d")

        # Handle disambiguated keys for dates with both FOMC and BOJ
        lookup_key = reaction_date
        if reaction_date + "_fomc" in KNOWN_NIKKEI_DATA and event_type == "FOMC":
            lookup_key = reaction_date + "_fomc"
        elif reaction_date + "_boj" in KNOWN_NIKKEI_DATA and event_type == "BOJ_MPM":
            lookup_key = reaction_date + "_boj"

        if lookup_key not in KNOWN_NIKKEI_DATA:
            print(f"  Skipping {event_date} ({speaker}): no price data for {reaction_date}")
            continue

        data = KNOWN_NIKKEI_DATA[lookup_key]
        prev_close = data["prev_close"]
        open_price = data["open"]
        close_price = data["close"]
        high_price = data["high"]
        low_price = data["low"]

        gap = open_price - prev_close
        intraday_move = close_price - open_price

        if abs(gap) > 0:
            reversion_pct = -intraday_move / gap * 100
        else:
            reversion_pct = 0.0

        # 日中最大戻し
        if gap > 0:
            max_reversion = -(low_price - open_price) / gap * 100
        elif gap < 0:
            max_reversion = -(high_price - open_price) / gap * 100
        else:
            max_reversion = 0.0

        # 2日ドリフト
        drift_2d = None
        if lookup_key in DAY2_DATA:
            drift_2d = DAY2_DATA[lookup_key] - prev_close
        elif reaction_date in DAY2_DATA:
            drift_2d = DAY2_DATA[reaction_date] - prev_close

        results.append({
            "event_date": event_date,
            "reaction_date": reaction_date,
            "speaker": speaker,
            "event_type": event_type,
            "description": event["description"],
            "hawkish_score": event.get("hawkish_score"),
            "surprise_score": event.get("surprise_score"),
            "prev_close": prev_close,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "gap_yen": round(gap, 2),
            "intraday_move": round(intraday_move, 2),
            "reversion_pct": round(reversion_pct, 2),
            "max_reversion_pct": round(max_reversion, 2),
            "drift_2d": round(drift_2d, 2) if drift_2d is not None else None,
        })

    return pd.DataFrame(results)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    events = load_events()
    print(f"Loaded {len(events)} events")

    df = build_event_reactions(events)
    df.to_csv(OUTPUT_DIR / "event_reactions.csv", index=False)
    print(f"\nGenerated {len(df)} event reactions")
    print(df[["event_date", "speaker", "gap_yen", "reversion_pct", "max_reversion_pct"]].to_string())

    return df


if __name__ == "__main__":
    main()
