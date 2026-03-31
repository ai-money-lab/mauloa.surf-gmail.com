#!/usr/bin/env python3
"""納品書兼御請求書 PDF生成スクリプト"""

from fpdf import FPDF
import os
from datetime import date


class InvoicePDF(FPDF):
    def __init__(self):
        super().__init__(orientation='P', unit='mm', format='A4')
        # IPA Gothic font
        font_path = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'
        self.add_font('IPAGothic', '', font_path, uni=True)
        font_path_p = '/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf'
        self.add_font('IPAPGothic', '', font_path_p, uni=True)


def format_yen(amount):
    """金額を日本円フォーマットに"""
    return f"¥{amount:,.0f}"


def generate_invoice(
    output_path: str,
    to_company: str = "株式会社ROCKEDGE",
    to_person: str = "御中",
    from_company: str = "安江工業株式会社",
    title: str = "納品書兼御請求書",
    subject: str = "デンキチ工事 2026年2月分",
    total_amount: float = 920546,
    issue_date: str = "2026年3月13日",
    due_date: str = "2026年3月末日",
):
    pdf = InvoicePDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # --- タイトル ---
    pdf.set_font('IPAPGothic', '', 22)
    pdf.cell(0, 15, title, align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # --- 発行日 ---
    pdf.set_font('IPAGothic', '', 10)
    pdf.cell(0, 6, f"発行日: {issue_date}", align='R', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # --- 宛先（左側）と発行元（右側）---
    y_start = pdf.get_y()

    # 宛先
    pdf.set_font('IPAPGothic', '', 14)
    pdf.cell(90, 10, f"{to_company}　{to_person}", new_x="LMARGIN", new_y="NEXT")

    # 下線
    pdf.line(10, pdf.get_y(), 100, pdf.get_y())
    pdf.ln(8)

    y_after_to = pdf.get_y()

    # 発行元（右寄せ）
    pdf.set_y(y_start)
    pdf.set_font('IPAGothic', '', 10)
    x_right = 120
    pdf.set_x(x_right)
    pdf.cell(0, 6, from_company, new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(x_right)
    pdf.cell(0, 6, "", new_x="LMARGIN", new_y="NEXT")  # 住所があれば入れる

    pdf.set_y(max(y_after_to, pdf.get_y()) + 5)

    # --- 件名 ---
    pdf.set_font('IPAGothic', '', 11)
    pdf.cell(25, 8, "件名:", new_x="RIGHT", new_y="TOP")
    pdf.set_font('IPAPGothic', '', 12)
    pdf.cell(0, 8, subject, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # --- 合計金額ボックス ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.5)

    box_x = 10
    box_w = 190
    box_h = 18

    pdf.rect(box_x, pdf.get_y(), box_w, box_h)
    pdf.set_fill_color(70, 70, 70)
    pdf.rect(box_x, pdf.get_y(), 50, box_h, 'F')

    y_box = pdf.get_y()
    pdf.set_xy(box_x, y_box + 3)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('IPAPGothic', '', 13)
    pdf.cell(50, 12, "ご請求金額", align='C')

    # 税込合計
    tax_rate = 0.10
    tax_amount = int(total_amount * tax_rate / (1 + tax_rate))  # 内税計算
    subtotal = total_amount - tax_amount

    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(box_x + 55, y_box + 1)
    pdf.set_font('IPAPGothic', '', 20)
    pdf.cell(130, 16, format_yen(total_amount) + "（税込）", align='C')

    pdf.set_y(y_box + box_h + 8)

    # --- お支払期限 ---
    pdf.set_font('IPAGothic', '', 10)
    pdf.cell(30, 7, "お支払期限:", new_x="RIGHT", new_y="TOP")
    pdf.cell(0, 7, due_date, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # --- 明細テーブル ---
    col_widths = [90, 20, 30, 50]  # 品名, 数量, 単価, 金額
    headers = ["品名", "数量", "単価", "金額"]

    # ヘッダー
    pdf.set_fill_color(60, 60, 60)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('IPAPGothic', '', 10)
    for i, (header, w) in enumerate(zip(headers, col_widths)):
        pdf.cell(w, 9, header, border=1, fill=True, align='C',
                 new_x="RIGHT", new_y="TOP")
    pdf.ln()

    # 明細行
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('IPAGothic', '', 10)

    items = [
        (subject, "1", format_yen(subtotal), format_yen(subtotal)),
    ]

    for item_name, qty, unit_price, amount in items:
        pdf.cell(col_widths[0], 9, f"  {item_name}", border=1, align='L',
                 new_x="RIGHT", new_y="TOP")
        pdf.cell(col_widths[1], 9, qty, border=1, align='C',
                 new_x="RIGHT", new_y="TOP")
        pdf.cell(col_widths[2], 9, unit_price, border=1, align='R',
                 new_x="RIGHT", new_y="TOP")
        pdf.cell(col_widths[3], 9, amount, border=1, align='R',
                 new_x="RIGHT", new_y="TOP")
        pdf.ln()

    # 空行（5行追加）
    for _ in range(5):
        for w in col_widths:
            pdf.cell(w, 9, "", border=1, new_x="RIGHT", new_y="TOP")
        pdf.ln()

    pdf.ln(3)

    # --- 小計・消費税・合計 ---
    summary_x = col_widths[0] + col_widths[1]  # 品名+数量の幅
    label_w = col_widths[2]
    val_w = col_widths[3]

    summaries = [
        ("小計", format_yen(subtotal)),
        ("消費税(10%)", format_yen(tax_amount)),
        ("合計（税込）", format_yen(total_amount)),
    ]

    for label, val in summaries:
        pdf.set_x(10 + summary_x)
        if label == "合計（税込）":
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font('IPAPGothic', '', 11)
            pdf.cell(label_w, 9, label, border=1, align='C', fill=True,
                     new_x="RIGHT", new_y="TOP")
            pdf.set_font('IPAPGothic', '', 12)
            pdf.cell(val_w, 9, val, border=1, align='R', fill=True,
                     new_x="RIGHT", new_y="TOP")
        else:
            pdf.set_font('IPAGothic', '', 10)
            pdf.cell(label_w, 9, label, border=1, align='C',
                     new_x="RIGHT", new_y="TOP")
            pdf.cell(val_w, 9, val, border=1, align='R',
                     new_x="RIGHT", new_y="TOP")
        pdf.ln()

    pdf.ln(15)

    # --- 備考 ---
    pdf.set_font('IPAPGothic', '', 11)
    pdf.cell(0, 8, "備考", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(180, 180, 180)
    pdf.rect(10, pdf.get_y(), 190, 30)
    pdf.set_font('IPAGothic', '', 9)
    pdf.set_xy(12, pdf.get_y() + 3)
    pdf.multi_cell(186, 5, "・デンキチ様案件 2026年2月施工分\n・お振込手数料はご負担をお願いいたします。")

    # --- 出力 ---
    pdf.output(output_path)
    return output_path


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "invoices")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "納品書兼御請求書_ROCKEDGE宛_安江_デンキチ工事2026年2月分.pdf")
    result = generate_invoice(out_path)
    print(f"PDF生成完了: {result}")
