"""
Phase 1-B補完: Claudeスコアと実際の日経反応の相関検証。
claude_scorer.pyの出力とevent_reactions.csvを結合し、
ハト派/タカ派スコアとギャップ・戻し率の相関を検証する。
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

DATA_DIR = Path(__file__).parent.parent / "data" / "market_data"


def load_claude_scores() -> pd.DataFrame | None:
    """Claude APIスコアリング結果を読み込む。"""
    path = DATA_DIR / "claude_scores.json"
    if not path.exists():
        print("claude_scores.json not found. Run claude_scorer.py first.")
        return None
    with open(path) as f:
        data = json.load(f)
    return pd.DataFrame(data)


def load_event_reactions() -> pd.DataFrame:
    """イベント反応データを読み込む。"""
    path = DATA_DIR / "event_reactions.csv"
    if not path.exists():
        print("ERROR: event_reactions.csv not found. Run fetch_data.py first.")
        sys.exit(1)
    return pd.read_csv(path)


def compute_correlations(merged: pd.DataFrame) -> dict:
    """スコアと市場反応の相関を計算する。"""
    results = {}

    pairs = [
        ("hawkish_score_claude", "gap_yen"),
        ("hawkish_score_claude", "intraday_move"),
        ("hawkish_score_claude", "reversion_pct"),
        ("surprise_score_claude", "gap_yen"),
        ("surprise_score_claude", "reversion_pct"),
        ("surprise_score_claude", "max_reversion_pct"),
    ]

    for x_col, y_col in pairs:
        if x_col not in merged.columns or y_col not in merged.columns:
            continue

        valid = merged[[x_col, y_col]].dropna()
        if len(valid) < 3:
            continue

        x = valid[x_col].values
        y = valid[y_col].values

        # ピアソン相関
        r, p = stats.pearsonr(x, y)
        # スピアマン順位相関
        rho, p_rho = stats.spearmanr(x, y)

        results[f"{x_col}_vs_{y_col}"] = {
            "n": len(valid),
            "pearson_r": round(r, 4),
            "pearson_p": round(p, 6),
            "spearman_rho": round(rho, 4),
            "spearman_p": round(p_rho, 6),
            "significant_5pct": p < 0.05 or p_rho < 0.05,
        }

    return results


def use_event_scores_as_proxy(reactions: pd.DataFrame) -> dict:
    """
    Claude APIスコアがない場合、events.jsonの手動スコアで相関検証。
    """
    print("\n■ 手動スコア vs 市場反応の相関（Claude APIスコアの代理）")

    # FOMCイベントのみ（hawkish_scoreが数値のもの）
    fomc = reactions[reactions["event_type"] == "FOMC"].copy()
    fomc["hawkish_score"] = pd.to_numeric(fomc["hawkish_score"], errors="coerce")
    fomc["surprise_score"] = pd.to_numeric(fomc["surprise_score"], errors="coerce")
    fomc = fomc.dropna(subset=["hawkish_score"])

    if len(fomc) < 3:
        print("  Not enough FOMC events with scores.")
        return {}

    results = {}
    pairs = [
        ("hawkish_score", "gap_yen", "タカ派度 vs ギャップ"),
        ("hawkish_score", "intraday_move", "タカ派度 vs 日中動き"),
        ("surprise_score", "gap_yen", "サプライズ度 vs ギャップ（絶対値）"),
        ("surprise_score", "reversion_pct", "サプライズ度 vs 戻し率"),
    ]

    for x_col, y_col, label in pairs:
        valid = fomc[[x_col, y_col]].dropna()
        if len(valid) < 3:
            continue

        x = valid[x_col].values
        # サプライズ度 vs ギャップは絶対値で見る
        y = np.abs(valid[y_col].values) if "surprise" in x_col and "gap" in y_col else valid[y_col].values

        r, p = stats.pearsonr(x, y)
        rho, p_rho = stats.spearmanr(x, y)

        sig = "★" if p < 0.05 or p_rho < 0.05 else ""
        print(f"  {label}: r={r:.3f}(p={p:.4f}) ρ={rho:.3f}(p={p_rho:.4f}) {sig}")

        results[f"{x_col}_vs_{y_col}"] = {
            "n": len(valid),
            "pearson_r": round(r, 4),
            "pearson_p": round(p, 6),
            "spearman_rho": round(rho, 4),
            "spearman_p": round(p_rho, 6),
        }

    # 全イベント（トランプ含む）: サプライズ度 vs |ギャップ|
    all_events = reactions.copy()
    all_events["surprise_score"] = pd.to_numeric(all_events["surprise_score"], errors="coerce")
    valid_all = all_events[["surprise_score", "gap_yen"]].dropna()
    if len(valid_all) >= 3:
        x = valid_all["surprise_score"].values
        y = np.abs(valid_all["gap_yen"].values)
        r, p = stats.pearsonr(x, y)
        print(f"\n  全イベント サプライズ度 vs |ギャップ|: r={r:.3f}(p={p:.4f}) N={len(valid_all)}")

    return results


def main():
    reactions = load_event_reactions()

    # まずClaude APIスコアで相関検証を試みる
    scores = load_claude_scores()

    if scores is not None and not scores.empty:
        # スコアとイベント反応をマージ
        scores = scores.rename(columns={
            "hawkish_score": "hawkish_score_claude",
            "surprise_score": "surprise_score_claude",
        })
        merged = reactions.merge(scores, left_on="event_date", right_on="date", how="inner")
        print(f"Merged {len(merged)} events with Claude scores")

        corr_results = compute_correlations(merged)

        print("\n■ Claude APIスコア vs 市場反応の相関")
        for key, val in corr_results.items():
            sig = "★有意" if val["significant_5pct"] else ""
            print(f"  {key}: r={val['pearson_r']:.3f}(p={val['pearson_p']:.4f}) "
                  f"ρ={val['spearman_rho']:.3f}(p={val['spearman_p']:.4f}) {sig}")

        # 結果保存
        with open(DATA_DIR / "correlation_results.json", "w") as f:
            json.dump(corr_results, f, indent=2)
    else:
        print("Claude APIスコアなし。手動スコアで代理検証。")

    # 手動スコアでの代理検証（常に実行）
    proxy_results = use_event_scores_as_proxy(reactions)

    # 結合結果保存
    with open(DATA_DIR / "correlation_proxy_results.json", "w") as f:
        json.dump(proxy_results, f, indent=2, ensure_ascii=False)

    print("\nDone.")


if __name__ == "__main__":
    main()
