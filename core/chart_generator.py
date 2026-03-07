"""チャート・グラフ自動生成モジュール

不動産レポート用のグラフ画像を自動生成する。
matplotlib + 日本語フォントでPNG画像を出力し、PDFに埋め込む。
"""

import logging
import os
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # GUI不要
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

logger = logging.getLogger(__name__)

# --- 日本語フォント設定 ---
_JP_FONTS = ["Yu Gothic", "Meiryo", "MS Gothic"]

def _setup_japanese_font():
    """Windows標準の日本語フォントを設定"""
    from matplotlib import font_manager
    for font_name in _JP_FONTS:
        fonts = font_manager.findSystemFonts()
        for fpath in fonts:
            try:
                fp = font_manager.FontProperties(fname=fpath)
                if font_name.lower() in fp.get_name().lower():
                    plt.rcParams["font.family"] = fp.get_name()
                    plt.rcParams["axes.unicode_minus"] = False
                    logger.info(f"Japanese font set: {fp.get_name()}")
                    return
            except Exception:
                continue
    logger.warning("Japanese font not found, using default")

_setup_japanese_font()

# --- カラーパレット ---
COLORS = {
    "primary": "#1A2140",
    "secondary": "#0F3460",
    "accent": "#E94560",
    "blue": "#3B82F6",
    "green": "#10B981",
    "orange": "#F59E0B",
    "red": "#EF4444",
    "gray": "#6B7280",
    "light_bg": "#F8F9FA",
    "grid": "#E5E7EB",
}

PALETTE = [COLORS["blue"], COLORS["accent"], COLORS["green"],
           COLORS["orange"], COLORS["primary"], COLORS["gray"]]


class ChartGenerator:
    """不動産レポート用チャート生成"""

    def __init__(self, output_dir: str = "data/charts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dpi = 150
        self.figsize_standard = (8, 5)
        self.figsize_wide = (10, 5)
        self.figsize_small = (6, 4)

    def _save(self, fig, filename: str) -> str:
        """figを保存してパスを返す"""
        path = self.output_dir / filename
        fig.savefig(str(path), dpi=self.dpi, bbox_inches="tight",
                    facecolor="white", edgecolor="none")
        plt.close(fig)
        logger.info(f"Chart saved: {path}")
        return str(path)

    # ======================================================
    # 人口動態グラフ（棒グラフ + 折れ線）
    # ======================================================
    def population_trend(
        self,
        years: list,
        populations: list,
        growth_rates: list,
        area_name: str = "",
        filename: str = "population_trend.png",
    ) -> str:
        """人口推移の棒グラフ + 増減率の折れ線"""
        fig, ax1 = plt.subplots(figsize=self.figsize_standard)

        # 棒グラフ（人口）
        bars = ax1.bar(years, populations, color=COLORS["blue"], alpha=0.7,
                       width=0.6, label="人口")
        ax1.set_xlabel("年", fontsize=11)
        ax1.set_ylabel("人口（人）", fontsize=11, color=COLORS["blue"])
        ax1.tick_params(axis="y", labelcolor=COLORS["blue"])
        ax1.yaxis.set_major_formatter(ticker.FuncFormatter(
            lambda x, p: f"{x:,.0f}"))
        ax1.set_ylim(min(populations) * 0.98, max(populations) * 1.02)

        # 折れ線（増減率）
        ax2 = ax1.twinx()
        ax2.plot(years, growth_rates, color=COLORS["accent"], marker="o",
                 linewidth=2, markersize=6, label="対前年比(%)")
        ax2.set_ylabel("対前年比(%)", fontsize=11, color=COLORS["accent"])
        ax2.tick_params(axis="y", labelcolor=COLORS["accent"])
        ax2.axhline(y=0, color=COLORS["gray"], linestyle="--", alpha=0.5)

        title = f"{area_name} 人口推移" if area_name else "人口推移"
        ax1.set_title(title, fontsize=14, fontweight="bold", pad=15)
        ax1.grid(axis="y", alpha=0.3)

        # 凡例
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

        fig.tight_layout()
        return self._save(fig, filename)

    # ======================================================
    # 地価推移グラフ（折れ線）
    # ======================================================
    def land_price_trend(
        self,
        years: list,
        prices: list,
        growth_rates: Optional[list] = None,
        area_name: str = "",
        price_label: str = "公示地価（万円/㎡）",
        filename: str = "land_price_trend.png",
    ) -> str:
        """地価推移の折れ線グラフ"""
        fig, ax1 = plt.subplots(figsize=self.figsize_standard)

        ax1.plot(years, prices, color=COLORS["primary"], marker="s",
                 linewidth=2.5, markersize=7, label=price_label)
        ax1.fill_between(years, prices, alpha=0.1, color=COLORS["primary"])
        ax1.set_xlabel("年", fontsize=11)
        ax1.set_ylabel(price_label, fontsize=11)
        ax1.yaxis.set_major_formatter(ticker.FuncFormatter(
            lambda x, p: f"{x:.1f}"))

        if growth_rates:
            ax2 = ax1.twinx()
            ax2.bar(years, growth_rates, color=COLORS["green"], alpha=0.3,
                    width=0.4, label="対前年比(%)")
            ax2.set_ylabel("対前年比(%)", fontsize=11, color=COLORS["green"])
            ax2.tick_params(axis="y", labelcolor=COLORS["green"])
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
        else:
            ax1.legend(loc="upper left")

        title = f"{area_name} 地価推移" if area_name else "地価推移"
        ax1.set_title(title, fontsize=14, fontweight="bold", pad=15)
        ax1.grid(axis="y", alpha=0.3)

        fig.tight_layout()
        return self._save(fig, filename)

    # ======================================================
    # 賃料相場ヒートマップ
    # ======================================================
    def rental_heatmap(
        self,
        categories: list,
        age_groups: list,
        data: list,
        area_name: str = "",
        filename: str = "rental_heatmap.png",
    ) -> str:
        """賃料相場のヒートマップ（間取り×築年数）"""
        fig, ax = plt.subplots(figsize=self.figsize_standard)

        arr = np.array(data)
        im = ax.imshow(arr, cmap="YlOrRd", aspect="auto")

        ax.set_xticks(range(len(age_groups)))
        ax.set_xticklabels(age_groups, fontsize=10)
        ax.set_yticks(range(len(categories)))
        ax.set_yticklabels(categories, fontsize=10)

        # 値をセルに表示
        for i in range(len(categories)):
            for j in range(len(age_groups)):
                val = arr[i, j]
                color = "white" if val > arr.mean() else "black"
                ax.text(j, i, f"{val:,.0f}", ha="center", va="center",
                        fontsize=10, color=color, fontweight="bold")

        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label("賃料（円）", fontsize=10)

        title = f"{area_name} 賃料相場マップ" if area_name else "賃料相場マップ"
        ax.set_title(title, fontsize=14, fontweight="bold", pad=15)

        fig.tight_layout()
        return self._save(fig, filename)

    # ======================================================
    # 空室率推移（折れ線比較）
    # ======================================================
    def vacancy_rate_comparison(
        self,
        years: list,
        area_rates: list,
        avg_rates: list,
        area_name: str = "",
        filename: str = "vacancy_rate.png",
    ) -> str:
        """空室率の推移比較（対象エリア vs 平均）"""
        fig, ax = plt.subplots(figsize=self.figsize_standard)

        ax.plot(years, area_rates, color=COLORS["blue"], marker="o",
                linewidth=2.5, markersize=7, label=area_name or "対象エリア")
        ax.plot(years, avg_rates, color=COLORS["gray"], marker="^",
                linewidth=2, markersize=6, linestyle="--", label="23区平均")
        ax.fill_between(years, area_rates, avg_rates, alpha=0.1,
                        color=COLORS["blue"])

        ax.set_xlabel("年", fontsize=11)
        ax.set_ylabel("空室率(%)", fontsize=11)
        ax.set_title("空室率推移", fontsize=14, fontweight="bold", pad=15)
        ax.legend(loc="upper right", fontsize=10)
        ax.grid(axis="y", alpha=0.3)

        fig.tight_layout()
        return self._save(fig, filename)

    # ======================================================
    # 収益シミュレーション比較（横棒グラフ）
    # ======================================================
    def yield_comparison(
        self,
        scenarios: list,
        gross_yields: list,
        net_yields: list,
        filename: str = "yield_comparison.png",
    ) -> str:
        """収益シミュレーション3パターン比較"""
        fig, ax = plt.subplots(figsize=self.figsize_small)

        y_pos = np.arange(len(scenarios))
        bar_height = 0.35

        bars1 = ax.barh(y_pos - bar_height/2, gross_yields, bar_height,
                        color=COLORS["blue"], alpha=0.8, label="表面利回り")
        bars2 = ax.barh(y_pos + bar_height/2, net_yields, bar_height,
                        color=COLORS["green"], alpha=0.8, label="実質利回り")

        ax.set_yticks(y_pos)
        ax.set_yticklabels(scenarios, fontsize=11)
        ax.set_xlabel("利回り(%)", fontsize=11)
        ax.set_title("収益シミュレーション比較", fontsize=14,
                     fontweight="bold", pad=15)
        ax.legend(loc="lower right")

        # 値表示
        for bar in bars1:
            width = bar.get_width()
            ax.text(width + 0.05, bar.get_y() + bar.get_height()/2,
                    f"{width:.1f}%", va="center", fontsize=10)
        for bar in bars2:
            width = bar.get_width()
            ax.text(width + 0.05, bar.get_y() + bar.get_height()/2,
                    f"{width:.1f}%", va="center", fontsize=10)

        ax.grid(axis="x", alpha=0.3)
        fig.tight_layout()
        return self._save(fig, filename)

    # ======================================================
    # リフォームコスト比較（積み上げ棒グラフ）
    # ======================================================
    def renovation_cost_breakdown(
        self,
        plans: list,
        categories: list,
        costs: list,
        filename: str = "renovation_cost.png",
    ) -> str:
        """リフォーム費用のプラン別積み上げ棒グラフ

        costs: [[plan1_cat1, plan1_cat2, ...], [plan2_cat1, ...], ...]
        """
        fig, ax = plt.subplots(figsize=self.figsize_standard)

        x = np.arange(len(plans))
        width = 0.5
        bottom = np.zeros(len(plans))

        for i, cat in enumerate(categories):
            values = [costs[j][i] for j in range(len(plans))]
            bars = ax.bar(x, values, width, bottom=bottom,
                         label=cat, color=PALETTE[i % len(PALETTE)], alpha=0.85)
            bottom += values

        ax.set_xticks(x)
        ax.set_xticklabels(plans, fontsize=11)
        ax.set_ylabel("費用（万円）", fontsize=11)
        ax.set_title("リフォーム費用プラン別比較", fontsize=14,
                     fontweight="bold", pad=15)
        ax.legend(loc="upper left", fontsize=9, ncol=2)
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(
            lambda x, p: f"{x:,.0f}"))
        ax.grid(axis="y", alpha=0.3)

        # 合計値を棒の上に表示
        for i, total in enumerate(bottom):
            ax.text(i, total + 5, f"{total:,.0f}万円",
                    ha="center", fontsize=10, fontweight="bold")

        fig.tight_layout()
        return self._save(fig, filename)

    # ======================================================
    # 売却価格推定の手法別比較
    # ======================================================
    def price_estimation_methods(
        self,
        methods: list,
        prices: list,
        weights: list,
        weighted_avg: float,
        filename: str = "price_estimation.png",
    ) -> str:
        """売却価格の推定手法別比較"""
        fig, ax = plt.subplots(figsize=self.figsize_standard)

        colors = [PALETTE[i % len(PALETTE)] for i in range(len(methods))]
        bars = ax.bar(methods, prices, color=colors, alpha=0.8, width=0.5)

        # ウェイト表示
        for i, (bar, w) in enumerate(zip(bars, weights)):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 20,
                    f"ウェイト: {w}%", ha="center", fontsize=9, color=COLORS["gray"])

        # 加重平均ライン
        ax.axhline(y=weighted_avg, color=COLORS["accent"], linewidth=2,
                   linestyle="--", label=f"加重平均: {weighted_avg:,.0f}万円")

        ax.set_ylabel("推定価格（万円）", fontsize=11)
        ax.set_title("売却価格推定 手法別比較", fontsize=14,
                     fontweight="bold", pad=15)
        ax.legend(loc="upper right", fontsize=10)
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(
            lambda x, p: f"{x:,.0f}"))
        ax.grid(axis="y", alpha=0.3)

        fig.tight_layout()
        return self._save(fig, filename)

    # ======================================================
    # 世帯構成の円グラフ
    # ======================================================
    def household_composition(
        self,
        labels: list,
        sizes: list,
        area_name: str = "",
        filename: str = "household_composition.png",
    ) -> str:
        """世帯構成の円グラフ"""
        fig, ax = plt.subplots(figsize=self.figsize_small)

        colors = PALETTE[:len(labels)]
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, colors=colors, autopct="%1.1f%%",
            startangle=90, pctdistance=0.75,
            textprops={"fontsize": 10},
        )
        for at in autotexts:
            at.set_fontsize(9)
            at.set_fontweight("bold")

        title = f"{area_name} 世帯構成" if area_name else "世帯構成"
        ax.set_title(title, fontsize=14, fontweight="bold", pad=15)

        fig.tight_layout()
        return self._save(fig, filename)

    # ======================================================
    # 賃料設定シミュレーション
    # ======================================================
    def rent_simulation(
        self,
        rent_levels: list,
        vacancy_weeks: list,
        annual_incomes: list,
        recommended_idx: int = 1,
        filename: str = "rent_simulation.png",
    ) -> str:
        """賃料設定別の年間収入シミュレーション"""
        fig, ax1 = plt.subplots(figsize=self.figsize_standard)

        colors = [COLORS["accent"] if i == recommended_idx else COLORS["blue"]
                  for i in range(len(rent_levels))]
        bars = ax1.bar(
            [f"{r:,}円" for r in rent_levels], annual_incomes,
            color=colors, alpha=0.8, width=0.5,
        )

        # 推奨マーク
        if 0 <= recommended_idx < len(rent_levels):
            bars[recommended_idx].set_edgecolor(COLORS["accent"])
            bars[recommended_idx].set_linewidth(2)

        ax1.set_ylabel("年間実質収入（円）", fontsize=11)
        ax1.yaxis.set_major_formatter(ticker.FuncFormatter(
            lambda x, p: f"{x:,.0f}"))

        # 空室期間の折れ線
        ax2 = ax1.twinx()
        ax2.plot([f"{r:,}円" for r in rent_levels], vacancy_weeks,
                 color=COLORS["orange"], marker="D", linewidth=2,
                 markersize=7, label="想定空室期間（週）")
        ax2.set_ylabel("想定空室期間（週）", fontsize=11, color=COLORS["orange"])
        ax2.tick_params(axis="y", labelcolor=COLORS["orange"])

        ax1.set_title("賃料設定シミュレーション", fontsize=14,
                     fontweight="bold", pad=15)
        ax2.legend(loc="upper right")
        ax1.grid(axis="y", alpha=0.3)

        fig.tight_layout()
        return self._save(fig, filename)

    # ======================================================
    # 季節別成約率
    # ======================================================
    def seasonal_transaction_rate(
        self,
        months: list,
        rates: list,
        filename: str = "seasonal_rate.png",
    ) -> str:
        """月別成約率のレーダーチャート風棒グラフ"""
        fig, ax = plt.subplots(figsize=self.figsize_standard)

        colors = [COLORS["accent"] if r >= 110 else
                  COLORS["blue"] if r >= 90 else
                  COLORS["gray"] for r in rates]

        bars = ax.bar(months, rates, color=colors, alpha=0.8, width=0.6)
        ax.axhline(y=100, color=COLORS["primary"], linewidth=1.5,
                   linestyle="--", label="年間平均(100%)")

        ax.set_ylabel("成約率（年間平均=100%）", fontsize=11)
        ax.set_title("月別成約率（売却タイミング分析）", fontsize=14,
                     fontweight="bold", pad=15)
        ax.legend()
        ax.grid(axis="y", alpha=0.3)

        # 値表示
        for bar, rate in zip(bars, rates):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f"{rate}%", ha="center", fontsize=9)

        fig.tight_layout()
        return self._save(fig, filename)

    # ======================================================
    # 投資スコアレーダーチャート
    # ======================================================
    def investment_radar(
        self,
        categories: list,
        scores: list,
        area_name: str = "",
        max_score: float = 5.0,
        filename: str = "investment_radar.png",
    ) -> str:
        """投資適性のレーダーチャート（多角形）

        categories: ["収益性", "安全性", "成長性", "流動性", "利便性"]
        scores: [4.2, 3.8, 4.5, 3.5, 4.0]
        """
        fig, ax = plt.subplots(figsize=(7, 7),
                               subplot_kw=dict(projection="polar"))

        num = len(categories)
        angles = np.linspace(0, 2 * np.pi, num, endpoint=False).tolist()
        scores_plot = scores + [scores[0]]
        angles_plot = angles + [angles[0]]

        ax.fill(angles_plot, scores_plot, color=COLORS["blue"], alpha=0.2)
        ax.plot(angles_plot, scores_plot, color=COLORS["blue"], linewidth=2.5,
                marker="o", markersize=8)

        for i, (angle, score) in enumerate(zip(angles, scores)):
            ax.text(angle, score + 0.35, f"{score:.1f}",
                    ha="center", va="center", fontsize=12,
                    fontweight="bold", color=COLORS["primary"])

        ax.set_xticks(angles)
        ax.set_xticklabels(categories, fontsize=12)
        ax.set_ylim(0, max_score)
        ax.set_yticks(np.arange(1, max_score + 1))
        ax.set_yticklabels([f"{int(v)}" for v in np.arange(1, max_score + 1)],
                           fontsize=9, color=COLORS["gray"])
        ax.grid(True, alpha=0.3)

        title = f"{area_name} 投資適性スコア" if area_name else "投資適性スコア"
        ax.set_title(title, fontsize=14, fontweight="bold", pad=25)

        fig.tight_layout()
        return self._save(fig, filename)

    # ======================================================
    # 再開発タイムライン（ガントチャート風）
    # ======================================================
    def redevelopment_timeline(
        self,
        projects: list,
        start_years: list,
        end_years: list,
        statuses: list = None,
        filename: str = "redevelopment_timeline.png",
    ) -> str:
        """再開発プロジェクトのタイムラインチャート"""
        fig, ax = plt.subplots(figsize=self.figsize_wide)

        n = len(projects)
        colors_map = {
            "完了": COLORS["green"],
            "着工中": COLORS["blue"],
            "計画中": COLORS["orange"],
            "完了間近": COLORS["accent"],
        }

        for i, (proj, start, end) in enumerate(
                zip(projects, start_years, end_years)):
            duration = end - start
            status = statuses[i] if statuses and i < len(statuses) else "計画中"
            color = colors_map.get(status, COLORS["gray"])

            ax.barh(i, duration, left=start, height=0.5,
                    color=color, alpha=0.85, edgecolor="white", linewidth=1)
            ax.text(start + duration / 2, i, f"{start}〜{end}年",
                    ha="center", va="center", fontsize=9,
                    color="white", fontweight="bold")
            if statuses and i < len(statuses):
                ax.text(end + 0.15, i, f" {statuses[i]}",
                        ha="left", va="center", fontsize=9,
                        color=color, fontweight="bold")

        ax.set_yticks(range(n))
        ax.set_yticklabels(projects, fontsize=11)
        ax.invert_yaxis()
        ax.axvline(x=2025.5, color=COLORS["accent"], linewidth=2,
                   linestyle="--", alpha=0.7, label="現在 (2025年)")
        ax.set_xlabel("年", fontsize=11)
        ax.set_title("再開発・インフラ計画タイムライン", fontsize=14,
                     fontweight="bold", pad=15)
        ax.legend(loc="lower right")
        ax.grid(axis="x", alpha=0.3)
        ax.set_axisbelow(True)

        fig.tight_layout()
        return self._save(fig, filename)

    # ======================================================
    # 総合スコアゲージ（半円メーター）
    # ======================================================
    def score_gauge(
        self,
        score: float,
        max_score: float = 5.0,
        label: str = "総合評価",
        sublabel: str = "",
        filename: str = "score_gauge.png",
    ) -> str:
        """半円ゲージで総合スコアを可視化"""
        fig, ax = plt.subplots(figsize=(7, 4))

        n_segments = 50
        ratio = min(score / max_score, 1.0)
        r_outer, r_inner = 1.0, 0.6

        def _segment_color(t):
            if t < 0.3:
                return COLORS["red"]
            elif t < 0.6:
                return COLORS["orange"]
            elif t < 0.8:
                return COLORS["blue"]
            return COLORS["green"]

        filled = int(ratio * n_segments)
        for i in range(n_segments):
            a0 = np.pi - (i / n_segments) * np.pi
            a1 = np.pi - ((i + 1) / n_segments) * np.pi
            theta = np.linspace(a0, a1, 10)
            x_o = np.cos(theta) * r_outer
            y_o = np.sin(theta) * r_outer
            x_i = np.cos(theta[::-1]) * r_inner
            y_i = np.sin(theta[::-1]) * r_inner
            x = np.concatenate([x_o, x_i])
            y = np.concatenate([y_o, y_i])
            if i < filled:
                ax.fill(x, y, color=_segment_color(i / n_segments), alpha=0.85)
            else:
                ax.fill(x, y, color="#E5E7EB", alpha=0.4)

        ax.text(0, 0.15, f"{score:.1f}", ha="center", va="center",
                fontsize=36, fontweight="bold", color=COLORS["primary"])
        ax.text(0, -0.08, f"/ {max_score:.1f}", ha="center", va="center",
                fontsize=14, color=COLORS["gray"])
        ax.text(0, -0.28, label, ha="center", va="center",
                fontsize=14, fontweight="bold", color=COLORS["primary"])
        if sublabel:
            ax.text(0, -0.42, sublabel, ha="center", va="center",
                    fontsize=12, color=COLORS["accent"])

        ax.set_xlim(-1.3, 1.3)
        ax.set_ylim(-0.55, 1.15)
        ax.set_aspect("equal")
        ax.axis("off")

        fig.tight_layout()
        return self._save(fig, filename)

    # ======================================================
    # 感度分析ヒートマップ（2D）
    # ======================================================
    def sensitivity_heatmap(
        self,
        x_labels: list,
        y_labels: list,
        values: list,
        x_title: str = "空室率(%)",
        y_title: str = "賃料変動(%)",
        value_label: str = "実質利回り(%)",
        filename: str = "sensitivity_heatmap.png",
    ) -> str:
        """2D感度分析ヒートマップ"""
        fig, ax = plt.subplots(figsize=self.figsize_standard)

        arr = np.array(values)
        im = ax.imshow(arr, cmap="RdYlGn", aspect="auto",
                       vmin=arr.min() - 0.5, vmax=arr.max() + 0.5)

        ax.set_xticks(range(len(x_labels)))
        ax.set_xticklabels(x_labels, fontsize=10)
        ax.set_yticks(range(len(y_labels)))
        ax.set_yticklabels(y_labels, fontsize=10)
        ax.set_xlabel(x_title, fontsize=11)
        ax.set_ylabel(y_title, fontsize=11)

        for i in range(len(y_labels)):
            for j in range(len(x_labels)):
                val = arr[i, j]
                color = "white" if val < arr.mean() else "black"
                ax.text(j, i, f"{val:.1f}%", ha="center", va="center",
                        fontsize=11, color=color, fontweight="bold")

        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label(value_label, fontsize=10)
        ax.set_title("感度分析（シナリオ別利回り）", fontsize=14,
                     fontweight="bold", pad=15)

        fig.tight_layout()
        return self._save(fig, filename)
