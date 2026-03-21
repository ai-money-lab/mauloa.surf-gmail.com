"""
Phase 1-A: yfinanceから日経225/NYダウの日足データを取得する。
イベント日リストに基づき、前後の価格データを抽出・保存。
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).parent.parent / "data"
EVENTS_FILE = DATA_DIR / "events.json"
OUTPUT_DIR = DATA_DIR / "market_data"


def load_events() -> list[dict]:
    """events.jsonからイベントリストを読み込む。"""
    with open(EVENTS_FILE) as f:
        data = json.load(f)
    return data["events"]


def fetch_daily_data(
    ticker: str, start: str = "2020-01-01", end: str = "2026-03-22"
) -> pd.DataFrame:
    """yfinanceから日足データを取得する。"""
    print(f"Fetching {ticker} daily data from {start} to {end}...")
    df = yf.download(ticker, start=start, end=end, progress=False)
    if df.empty:
        print(f"WARNING: No data returned for {ticker}")
        return df
    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    print(f"  Got {len(df)} rows for {ticker}")
    return df


def fetch_intraday_data(
    ticker: str, event_date: str, days_around: int = 3
) -> pd.DataFrame:
    """イベント日前後の5分足データを取得する（yfinanceの制限: 直近60日のみ）。"""
    dt = pd.Timestamp(event_date)
    start = (dt - timedelta(days=days_around)).strftime("%Y-%m-%d")
    end = (dt + timedelta(days=days_around + 1)).strftime("%Y-%m-%d")

    print(f"Fetching {ticker} 5min data around {event_date}...")
    df = yf.download(ticker, start=start, end=end, interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.empty:
        print(f"  WARNING: No intraday data for {event_date} (may be >60 days ago)")
    else:
        print(f"  Got {len(df)} 5min bars")
    return df


def get_trading_day(daily_df: pd.DataFrame, target_date: str, offset: int = 0) -> str:
    """target_dateから最も近い取引日を返す。offset=1なら翌営業日。"""
    idx = daily_df.index
    # target_dateをTimestampに変換（tz-naive）
    target = pd.Timestamp(target_date)
    if target.tzinfo is not None:
        target = target.tz_localize(None)

    # idx もtz-naiveに変換
    if idx.tzinfo is not None:
        idx = idx.tz_localize(None)

    # target_date以降の最初の取引日を見つける
    future_dates = idx[idx >= target]
    if len(future_dates) == 0:
        return None

    if offset == 0:
        return str(future_dates[0].date())
    elif offset > 0 and len(future_dates) > offset:
        return str(future_dates[offset].date())
    return None


def extract_event_data(
    nikkei_daily: pd.DataFrame, dow_daily: pd.DataFrame, events: list[dict]
) -> pd.DataFrame:
    """各イベント日について価格データを抽出し、統計量を計算する。"""
    results = []

    for event in events:
        event_date = event["date"]
        speaker = event["speaker"]
        event_type = event["event_type"]

        # FOMCは米国時間で発表→翌東京営業日に影響
        if event_type == "FOMC":
            reaction_date = get_trading_day(nikkei_daily, event_date, offset=1)
        else:
            # 日銀MPM/トランプ発言は当日or翌日
            reaction_date = get_trading_day(nikkei_daily, event_date, offset=0)

        if reaction_date is None:
            print(f"  Skipping {event_date} ({speaker}): no trading day found")
            continue

        # 前営業日を取得
        prev_date = get_trading_day(nikkei_daily, event_date, offset=-1)
        # 前営業日: reaction_dateの1つ前の取引日
        nk_idx = nikkei_daily.index
        if nk_idx.tzinfo is not None:
            nk_idx = nk_idx.tz_localize(None)
        reaction_ts = pd.Timestamp(reaction_date)
        prior_dates = nk_idx[nk_idx < reaction_ts]
        if len(prior_dates) == 0:
            continue
        prev_date = str(prior_dates[-1].date())

        # 2日後の取引日
        day2_date = get_trading_day(nikkei_daily, reaction_date, offset=1)

        # 価格データ取得
        try:
            prev_row = nikkei_daily.loc[prev_date]
            reaction_row = nikkei_daily.loc[reaction_date]
        except KeyError:
            print(f"  Skipping {event_date}: price data missing")
            continue

        prev_close = float(prev_row["Close"])
        open_price = float(reaction_row["Open"])
        close_price = float(reaction_row["Close"])
        high_price = float(reaction_row["High"])
        low_price = float(reaction_row["Low"])

        gap = open_price - prev_close
        intraday_move = close_price - open_price

        # 戻し率: ギャップの逆方向に動いた割合
        if abs(gap) > 0:
            reversion_pct = -intraday_move / gap * 100
        else:
            reversion_pct = 0.0

        # 日中最大戻し
        if gap > 0:
            # ギャップアップ→下に戻す
            max_reversion = -(low_price - open_price) / gap * 100
        elif gap < 0:
            # ギャップダウン→上に戻す
            max_reversion = -(high_price - open_price) / gap * 100
        else:
            max_reversion = 0.0

        # 2日ドリフト
        drift_2d = None
        if day2_date:
            try:
                day2_row = nikkei_daily.loc[day2_date]
                drift_2d = float(day2_row["Close"]) - prev_close
            except KeyError:
                pass

        # NYダウの動き（同日）
        dow_change = None
        try:
            # FOMCの場合はイベント日当日のダウの動き
            dow_row = dow_daily.loc[event_date]
            dow_prev_dates = dow_daily.index[dow_daily.index < pd.Timestamp(event_date)]
            if len(dow_prev_dates) > 0:
                dow_prev = dow_daily.loc[str(dow_prev_dates[-1].date())]
                dow_change = float(dow_row["Close"]) - float(dow_prev["Close"])
        except (KeyError, IndexError):
            pass

        results.append({
            "event_date": event_date,
            "reaction_date": reaction_date,
            "speaker": speaker,
            "event_type": event_type,
            "description": event["description"],
            "hawkish_score": event.get("hawkish_score"),
            "surprise_score": event.get("surprise_score"),
            "prev_close": round(prev_close, 2),
            "open": round(open_price, 2),
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "close": round(close_price, 2),
            "gap_yen": round(gap, 2),
            "intraday_move": round(intraday_move, 2),
            "reversion_pct": round(reversion_pct, 2),
            "max_reversion_pct": round(max_reversion, 2),
            "drift_2d": round(drift_2d, 2) if drift_2d is not None else None,
            "dow_change": round(dow_change, 2) if dow_change is not None else None,
        })

    return pd.DataFrame(results)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. イベントリスト読み込み
    events = load_events()
    print(f"Loaded {len(events)} events")

    # 2. 日足データ取得
    nikkei_daily = fetch_daily_data("^N225")
    dow_daily = fetch_daily_data("^DJI")

    # 日足データ保存
    nikkei_daily.to_csv(OUTPUT_DIR / "nikkei225_daily.csv")
    dow_daily.to_csv(OUTPUT_DIR / "dow_daily.csv")
    print(f"Saved daily data to {OUTPUT_DIR}")

    # 3. イベント反応データ抽出
    event_df = extract_event_data(nikkei_daily, dow_daily, events)
    event_df.to_csv(OUTPUT_DIR / "event_reactions.csv", index=False)
    print(f"\nExtracted {len(event_df)} event reactions")
    print(event_df.to_string())

    # 4. 直近イベントの5分足取得（60日以内のもののみ）
    cutoff = datetime.now() - timedelta(days=59)
    recent_events = [e for e in events if datetime.strptime(e["date"], "%Y-%m-%d") > cutoff]
    print(f"\n{len(recent_events)} events within 60-day window for intraday data")

    for event in recent_events:
        ticker = "^N225"
        intraday = fetch_intraday_data(ticker, event["date"])
        if not intraday.empty:
            safe_date = event["date"].replace("-", "")
            intraday.to_csv(OUTPUT_DIR / f"intraday_5min_{safe_date}.csv")

    return event_df


if __name__ == "__main__":
    df = main()
