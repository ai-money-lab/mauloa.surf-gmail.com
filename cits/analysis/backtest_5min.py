"""
Phase 1-C: 5分足レベルの精密バックテスト。
「何分後にギャップの何%を戻すか」を5分刻みで測定し、
最適なエントリー/エグジットタイミングを特定する。

5分足データが利用可能な直近イベントに対して実行。
日足データしかない場合はday-levelシミュレーションにフォールバック。
"""

import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data" / "market_data"

# パラメータグリッド
ENTRY_DELAYS = [0, 5, 10, 15, 30]  # 寄付きからの遅延（分）
TAKE_PROFITS = [10, 20, 30, 40, 50]  # ギャップの%
STOP_LOSSES = [10, 20, 30, 40, 50]  # ギャップの%
HOLD_LIMITS = [30, 60, 120, 240]  # 保有時間上限（分）, 240=大引け

MICRO_MULTIPLIER = 100
COMMISSION = 11  # 片道


def load_intraday_data(event_date: str) -> pd.DataFrame | None:
    """5分足データを読み込む。"""
    safe_date = event_date.replace("-", "")
    path = DATA_DIR / f"intraday_5min_{safe_date}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df


def extract_session_data(df: pd.DataFrame, reaction_date: str) -> pd.DataFrame:
    """リアクション日の東京セッション（9:00-15:00 JST）を抽出。"""
    # yfinanceの日経データはJST
    target = pd.Timestamp(reaction_date)
    session_start = target.replace(hour=9, minute=0)
    session_end = target.replace(hour=15, minute=0)

    mask = (df.index >= session_start) & (df.index <= session_end)
    session = df[mask]
    return session


def simulate_trade_5min(
    session: pd.DataFrame,
    gap_yen: float,
    entry_delay: int,
    take_profit_pct: float,
    stop_loss_pct: float,
    hold_limit_min: int,
) -> dict | None:
    """5分足データで1トレードをシミュレーション。"""
    if session.empty or abs(gap_yen) < 50:
        return None

    # エントリーポイント
    entry_idx = entry_delay // 5
    if entry_idx >= len(session):
        return None

    entry_price = float(session.iloc[entry_idx]["Open"])
    entry_time = session.index[entry_idx]

    # TP/SLラインの計算（ギャップの逆方向にエントリー）
    tp_distance = abs(gap_yen) * take_profit_pct / 100
    sl_distance = abs(gap_yen) * stop_loss_pct / 100

    if gap_yen > 0:
        # ギャップアップ→ショート（下を期待）
        tp_price = entry_price - tp_distance
        sl_price = entry_price + sl_distance
        direction = -1  # short
    else:
        # ギャップダウン→ロング（上を期待）
        tp_price = entry_price + tp_distance
        sl_price = entry_price - sl_distance
        direction = 1  # long

    # 保有時間上限
    max_bars = hold_limit_min // 5
    exit_idx = min(entry_idx + max_bars, len(session) - 1)

    # バーを順にチェック
    exit_price = None
    exit_time = None
    result = None

    for i in range(entry_idx + 1, exit_idx + 1):
        bar = session.iloc[i]
        high = float(bar["High"])
        low = float(bar["Low"])

        if direction == 1:  # ロング
            if high >= tp_price:
                exit_price = tp_price
                result = "TP"
                exit_time = session.index[i]
                break
            if low <= sl_price:
                exit_price = sl_price
                result = "SL"
                exit_time = session.index[i]
                break
        else:  # ショート
            if low <= tp_price:
                exit_price = tp_price
                result = "TP"
                exit_time = session.index[i]
                break
            if high >= sl_price:
                exit_price = sl_price
                result = "SL"
                exit_time = session.index[i]
                break

    # タイムアウト
    if exit_price is None:
        exit_price = float(session.iloc[exit_idx]["Close"])
        exit_time = session.index[exit_idx]
        result = "TIMEOUT"

    pnl_points = (exit_price - entry_price) * direction
    pnl_yen = pnl_points * MICRO_MULTIPLIER - COMMISSION * 2  # 1枚

    return {
        "entry_time": str(entry_time),
        "exit_time": str(exit_time),
        "entry_price": round(entry_price, 2),
        "exit_price": round(exit_price, 2),
        "direction": "LONG" if direction == 1 else "SHORT",
        "result": result,
        "pnl_points": round(pnl_points, 2),
        "pnl_yen": round(pnl_yen, 2),
        "hold_minutes": (pd.Timestamp(exit_time) - pd.Timestamp(entry_time)).total_seconds() / 60,
    }


def run_parameter_grid(events_with_data: list[dict]) -> pd.DataFrame:
    """パラメータグリッドサーチを実行。"""
    all_results = []
    param_combos = list(product(ENTRY_DELAYS, TAKE_PROFITS, STOP_LOSSES, HOLD_LIMITS))
    print(f"Parameter combinations: {len(param_combos)}")
    print(f"Events with intraday data: {len(events_with_data)}")
    print(f"Total simulations: {len(param_combos) * len(events_with_data)}")

    for ed, tp, sl, hl in param_combos:
        combo_pnl = 0
        combo_trades = 0
        combo_wins = 0

        for evt in events_with_data:
            trade = simulate_trade_5min(
                evt["session"], evt["gap_yen"], ed, tp, sl, hl
            )
            if trade is None:
                continue

            combo_trades += 1
            combo_pnl += trade["pnl_yen"]
            if trade["result"] == "TP":
                combo_wins += 1

        if combo_trades > 0:
            all_results.append({
                "entry_delay": ed,
                "take_profit_pct": tp,
                "stop_loss_pct": sl,
                "hold_limit_min": hl,
                "n_trades": combo_trades,
                "total_pnl": round(combo_pnl, 2),
                "win_rate": round(combo_wins / combo_trades * 100, 2),
                "avg_pnl": round(combo_pnl / combo_trades, 2),
            })

    return pd.DataFrame(all_results)


def simulate_daily_fallback(event_reactions_df: pd.DataFrame) -> pd.DataFrame:
    """5分足データがない場合、日足ベースでパラメータ感度分析。"""
    print("\n■ 日足ベース パラメータ感度分析（5分足データなし時のフォールバック）")

    results = []
    for tp_pct in TAKE_PROFITS:
        for sl_pct in STOP_LOSSES:
            trades = 0
            wins = 0
            total_pnl = 0

            for _, row in event_reactions_df.iterrows():
                gap = row["gap_yen"]
                if abs(gap) < 100:
                    continue

                surprise = row.get("surprise_score", 0) or 0
                if surprise < 10:
                    continue

                max_rev = row["max_reversion_pct"]
                actual_rev = row["reversion_pct"]

                trades += 1

                if max_rev >= tp_pct:
                    pnl = abs(gap) * tp_pct / 100
                    wins += 1
                elif max_rev < -sl_pct:
                    pnl = -abs(gap) * sl_pct / 100
                else:
                    if actual_rev > 0:
                        pnl = abs(gap) * min(actual_rev, tp_pct) / 100
                    else:
                        pnl = max(abs(gap) * actual_rev / 100, -abs(gap) * sl_pct / 100)

                net = pnl * MICRO_MULTIPLIER - COMMISSION * 2
                total_pnl += net

            if trades > 0:
                results.append({
                    "take_profit_pct": tp_pct,
                    "stop_loss_pct": sl_pct,
                    "n_trades": trades,
                    "total_pnl": round(total_pnl, 2),
                    "win_rate": round(wins / trades * 100, 2),
                    "avg_pnl": round(total_pnl / trades, 2),
                })

    return pd.DataFrame(results)


def main():
    # イベント反応データ読み込み
    reactions_path = DATA_DIR / "event_reactions.csv"
    if not reactions_path.exists():
        print("ERROR: event_reactions.csv not found. Run fetch_data.py first.")
        sys.exit(1)

    reactions_df = pd.read_csv(reactions_path)

    # 5分足データのあるイベントを収集
    events_with_data = []
    for _, row in reactions_df.iterrows():
        intraday = load_intraday_data(row["reaction_date"])
        if intraday is not None and not intraday.empty:
            session = extract_session_data(intraday, row["reaction_date"])
            if not session.empty:
                events_with_data.append({
                    "event_date": row["event_date"],
                    "reaction_date": row["reaction_date"],
                    "speaker": row["speaker"],
                    "gap_yen": row["gap_yen"],
                    "session": session,
                })

    print(f"Events with 5-min data: {len(events_with_data)} / {len(reactions_df)}")

    if events_with_data:
        # 5分足グリッドサーチ
        grid_results = run_parameter_grid(events_with_data)
        if not grid_results.empty:
            grid_results = grid_results.sort_values("total_pnl", ascending=False)
            print("\n■ Top 10 パラメータ組み合わせ（累積P&L順）")
            print(grid_results.head(10).to_string(index=False))

            grid_results.to_csv(DATA_DIR / "5min_grid_results.csv", index=False)
    else:
        print("No 5-min intraday data available (events >60 days ago)")

    # 日足フォールバック
    daily_results = simulate_daily_fallback(reactions_df)
    if not daily_results.empty:
        daily_results = daily_results.sort_values("total_pnl", ascending=False)
        print("\n■ 日足ベース Top 10 パラメータ組み合わせ")
        print(daily_results.head(10).to_string(index=False))
        daily_results.to_csv(DATA_DIR / "daily_grid_results.csv", index=False)

    print("\nDone.")


if __name__ == "__main__":
    main()
