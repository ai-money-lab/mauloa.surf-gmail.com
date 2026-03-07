"""PDF生成モジュール - PremiumPDF（fpdf2ベース）

プロフェッショナル品質の「バイブル級」レポートPDFを生成する。
- PremiumPDFサブクラス: ヘッダー/フッター/ページ番号/透かし自動描画
- プレミアム表紙（ネイビー＋コーラルアクセント）
- H2: 全幅ネイビーバンド＋コーラル番号バッジ
- コールアウトボックス: KEY INSIGHT / RISK WARNING / ACTION / METRIC
- メトリックカード: CARD マーカー
- テーブル: モダンデザイン（縦罫線なし・数値右寄せ）
- PDFブックマーク自動生成
"""

import logging
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import markdown
import yaml
from jinja2 import Template

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

# --- カラーパレット ---
NAVY = (22, 33, 62)       # #16213E メインカラー
CORAL = (233, 69, 96)     # #E94560 アクセント
DARK_BLUE = (15, 52, 96)  # #0F3460 H3色
TEXT_DARK = (51, 51, 51)   # #333333 本文
TEXT_GRAY = (120, 120, 120)
WHITE = (255, 255, 255)
WATERMARK_GRAY = (240, 240, 243)   # 透かし色

# コールアウト色定義: (背景RGB, 左バーRGB, ラベル)
CALLOUT_STYLES = {
    "KEY INSIGHT": ((230, 240, 255), NAVY, "KEY INSIGHT"),
    "RISK WARNING": ((255, 248, 225), (217, 164, 6), "RISK WARNING"),
    "ACTION": ((225, 250, 235), (16, 185, 129), "ACTION"),
    "METRIC": ((240, 230, 255), (128, 90, 213), "METRIC"),
}

# --- レイアウト設定 ---
LINE_HEIGHT_BODY = 7          # 本文行高さ（mm）
LINE_HEIGHT_H3 = 10           # h3行高さ
LINE_HEIGHT_H4 = 9            # h4行高さ
SPACING_AFTER_H2 = 6          # h2後のスペース
SPACING_AFTER_H3 = 4          # h3後のスペース
SPACING_AFTER_H4 = 3          # h4後のスペース
SPACING_AFTER_TABLE = 5       # テーブル後のスペース
SPACING_AFTER_IMAGE = 6       # 画像後のスペース
SPACING_EMPTY_LINE = 3        # 空行のスペース（連続空行抑制あり）
MARGIN_LEFT = 15              # 左マージン
MARGIN_RIGHT = 15             # 右マージン
MARGIN_TOP = 18               # 上マージン（ヘッダー分）
MARGIN_BOTTOM = 20            # ページ下マージン
HEADER_HEIGHT = 14            # ヘッダー高さ
FOOTER_HEIGHT = 12            # フッター高さ
IMAGE_MAX_HEIGHT = 130        # 画像の最大高さ（mm）
PAGE_BREAK_THRESHOLD_H3 = 50  # h3の前にこれ以下の残りスペースなら改ページ
MAX_CONSECUTIVE_EMPTY = 2     # 連続空行の最大数


class PDFGenerator:
    """Markdown/Jinja2テンプレートからPDFを生成（PremiumPDF使用）"""

    def __init__(self):
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        self.header = config["system_b"]["pdf_template_header"]
        self.author = config["system_b"]["pdf_template_author"]
        self.templates_dir = Path(__file__).parent.parent / "templates"

    def render_template(self, template_name: str, data: dict) -> str:
        """テンプレートをデータで埋めてMarkdownを生成"""
        template_path = self.templates_dir / template_name
        with open(template_path, "r", encoding="utf-8") as f:
            template_text = f.read()

        template = Template(template_text)
        data["header"] = self.header
        data["author"] = self.author
        data["date"] = datetime.now(JST).strftime("%Y年%m月%d日")
        data["year"] = datetime.now(JST).strftime("%Y")

        return template.render(**data)

    def markdown_to_html(self, md_text: str) -> str:
        """MarkdownをHTMLに変換"""
        html_body = markdown.markdown(
            md_text,
            extensions=["tables", "toc", "fenced_code"],
        )
        return f"""<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8"></head>
<body>
{html_body}
</body>
</html>"""

    def _remaining_space(self, pdf) -> float:
        """現在ページの残りスペース（mm）"""
        return pdf.h - pdf.get_y() - MARGIN_BOTTOM

    # =====================================================
    # メイン生成: Markdown → PremiumPDF
    # =====================================================
    def generate_pdf(self, md_text: str, output_path: str) -> str:
        """MarkdownからプレミアムPDFを生成"""
        from fpdf import FPDF

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        # --- PremiumPDFサブクラス（ヘッダー/フッター/透かし自動描画）---
        font_path = self._find_japanese_font()
        bold_path = self._find_japanese_font(bold=True)
        report_header_text = self.header

        class PremiumPDF(FPDF):
            """プレミアム版PDF - 全ページに自動的にヘッダー/フッター/透かし"""

            def __init__(self):
                super().__init__()
                self._is_cover_page = True
                self._current_section = ""
                self._report_title = ""
                self._font_name = "Helvetica"

            def header(self):
                """全ページ上部: ネイビーアクセントバー + レポート名 + セクション名"""
                if self.page == 1:  # 表紙はページ1
                    return

                # 薄いネイビーライン（上端）
                self.set_draw_color(*NAVY)
                self.set_line_width(0.8)
                self.line(MARGIN_LEFT, 8, self.w - MARGIN_RIGHT, 8)

                # レポート名（左）
                self.set_font(self._font_name, "", 7)
                self.set_text_color(*TEXT_GRAY)
                self.set_xy(MARGIN_LEFT, 9.5)
                self.cell(80, 5, report_header_text, align="L")

                # セクション名（右）
                if self._current_section:
                    self.set_xy(self.w - MARGIN_RIGHT - 80, 9.5)
                    self.cell(80, 5, self._current_section, align="R")

                # CONFIDENTIAL透かし（対角線）- Y位置を退避して復元
                save_y = self.y
                self.set_font(self._font_name, "B", 52)
                self.set_text_color(*WATERMARK_GRAY)
                with self.rotation(45, self.w / 2, self.h / 2):
                    self.set_xy(self.w / 2 - 60, self.h / 2 - 10)
                    self.cell(120, 20, "CONFIDENTIAL", align="C")
                # rotation内のset_xyでY位置が壊れるので復元
                self.set_xy(MARGIN_LEFT, MARGIN_TOP)

                # テキスト色を戻す
                self.set_text_color(*TEXT_DARK)

            def footer(self):
                """全ページ下部: 罫線 + ページ番号 + CONFIDENTIAL"""
                if self.page == 1:  # 表紙はページ1
                    return

                self.set_y(-FOOTER_HEIGHT)

                # 薄い罫線
                self.set_draw_color(200, 200, 200)
                self.set_line_width(0.3)
                self.line(MARGIN_LEFT, self.h - FOOTER_HEIGHT,
                          self.w - MARGIN_RIGHT, self.h - FOOTER_HEIGHT)

                # ページ番号（中央）
                self.set_font(self._font_name, "", 8)
                self.set_text_color(*TEXT_GRAY)
                self.cell(0, 10, f"- {self.page_no() - 1} -", align="C")

                # CONFIDENTIAL（右下）
                self.set_xy(self.w - MARGIN_RIGHT - 40, self.h - FOOTER_HEIGHT)
                self.set_font(self._font_name, "", 6)
                self.set_text_color(180, 180, 180)
                self.cell(40, 10, "CONFIDENTIAL", align="R")

        # --- PDFインスタンス生成 ---
        pdf = PremiumPDF()
        pdf.set_auto_page_break(auto=True, margin=MARGIN_BOTTOM)
        pdf.set_left_margin(MARGIN_LEFT)
        pdf.set_right_margin(MARGIN_RIGHT)
        pdf.set_top_margin(MARGIN_TOP)

        # 日本語フォント登録
        if font_path:
            pdf.add_font("JP", "", font_path, uni=True)
            pdf.add_font("JP", "B", bold_path, uni=True)
            font_name = "JP"
        else:
            font_name = "Helvetica"
            logger.warning("Japanese font not found, using Helvetica")
        pdf._font_name = font_name

        # --- プレミアム表紙 ---
        pdf._is_cover_page = True
        pdf.add_page()

        # タイトル抽出
        title_match = re.search(r'^#\s+(.+)$', md_text, re.MULTILINE)
        title = title_match.group(1) if title_match else "レポート"
        pdf._report_title = title

        # 上部ネイビーバンド（85mm）
        pdf.set_fill_color(*NAVY)
        pdf.rect(0, 0, pdf.w, 85, "F")

        # コーラルアクセントライン
        pdf.set_fill_color(*CORAL)
        pdf.rect(0, 85, pdf.w, 2.5, "F")

        # タイトル（白文字・ネイビー背景上）
        pdf.set_font(font_name, "B", 24)
        pdf.set_text_color(*WHITE)
        pdf.set_xy(MARGIN_LEFT + 5, 28)
        # タイトルを手動折り返し
        title_lines = self._wrap_text(pdf, title, pdf.w - MARGIN_LEFT - MARGIN_RIGHT - 10)
        for tl in title_lines:
            pdf.set_x(MARGIN_LEFT + 5)
            pdf.cell(0, 14, tl, new_x="LMARGIN", new_y="NEXT")

        # 中央白背景エリア: 会社名・作成者・日付
        pdf.set_text_color(*NAVY)
        pdf.set_y(105)
        pdf.set_font(font_name, "", 14)
        pdf.cell(0, 10, self.header, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        pdf.set_font(font_name, "", 12)
        pdf.set_text_color(*TEXT_DARK)
        pdf.cell(0, 10, f"作成者: {self.author}", align="C",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        pdf.cell(
            0, 10,
            datetime.now(JST).strftime("%Y年%m月%d日"),
            align="C", new_x="LMARGIN", new_y="NEXT",
        )

        # 下部ネイビーバンド（auto_page_breakを一時無効化）
        pdf.set_auto_page_break(auto=False)
        pdf.set_fill_color(*NAVY)
        pdf.rect(0, pdf.h - 27, pdf.w, 27, "F")
        pdf.set_font(font_name, "", 9)
        pdf.set_text_color(180, 180, 200)
        pdf.set_xy(0, pdf.h - 20)
        pdf.cell(pdf.w, 8, "CONFIDENTIAL  |  本レポートは機密文書です",
                 align="C")

        # 斜め透かし "HIROKI"（表紙に薄く）
        pdf.set_font(font_name, "B", 72)
        pdf.set_text_color(235, 235, 240)
        with pdf.rotation(35, pdf.w / 2, pdf.h / 2):
            pdf.set_xy(pdf.w / 2 - 55, pdf.h / 2 + 15)
            pdf.cell(110, 20, "HIROKI", align="C")

        # auto_page_breakを復元
        pdf.set_auto_page_break(auto=True, margin=MARGIN_BOTTOM)
        # テキスト色を戻す
        pdf.set_text_color(*TEXT_DARK)

        # --- 本文解析 ---
        pdf._is_cover_page = False
        page_width = pdf.w - MARGIN_LEFT - MARGIN_RIGHT
        lines = md_text.split("\n")
        in_table = False
        table_rows = []
        h2_count = 0
        in_callout = False
        callout_type = ""
        callout_lines = []
        in_card_block = False
        card_items = []
        found_first_h2 = False  # 最初のH2が来るまではスキップ（表紙情報）
        consecutive_empty = 0    # 連続空行カウンタ

        for line in lines:
            stripped = line.strip()

            # 最初のH2が来るまでは表紙情報なのでスキップ
            if not found_first_h2:
                if stripped.startswith("## ") and not stripped.startswith("### "):
                    found_first_h2 = True
                    # 以下のH2処理に落ちる
                else:
                    continue

            # 空行以外が来たら連続空行カウンタをリセット
            if stripped != "":
                consecutive_empty = 0

            # ---------------------------------------------------
            # コールアウト終了判定（> で始まらない行が来たら終了）
            # ---------------------------------------------------
            if in_callout and not stripped.startswith(">"):
                self._render_callout(pdf, callout_type, callout_lines,
                                     font_name, page_width)
                in_callout = False
                callout_type = ""
                callout_lines = []

            # CARDブロック終了判定
            if in_card_block and not stripped.startswith("> CARD:"):
                self._render_metric_cards(pdf, card_items, font_name,
                                          page_width)
                in_card_block = False
                card_items = []

            # ---------------------------------------------------
            # コールアウト / カードの検出
            # ---------------------------------------------------
            if stripped.startswith(">"):
                inner = stripped.lstrip(">").strip()

                # CARDマーカー: > CARD: ラベル | 値 | 補足
                if inner.startswith("CARD:"):
                    card_data = inner[5:].strip()
                    parts = [p.strip() for p in card_data.split("|")]
                    if len(parts) >= 2:
                        card_items.append(parts)
                        in_card_block = True
                    continue

                # コールアウトマーカー検出
                callout_found = False
                for marker in CALLOUT_STYLES:
                    if inner.startswith(f"{marker}:"):
                        content = inner[len(marker) + 1:].strip()
                        if in_callout and callout_type != marker:
                            # 前のコールアウトを閉じる
                            self._render_callout(pdf, callout_type,
                                                 callout_lines, font_name,
                                                 page_width)
                            callout_lines = []
                        callout_type = marker
                        in_callout = True
                        if content:
                            callout_lines.append(content)
                        callout_found = True
                        break

                if callout_found:
                    continue

                # コールアウト継続行（> で始まるがマーカーなし）
                if in_callout:
                    callout_lines.append(inner)
                    continue

                # 通常の引用行（コールアウトでない > 行）→ 普通のテキストとして
                if in_table:
                    self._render_table(pdf, table_rows, font_name)
                    in_table = False
                    table_rows = []
                pdf.set_font(font_name, "", 10)
                clean = re.sub(r'\*\*(.+?)\*\*', r'\1', inner)
                clean = re.sub(r'\*(.+?)\*', r'\1', clean)
                pdf.set_x(MARGIN_LEFT + 4)
                self._render_multicell_indented(
                    pdf, page_width - 4, LINE_HEIGHT_BODY, clean,
                    MARGIN_LEFT + 4)
                continue

            # ---------------------------------------------------
            # 水平線（---）はスキップ
            # ---------------------------------------------------
            if stripped == "---":
                if in_table:
                    self._render_table(pdf, table_rows, font_name)
                    in_table = False
                    table_rows = []
                pdf.ln(2)
                continue

            # h1（表紙で既に使ったのでスキップ）
            if stripped.startswith("# ") and not stripped.startswith("## "):
                continue

            # ---------------------------------------------------
            # h2 - プレミアム章ヘッダー
            # ---------------------------------------------------
            elif stripped.startswith("## ") and not stripped.startswith("### "):
                if in_table:
                    self._render_table(pdf, table_rows, font_name)
                    in_table = False
                    table_rows = []
                h2_count += 1
                h2_text = stripped.lstrip("# ").strip()
                pdf._current_section = h2_text

                pdf.add_page()

                # --- 全幅ネイビーバンド（30mm高） ---
                band_y = pdf.get_y()
                band_h = 22
                pdf.set_fill_color(*NAVY)
                pdf.rect(0, band_y, pdf.w, band_h, "F")

                # コーラル番号バッジ（円形）
                badge_x = MARGIN_LEFT + 10
                badge_y_center = band_y + band_h / 2
                badge_r = 7
                pdf.set_fill_color(*CORAL)
                pdf.ellipse(badge_x - badge_r, badge_y_center - badge_r,
                            badge_r * 2, badge_r * 2, "F")

                # バッジ内の番号
                pdf.set_font(font_name, "B", 13)
                pdf.set_text_color(*WHITE)
                num_str = str(h2_count)
                num_w = pdf.get_string_width(num_str)
                pdf.set_xy(badge_x - num_w / 2, badge_y_center - 4.5)
                pdf.cell(num_w, 9, num_str, align="C")

                # 章タイトル（白文字）
                pdf.set_font(font_name, "B", 16)
                title_x = badge_x + badge_r + 6
                pdf.set_xy(title_x, badge_y_center - 5.5)
                pdf.cell(0, 11, h2_text)

                # コーラルアクセントライン（バンド下）
                pdf.set_fill_color(*CORAL)
                pdf.rect(0, band_y + band_h, pdf.w, 1.5, "F")

                pdf.set_y(band_y + band_h + 1.5 + SPACING_AFTER_H2)
                pdf.set_text_color(*TEXT_DARK)

                # PDFブックマーク
                pdf.start_section(h2_text, level=0)

            # ---------------------------------------------------
            # h3
            # ---------------------------------------------------
            elif stripped.startswith("### ") and not stripped.startswith("#### "):
                if in_table:
                    self._render_table(pdf, table_rows, font_name)
                    in_table = False
                    table_rows = []
                if self._remaining_space(pdf) < PAGE_BREAK_THRESHOLD_H3:
                    pdf.add_page()
                pdf.ln(4)

                # 左にコーラルバー
                y_before = pdf.get_y()
                pdf.set_fill_color(*CORAL)
                pdf.rect(MARGIN_LEFT, y_before, 3, 9, "F")

                pdf.set_font(font_name, "B", 13)
                pdf.set_text_color(*DARK_BLUE)
                h3_text = stripped.lstrip("# ").strip()
                pdf.set_x(MARGIN_LEFT + 6)
                pdf.cell(0, LINE_HEIGHT_H3, h3_text,
                         new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(*TEXT_DARK)
                pdf.ln(SPACING_AFTER_H3)

                # PDFブックマーク（サブセクション）
                pdf.start_section(h3_text, level=1)

            # ---------------------------------------------------
            # h4
            # ---------------------------------------------------
            elif stripped.startswith("#### "):
                if in_table:
                    self._render_table(pdf, table_rows, font_name)
                    in_table = False
                    table_rows = []
                if self._remaining_space(pdf) < 40:
                    pdf.add_page()
                pdf.ln(2)
                pdf.set_font(font_name, "B", 11)
                pdf.set_text_color(51, 71, 91)
                h4_text = stripped.lstrip("# ").strip()
                pdf.multi_cell(0, LINE_HEIGHT_H4, h4_text)
                pdf.set_text_color(*TEXT_DARK)
                pdf.ln(SPACING_AFTER_H4)

            # ---------------------------------------------------
            # テーブル行
            # ---------------------------------------------------
            elif "|" in stripped and stripped.startswith("|"):
                if "---" in stripped:
                    continue  # セパレータ行はスキップ
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                if not in_table:
                    in_table = True
                    table_rows = []
                table_rows.append(cells)

            # ---------------------------------------------------
            # 空行（連続空行を抑制）
            # ---------------------------------------------------
            elif stripped == "":
                if in_table:
                    self._render_table(pdf, table_rows, font_name)
                    in_table = False
                    table_rows = []
                consecutive_empty += 1
                if consecutive_empty <= MAX_CONSECUTIVE_EMPTY:
                    pdf.ln(SPACING_EMPTY_LINE)
                continue

            # ---------------------------------------------------
            # 画像埋め込み
            # ---------------------------------------------------
            elif re.match(r'!\[.*?\]\(.+?\)', stripped):
                if in_table:
                    self._render_table(pdf, table_rows, font_name)
                    in_table = False
                    table_rows = []
                img_match = re.match(r'!\[.*?\]\((.+?)\)', stripped)
                if img_match:
                    img_path = img_match.group(1)
                    self._embed_image(pdf, img_path)

            # ---------------------------------------------------
            # 箇条書き（- / * で始まる行）
            # ---------------------------------------------------
            elif stripped.startswith("- ") or stripped.startswith("* "):
                if in_table:
                    self._render_table(pdf, table_rows, font_name)
                    in_table = False
                    table_rows = []
                pdf.set_font(font_name, "", 10)
                clean = stripped[2:]
                clean = re.sub(r'\*\*(.+?)\*\*', r'\1', clean)
                clean = re.sub(r'\*(.+?)\*', r'\1', clean)
                bullet_text = f"  \u2022  {clean}"
                indent = 6
                cell_w = page_width - indent
                pdf.set_x(MARGIN_LEFT + indent)
                self._render_multicell_indented(
                    pdf, cell_w, LINE_HEIGHT_BODY, bullet_text,
                    MARGIN_LEFT + indent)
                pdf.ln(1)

            # ---------------------------------------------------
            # 番号付きリスト
            # ---------------------------------------------------
            elif re.match(r'^\d+\.\s', stripped):
                if in_table:
                    self._render_table(pdf, table_rows, font_name)
                    in_table = False
                    table_rows = []
                pdf.set_font(font_name, "", 10)
                clean = re.sub(r'\*\*(.+?)\*\*', r'\1', stripped)
                clean = re.sub(r'\*(.+?)\*', r'\1', clean)
                indent = 6
                cell_w = page_width - indent
                pdf.set_x(MARGIN_LEFT + indent)
                self._render_multicell_indented(
                    pdf, cell_w, LINE_HEIGHT_BODY, clean,
                    MARGIN_LEFT + indent)
                pdf.ln(1)

            # ---------------------------------------------------
            # 通常テキスト
            # ---------------------------------------------------
            else:
                if in_table:
                    self._render_table(pdf, table_rows, font_name)
                    in_table = False
                    table_rows = []
                # 太字行かどうか判定
                bold_line = re.match(r'^\*\*(.+)\*\*$', stripped)
                if bold_line:
                    pdf.set_font(font_name, "B", 10)
                    clean = bold_line.group(1)
                else:
                    pdf.set_font(font_name, "", 10)
                    clean = re.sub(r'\*\*(.+?)\*\*', r'\1', stripped)
                    clean = re.sub(r'\*(.+?)\*', r'\1', clean)
                pdf.set_x(MARGIN_LEFT)
                self._render_multicell_indented(
                    pdf, page_width, LINE_HEIGHT_BODY, clean,
                    MARGIN_LEFT)
                if bold_line:
                    pdf.set_font(font_name, "", 10)

        # --- 残りバッファ出力 ---
        if in_callout:
            self._render_callout(pdf, callout_type, callout_lines,
                                 font_name, page_width)
        if in_card_block:
            self._render_metric_cards(pdf, card_items, font_name, page_width)
        if in_table:
            self._render_table(pdf, table_rows, font_name)

        # --- Disclaimer ページ ---
        pdf.add_page()
        pdf.ln(10)
        # 罫線
        pdf.set_draw_color(*NAVY)
        pdf.set_line_width(0.5)
        pdf.line(MARGIN_LEFT, pdf.get_y(), pdf.w - MARGIN_RIGHT, pdf.get_y())
        pdf.ln(6)

        pdf.set_font(font_name, "B", 13)
        pdf.set_text_color(*NAVY)
        pdf.cell(0, 10, "Disclaimer / 免責事項",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        pdf.set_font(font_name, "", 9)
        pdf.set_text_color(*TEXT_GRAY)
        pdf.multi_cell(0, 6, (
            "本レポートはお客様限りの機密文書です。"
            "記載されたデータは作成時点のものであり、"
            "最新の状況とは異なる場合があります。"
            "将来の地価・賃料予測はAI分析と経験に基づく推定値であり、"
            "確実性を保証するものではありません。"
            "投資判断は自己責任でお願いいたします。"
            "本レポートの内容の第三者への共有はご遠慮ください。"
        ))

        pdf.ln(10)
        pdf.set_draw_color(*NAVY)
        pdf.line(MARGIN_LEFT, pdf.get_y(), pdf.w - MARGIN_RIGHT, pdf.get_y())
        pdf.ln(8)
        pdf.set_font(font_name, "", 10)
        pdf.set_text_color(*NAVY)
        pdf.cell(0, 8, self.header, align="C",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(font_name, "", 9)
        pdf.set_text_color(*TEXT_GRAY)
        pdf.cell(0, 8, f"\u00a9 {datetime.now(JST).strftime('%Y')} All Rights Reserved.",
                 align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.output(str(output))
        logger.info(
            f"PDF generated: {output} ({output.stat().st_size / 1024:.1f} KB)")
        return str(output)

    # =====================================================
    # コールアウトボックス描画
    # =====================================================
    def _render_callout(self, pdf, callout_type: str,
                        content_lines: list, font_name: str,
                        page_width: float):
        """コールアウトボックスを描画（KEY INSIGHT / RISK WARNING 等）"""
        if not content_lines or callout_type not in CALLOUT_STYLES:
            return

        bg_color, bar_color, label = CALLOUT_STYLES[callout_type]
        content = " ".join(content_lines)
        content = re.sub(r'\*\*(.+?)\*\*', r'\1', content)
        content = re.sub(r'\*(.+?)\*', r'\1', content)

        # コンテンツの行数を事前計算
        pdf.set_font(font_name, "", 9)
        inner_width = page_width - 12  # 左バー4mm + 左パディング4mm + 右パディング4mm
        wrapped = self._wrap_text(pdf, content, inner_width)
        box_h = max(18, 10 + len(wrapped) * 6 + 4)  # ラベル行 + コンテンツ + パディング

        # ページ下端チェック
        if self._remaining_space(pdf) < box_h + 5:
            pdf.add_page()

        pdf.ln(3)
        y_start = pdf.get_y()

        # 背景色
        pdf.set_fill_color(*bg_color)
        pdf.rect(MARGIN_LEFT, y_start, page_width, box_h, "F")

        # 左カラーバー（4mm幅）
        pdf.set_fill_color(*bar_color)
        pdf.rect(MARGIN_LEFT, y_start, 4, box_h, "F")

        # ラベル行
        pdf.set_font(font_name, "B", 8)
        pdf.set_text_color(*bar_color)
        pdf.set_xy(MARGIN_LEFT + 7, y_start + 3)
        # ラベルアイコン
        icons = {
            "KEY INSIGHT": "\u25c6",   # ◆
            "RISK WARNING": "\u26a0",  # ⚠
            "ACTION": "\u25b6",        # ▶
            "METRIC": "\u25cf",        # ●
        }
        icon = icons.get(callout_type, "\u25cf")
        pdf.cell(0, 5, f"{icon}  {label}")

        # コンテンツ
        pdf.set_font(font_name, "", 9)
        pdf.set_text_color(*TEXT_DARK)
        text_y = y_start + 10
        for wl in wrapped:
            pdf.set_xy(MARGIN_LEFT + 7, text_y)
            pdf.cell(inner_width, 6, wl)
            text_y += 6

        pdf.set_y(y_start + box_h + 3)
        pdf.set_text_color(*TEXT_DARK)

    # =====================================================
    # メトリックカード描画
    # =====================================================
    def _render_metric_cards(self, pdf, card_items: list,
                             font_name: str, page_width: float):
        """メトリックカードを横並びで描画（コーラル上線アクセント）"""
        if not card_items:
            return

        num_cards = min(len(card_items), 3)
        card_gap = 4
        card_w = (page_width - card_gap * (num_cards - 1)) / num_cards
        card_h = 28

        if self._remaining_space(pdf) < card_h + 8:
            pdf.add_page()

        pdf.ln(4)
        y_start = pdf.get_y()

        for i in range(num_cards):
            parts = card_items[i]
            label = parts[0] if len(parts) > 0 else ""
            value = parts[1] if len(parts) > 1 else ""
            note = parts[2] if len(parts) > 2 else ""

            x = MARGIN_LEFT + i * (card_w + card_gap)

            # カード背景（薄いグレー）
            pdf.set_fill_color(248, 249, 252)
            pdf.rect(x, y_start, card_w, card_h, "F")

            # コーラル上線
            pdf.set_fill_color(*CORAL)
            pdf.rect(x, y_start, card_w, 2, "F")

            # ラベル
            pdf.set_font(font_name, "", 7)
            pdf.set_text_color(*TEXT_GRAY)
            pdf.set_xy(x + 3, y_start + 4)
            pdf.cell(card_w - 6, 4, label, align="C")

            # 値（大きく）
            pdf.set_font(font_name, "B", 14)
            pdf.set_text_color(*NAVY)
            pdf.set_xy(x + 3, y_start + 10)
            pdf.cell(card_w - 6, 8, value, align="C")

            # 補足
            if note:
                pdf.set_font(font_name, "", 7)
                pdf.set_text_color(*TEXT_GRAY)
                pdf.set_xy(x + 3, y_start + 20)
                pdf.cell(card_w - 6, 4, note, align="C")

        pdf.set_y(y_start + card_h + 4)
        pdf.set_text_color(*TEXT_DARK)

    # =====================================================
    # テキスト描画ヘルパー
    # =====================================================
    def _render_multicell_indented(self, pdf, width: float,
                                   line_h: float, text: str,
                                   x_indent: float):
        """テキストを指定インデント位置で折り返しながら描画する。"""
        if not text:
            return
        lines_to_draw = self._wrap_text(pdf, text, width - 2)
        for line_text in lines_to_draw:
            if self._remaining_space(pdf) < line_h + 3:
                pdf.add_page()
            pdf.set_x(x_indent)
            pdf.cell(width, line_h, line_text,
                     new_x="LMARGIN", new_y="NEXT")

    def _wrap_text(self, pdf, text: str, max_width: float) -> list:
        """テキストを指定幅に収まるように行分割する（日本語混在対応）。"""
        if not text:
            return [""]
        lines = []
        current_line = ""
        current_width = 0.0
        for char in text:
            try:
                char_w = pdf.get_string_width(char)
            except Exception:
                char_w = 3.0
            if current_width + char_w > max_width and current_line:
                lines.append(current_line)
                current_line = char
                current_width = char_w
            else:
                current_line += char
                current_width += char_w
        if current_line:
            lines.append(current_line)
        return lines if lines else [""]

    # =====================================================
    # 画像埋め込み
    # =====================================================
    def _embed_image(self, pdf, img_path: str):
        """画像をPDFに埋め込む（グラフ・チャート用）"""
        if not os.path.exists(img_path):
            logger.warning(f"Image not found: {img_path}")
            return
        try:
            page_width = pdf.w - MARGIN_LEFT - MARGIN_RIGHT
            img_width = page_width * 0.80  # 80%幅でコンパクトに
            x_offset = MARGIN_LEFT + (page_width - img_width) / 2
            # 残りスペースが少なければ改ページ（100mmを閾値に）
            if self._remaining_space(pdf) < 100:
                pdf.add_page()
            pdf.image(img_path, x=x_offset, w=img_width)
            pdf.ln(SPACING_AFTER_IMAGE)
        except Exception as e:
            logger.error(f"Failed to embed image {img_path}: {e}")

    # =====================================================
    # テーブル描画（モダンデザイン: 縦罫線なし・数値右寄せ）
    # =====================================================
    def _calc_col_widths(self, pdf, rows: list, font_name: str,
                         font_size: int, page_width: float,
                         num_cols: int) -> list:
        """各列の最適幅を内容ベースで計算する"""
        pdf.set_font(font_name, "", font_size)
        max_widths = [0.0] * num_cols
        for row in rows:
            for j in range(num_cols):
                text = row[j] if j < len(row) else ""
                try:
                    w = pdf.get_string_width(text) + 3
                except Exception:
                    w = len(text) * font_size * 0.3 + 3
                if w > max_widths[j]:
                    max_widths[j] = w

        total = sum(max_widths)
        if total <= 0:
            return [page_width / num_cols] * num_cols

        min_col = 12
        col_widths = []
        for w in max_widths:
            cw = max(min_col, (w / total) * page_width)
            col_widths.append(cw)

        scale = page_width / sum(col_widths)
        col_widths = [cw * scale for cw in col_widths]
        return col_widths

    def _calc_row_height(self, pdf, row: list, col_widths: list,
                         font_name: str, font_size: int,
                         base_height: float) -> float:
        """行のセル内折り返しを考慮した必要高さを計算"""
        max_lines = 1
        for j, cw in enumerate(col_widths):
            text = row[j] if j < len(row) else ""
            if not text:
                continue
            try:
                text_w = pdf.get_string_width(text) + 2
            except Exception:
                text_w = len(text) * font_size * 0.3 + 2
            usable_w = cw - 2
            if usable_w > 0:
                lines = max(1, int(text_w / usable_w) + 1)
            else:
                lines = 1
            if lines > max_lines:
                max_lines = lines
        max_lines = min(max_lines, 3)
        return base_height * max_lines

    def _is_numeric_cell(self, text: str) -> bool:
        """セルが数値データかどうか判定（右寄せ用）"""
        if not text:
            return False
        # 数字・%・円・万・pt・倍・m2 等を含むセル
        return bool(re.search(
            r'[\d,\.]+\s*(%|円|万|千|億|pt|倍|m[2²]|㎡|件|棟|戸|人|世帯|年|週|室|回|kg|km)',
            text)) or bool(re.match(r'^[\d,\.\-\+]+%?$', text.strip()))

    def _draw_table_row(self, pdf, row: list, col_widths: list,
                        row_h: float, font_name: str, font_size: int,
                        is_header: bool, is_even: bool):
        """1行分のテーブルセルを描画（モダンデザイン: 縦罫線なし）"""
        num_cols = len(col_widths)
        x_start = pdf.get_x()
        y_start = pdf.get_y()

        if is_header:
            pdf.set_font(font_name, "B", font_size)
            pdf.set_fill_color(*NAVY)
            pdf.set_text_color(*WHITE)
        else:
            pdf.set_font(font_name, "", font_size)
            pdf.set_text_color(*TEXT_DARK)
            if is_even:
                pdf.set_fill_color(245, 247, 250)
            else:
                pdf.set_fill_color(*WHITE)

        # 背景のみ描画（縦罫線なし）
        total_width = sum(col_widths)
        pdf.rect(x_start, y_start, total_width, row_h, "F")

        # 横罫線（ヘッダー下は太め、データ行は薄い）
        if is_header:
            pdf.set_draw_color(*CORAL)
            pdf.set_line_width(0.6)
            pdf.line(x_start, y_start + row_h,
                     x_start + total_width, y_start + row_h)
        else:
            pdf.set_draw_color(220, 225, 230)
            pdf.set_line_width(0.2)
            pdf.line(x_start, y_start + row_h,
                     x_start + total_width, y_start + row_h)

        # テキスト描画
        x = x_start
        for j in range(num_cols):
            cell_text = row[j] if j < len(row) else ""
            cell_text = re.sub(r'\*\*(.+?)\*\*', r'\1', cell_text)
            cell_text = re.sub(r'\*(.+?)\*', r'\1', cell_text)

            usable_w = col_widths[j] - 2
            wrapped = self._wrap_text(pdf, cell_text, usable_w)
            max_display_lines = max(1, int(row_h / 5))
            wrapped = wrapped[:max_display_lines]

            # 数値セルの右寄せ自動判定（ヘッダー以外）
            align = "L"
            if not is_header and self._is_numeric_cell(cell_text):
                align = "R"

            line_h = row_h / max(1, len(wrapped))
            for li, line_text in enumerate(wrapped):
                pdf.set_xy(x + 1, y_start + 0.5 + li * line_h)
                pdf.cell(usable_w, line_h, line_text,
                         border=0, align=align)
            x += col_widths[j]

        pdf.set_xy(x_start, y_start + row_h)

    def _render_table(self, pdf, rows: list, font_name: str):
        """テーブルをPDFに描画（モダンデザイン版）"""
        if not rows:
            return

        num_cols = max(len(r) for r in rows)
        if num_cols == 0:
            return

        page_width = pdf.w - MARGIN_LEFT - MARGIN_RIGHT

        if page_width / num_cols < 12:
            pdf.set_font(font_name, "", 7)
            for row in rows:
                pdf.multi_cell(0, 5, " | ".join(row))
            pdf.ln(SPACING_AFTER_TABLE)
            return

        if num_cols <= 3:
            font_size = 9
        elif num_cols <= 5:
            font_size = 8
        elif num_cols <= 7:
            font_size = 7
        else:
            font_size = 6
        base_row_h = 6 if font_size <= 7 else 7

        col_widths = self._calc_col_widths(
            pdf, rows, font_name, font_size, page_width, num_cols)

        est_height = len(rows) * base_row_h + 10
        if self._remaining_space(pdf) < min(est_height, 45):
            pdf.add_page()

        def draw_header():
            h = self._calc_row_height(
                pdf, rows[0], col_widths, font_name, font_size, base_row_h)
            self._draw_table_row(
                pdf, rows[0], col_widths, h, font_name, font_size,
                is_header=True, is_even=False)

        for i, row in enumerate(rows):
            row_h = self._calc_row_height(
                pdf, row, col_widths, font_name, font_size, base_row_h)
            if self._remaining_space(pdf) < row_h + 3:
                pdf.add_page()
                draw_header()

            is_header = (i == 0)
            is_even = (i % 2 == 0)
            self._draw_table_row(
                pdf, row, col_widths, row_h, font_name, font_size,
                is_header=is_header, is_even=is_even)

        pdf.set_text_color(*TEXT_DARK)
        pdf.set_x(MARGIN_LEFT)
        pdf.ln(SPACING_AFTER_TABLE)

    # =====================================================
    # フォント検索
    # =====================================================
    def _find_japanese_font(self, bold=False) -> str:
        """Windows標準の日本語フォントパスを返す"""
        font_dir = "C:/Windows/Fonts"
        candidates = [
            ("YuGothM.ttc", "YuGothB.ttc"),
            ("meiryo.ttc", "meiryob.ttc"),
            ("msgothic.ttc", "msgothic.ttc"),
        ]
        for regular, bold_font in candidates:
            target = bold_font if bold else regular
            path = os.path.join(font_dir, target)
            if os.path.exists(path):
                return path
        return ""

    def generate_from_template(
        self, template_name: str, data: dict, output_path: str
    ) -> str:
        """テンプレート → Markdown → PDF の一括処理"""
        md_text = self.render_template(template_name, data)
        return self.generate_pdf(md_text, output_path)
