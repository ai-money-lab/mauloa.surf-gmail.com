"""
Phase 1-A: イベント反応の統計分析。
fetch_data.pyの出力を読み込み、以下を計算する：
- 日中戻し率の統計量（平均・中央値・標準偏差・最小・最大）
- 戻し率30%以上の確率
- 発言者別の統計
- scalp_reverse戦略のP&Lシミュレーション
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

DATA_DIR = Path(__file__).parent.parent / "data" / "market_data"
MICRO_MULTIPLIER = 100  # 日経225マイクロ先物: 100円/ポイント
COMMISSION = 11  # 片道手数料（円）
MAX_CONTRACTS = 2
INITIAL_CAPITAL = 100_000  # 10万円


def load_event_reactions() -> pd.DataFrame:
    """event_reactions.csvを読み込む。"""
    path = DATA_DIR / "event_reactions.csv"
    if not path.exists():
        print("ERROR: event_reactions.csv not found. Run fetch_data.py first.")
        sys.exit(1)
    df = pd.read_csv(path)
    print(f"Loaded {len(df)} event reactions")
    return df


def compute_statistics(df: pd.DataFrame) -> dict:
    """戻し率の統計量を計算する。"""
    rev = df["reversion_pct"].dropna()
    max_rev = df["max_reversion_pct"].dropna()

    result = {
        "n_events": len(df),
        "reversion_pct": {
            "mean": round(rev.mean(), 2),
            "median": round(rev.median(), 2),
            "std": round(rev.std(), 2),
            "min": round(rev.min(), 2),
            "max": round(rev.max(), 2),
            "pct_above_30": round((rev >= 30).mean() * 100, 2),
            "pct_above_0": round((rev > 0).mean() * 100, 2),
        },
        "max_reversion_pct": {
            "mean": round(max_rev.mean(), 2),
            "median": round(max_rev.median(), 2),
            "std": round(max_rev.std(), 2),
            "min": round(max_rev.min(), 2),
            "max": round(max_rev.max(), 2),
        },
    }

    # 統計的有意性: 戻し率が0より有意に大きいか
    if len(rev) > 2:
        t_stat, p_value = stats.ttest_1samp(rev, 0)
        result["t_test_vs_zero"] = {
            "t_statistic": round(t_stat, 4),
            "p_value": round(p_value, 6),
            "significant_5pct": p_value < 0.05,
        }

    return result


def analyze_by_speaker(df: pd.DataFrame) -> dict:
    """発言者別の統計を計算する。"""
    results = {}
    for speaker in df["speaker"].unique():
        subset = df[df["speaker"] == speaker]
        results[speaker] = compute_statistics(subset)

        # ギャップの統計
        gaps = subset["gap_yen"].dropna()
        results[speaker]["gap_yen"] = {
            "mean_abs": round(gaps.abs().mean(), 2),
            "mean": round(gaps.mean(), 2),
            "std": round(gaps.std(), 2),
        }

        # 2日ドリフト
        drift = subset["drift_2d"].dropna()
        if len(drift) > 0:
            # ギャップと同方向にドリフトする割合
            aligned = subset.dropna(subset=["gap_yen", "drift_2d"])
            if len(aligned) > 0:
                same_dir = (aligned["gap_yen"] * aligned["drift_2d"] > 0).mean()
                results[speaker]["drift_2d"] = {
                    "mean": round(drift.mean(), 2),
                    "same_direction_pct": round(same_dir * 100, 2),
                }

    return results


def simulate_scalp_reverse(
    df: pd.DataFrame,
    take_profit_pct: float = 30.0,
    stop_loss_pct: float = 30.0,
    min_abs_gap: float = 100.0,
    min_surprise: float = 10,
) -> pd.DataFrame:
    """
    scalp_reverse戦略のシミュレーション。
    ギャップの逆方向にエントリーし、ギャップの一定%を利確/損切り。

    Parameters:
        take_profit_pct: ギャップの何%戻したら利確
        stop_loss_pct: ギャップの何%さらに進んだら損切り
        min_abs_gap: 最小ギャップ幅（円）
        min_surprise: 最小サプライズ度
    """
    trades = []
    capital = INITIAL_CAPITAL

    for _, row in df.iterrows():
        gap = row["gap_yen"]
        surprise = row.get("surprise_score", 0) or 0
        max_rev = row["max_reversion_pct"]

        # フィルタ: 最小ギャップ幅とサプライズ度
        if abs(gap) < min_abs_gap:
            continue
        if surprise < min_surprise:
            continue

        # エントリー: ギャップの逆方向
        # 利確: max_reversionがtake_profit_pct以上なら利確成功
        # 損切り: 日中に損切りラインに到達したか（max_reversionがマイナスなら）
        # 簡易シミュレーション: 終値ベースの戻し率で判定

        tp_yen = abs(gap) * take_profit_pct / 100  # 利確幅（円）
        sl_yen = abs(gap) * stop_loss_pct / 100  # 損切り幅（円）

        # max_reversion_pctが利確ラインを超えているか
        if max_rev >= take_profit_pct:
            # 利確到達
            pnl_per_point = tp_yen
            result = "WIN"
        elif max_rev < -stop_loss_pct:
            # 損切り到達（ギャップ方向にさらに進行）
            pnl_per_point = -sl_yen
            result = "LOSS"
        else:
            # 引けまで保持→終値ベースの戻し率で計算
            actual_reversion = row["reversion_pct"]
            if actual_reversion > 0:
                pnl_per_point = abs(gap) * min(actual_reversion, take_profit_pct) / 100
                result = "PARTIAL_WIN"
            else:
                pnl_per_point = abs(gap) * actual_reversion / 100  # negative
                pnl_per_point = max(pnl_per_point, -sl_yen)
                result = "PARTIAL_LOSS"

        # 損益計算（マイクロ先物1枚）
        contracts = min(MAX_CONTRACTS, max(1, int(capital // 26000)))
        pnl_yen = pnl_per_point * MICRO_MULTIPLIER * contracts
        commission = COMMISSION * 2 * contracts  # 往復
        net_pnl = pnl_yen - commission
        capital += net_pnl

        trades.append({
            "event_date": row["event_date"],
            "reaction_date": row["reaction_date"],
            "speaker": row["speaker"],
            "gap_yen": gap,
            "surprise_score": surprise,
            "max_reversion_pct": max_rev,
            "reversion_pct": row["reversion_pct"],
            "result": result,
            "pnl_per_point": round(pnl_per_point, 2),
            "contracts": contracts,
            "gross_pnl": round(pnl_yen, 2),
            "commission": commission,
            "net_pnl": round(net_pnl, 2),
            "capital": round(capital, 2),
        })

    return pd.DataFrame(trades)


def print_report(stats_all: dict, stats_by_speaker: dict, trades_df: pd.DataFrame):
    """分析レポートを出力する。"""
    print("=" * 70)
    print("CITS Phase 1-A: イベント反応分析レポート")
    print("=" * 70)

    print(f"\n■ 全イベント統計 (N={stats_all['n_events']})")
    rev = stats_all["reversion_pct"]
    print(f"  日中戻し率: 平均{rev['mean']:.1f}% / 中央値{rev['median']:.1f}% / σ={rev['std']:.1f}%")
    print(f"  戻し率>0%の確率: {rev['pct_above_0']:.1f}%")
    print(f"  戻し率≥30%の確率: {rev['pct_above_30']:.1f}%")

    max_rev = stats_all["max_reversion_pct"]
    print(f"  日中最大戻し率: 平均{max_rev['mean']:.1f}% / 中央値{max_rev['median']:.1f}%")

    if "t_test_vs_zero" in stats_all:
        tt = stats_all["t_test_vs_zero"]
        sig = "★有意" if tt["significant_5pct"] else "有意でない"
        print(f"  t検定(H0: 戻し率=0): t={tt['t_statistic']:.3f}, p={tt['p_value']:.6f} → {sig}")

    print(f"\n■ 発言者別統計")
    for speaker, s in stats_by_speaker.items():
        print(f"\n  [{speaker.upper()}] (N={s['n_events']})")
        rev = s["reversion_pct"]
        print(f"    戻し率: 平均{rev['mean']:.1f}% / 中央値{rev['median']:.1f}%")
        print(f"    戻し率≥30%: {rev['pct_above_30']:.1f}%")
        if "gap_yen" in s:
            g = s["gap_yen"]
            print(f"    ギャップ: 平均|{g['mean_abs']:.0f}|円 (σ={g['std']:.0f})")
        if "drift_2d" in s:
            d = s["drift_2d"]
            print(f"    2日ドリフト同方向率: {d['same_direction_pct']:.1f}%")

    if not trades_df.empty:
        print(f"\n■ scalp_reverse戦略シミュレーション")
        print(f"  トレード数: {len(trades_df)}")
        wins = trades_df[trades_df["result"].str.contains("WIN")]
        losses = trades_df[trades_df["result"].str.contains("LOSS")]
        print(f"  勝ち: {len(wins)} / 負け: {len(losses)}")
        if len(trades_df) > 0:
            win_rate = len(wins) / len(trades_df) * 100
            print(f"  勝率: {win_rate:.1f}%")
        total_pnl = trades_df["net_pnl"].sum()
        print(f"  累積損益: ¥{total_pnl:,.0f}")
        print(f"  最終資金: ¥{trades_df['capital'].iloc[-1]:,.0f} (初期: ¥{INITIAL_CAPITAL:,})")
        print(f"  最大単発損失: ¥{trades_df['net_pnl'].min():,.0f}")
        print(f"  最大単発利益: ¥{trades_df['net_pnl'].max():,.0f}")
        print(f"\n  トレード詳細:")
        for _, t in trades_df.iterrows():
            print(f"    {t['reaction_date']} {t['speaker']:8s} gap={t['gap_yen']:+.0f} "
                  f"rev={t['reversion_pct']:+.1f}% → {t['result']:12s} ¥{t['net_pnl']:+,.0f} "
                  f"(残高¥{t['capital']:,.0f})")

    print("\n" + "=" * 70)


def main():
    # 1. データ読み込み
    df = load_event_reactions()

    # 2. 全体統計
    stats_all = compute_statistics(df)

    # 3. 発言者別統計
    stats_by_speaker = analyze_by_speaker(df)

    # 4. scalp_reverse戦略シミュレーション
    trades_df = simulate_scalp_reverse(df)

    # 5. レポート出力
    print_report(stats_all, stats_by_speaker, trades_df)

    # 6. 結果保存
    output_dir = DATA_DIR
    import json
    report = {
        "all_events": stats_all,
        "by_speaker": stats_by_speaker,
    }

    # Convert numpy bools to Python bools for JSON serialization
    def convert_types(obj):
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, dict):
            return {k: convert_types(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert_types(i) for i in obj]
        return obj

    report = convert_types(report)
    with open(output_dir / "analysis_report.json", "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    if not trades_df.empty:
        trades_df.to_csv(output_dir / "scalp_reverse_trades.csv", index=False)

    print(f"\nResults saved to {output_dir}")
    return stats_all, stats_by_speaker, trades_df


if __name__ == "__main__":
    main()
