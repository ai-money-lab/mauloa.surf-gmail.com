#!/usr/bin/env python3
"""納品書兼御請求書 PDF生成スクリプト - 安江フォーマット準拠"""

from fpdf import FPDF
import os


class InvoicePDF(FPDF):
    def __init__(self):
        super().__init__(orientation='P', unit='mm', format='A4')
        font_path = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'
        self.add_font('IPAGothic', '', font_path)
        font_path_p = '/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf'
        self.add_font('IPAPGothic', '', font_path_p)


def fmt(amount):
    """金額フォーマット"""
    return f"¥{amount:,}"


def generate_invoice(output_path, items, issue_date="2026年3月3日",
                     case_name="デンキチさま2026年2月施工分"):
    """
    items: list of (description, unit_price) tuples
    """
    pdf = InvoicePDF()
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    # ===== タイトル =====
    pdf.set_font('IPAPGothic', '', 20)
    pdf.cell(0, 14, "納品書 兼 御請求書", align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # ===== 左: 宛先 / 右: 案・発 =====
    y_top = pdf.get_y()

    # 宛先
    pdf.set_font('IPAPGothic', '', 12)
    pdf.cell(110, 7, "株式会社ROCKEDGEPropertyManagement", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # 案件名
    pdf.set_font('IPAGothic', '', 10)
    pdf.cell(20, 6, "案件名", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('IPAPGothic', '', 11)
    pdf.cell(110, 7, case_name, new_x="LMARGIN", new_y="NEXT")

    y_after_left = pdf.get_y()

    # 右側: 案番号・発行日
    pdf.set_y(y_top)
    pdf.set_font('IPAGothic', '', 10)
    pdf.set_x(130)
    pdf.cell(20, 6, "案", new_x="RIGHT", new_y="TOP")
    pdf.cell(40, 6, "0", align='R', new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(130)
    pdf.cell(20, 6, "発", new_x="RIGHT", new_y="TOP")
    pdf.cell(40, 6, issue_date, align='R', new_x="LMARGIN", new_y="NEXT")

    # 右側: 発行元情報
    pdf.ln(2)
    pdf.set_x(130)
    pdf.set_font('IPAGothic', '', 9)
    from_lines = [
        "La Chaleur（ラ・シャルール）",
        "合同会社安江",
        "168-0061",
        "東京都杉並区大宮1-11-13",
        "TEL: 090-8007-8981",
        "E-Mail:",
    ]
    for line in from_lines:
        pdf.set_x(130)
        pdf.cell(65, 5, line, new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(130)
    pdf.set_font('IPAPGothic', '', 10)
    pdf.cell(65, 6, "担 安江啓太", new_x="LMARGIN", new_y="NEXT")

    y_after_right = pdf.get_y()
    pdf.set_y(max(y_after_left, y_after_right) + 4)

    # ===== 御請求金額ボックス =====
    subtotal = sum(price for _, price in items)
    tax = round(subtotal * 0.10)
    total = subtotal + tax

    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.4)

    box_y = pdf.get_y()
    # 左ラベル
    pdf.set_font('IPAPGothic', '', 12)
    pdf.cell(50, 12, "御請求金額", border=1, align='C', new_x="RIGHT", new_y="TOP")
    # 金額
    pdf.set_font('IPAPGothic', '', 16)
    pdf.cell(60, 12, fmt(total), border=1, align='C', new_x="LMARGIN", new_y="NEXT")

    # 右側: 番号
    pdf.set_y(box_y)
    pdf.set_x(140)
    pdf.set_font('IPAGothic', '', 9)
    pdf.cell(55, 6, "番号:T7011303004853", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(box_y + 14)

    # ===== 明細テーブル =====
    col_no = 10
    col_item = 88
    col_qty = 12
    col_unit = 12
    col_price = 30
    col_amount = 38
    row_h = 6.5

    pdf.ln(3)

    # ヘッダー
    pdf.set_font('IPAPGothic', '', 9)
    pdf.cell(col_no, row_h, "No.", border=1, align='C', new_x="RIGHT", new_y="TOP")
    pdf.cell(col_item, row_h, "項目", border=1, align='C', new_x="RIGHT", new_y="TOP")
    pdf.cell(col_qty, row_h, "数量", border=1, align='C', new_x="RIGHT", new_y="TOP")
    pdf.cell(col_unit, row_h, "単位", border=1, align='C', new_x="RIGHT", new_y="TOP")
    pdf.cell(col_price, row_h, "単価", border=1, align='C', new_x="RIGHT", new_y="TOP")
    pdf.cell(col_amount, row_h, "金額", border=1, align='C', new_x="RIGHT", new_y="TOP")
    pdf.ln()

    # 明細行
    pdf.set_font('IPAGothic', '', 8)
    for i, (desc, price) in enumerate(items, 1):
        pdf.cell(col_no, row_h, str(i), border=1, align='R', new_x="RIGHT", new_y="TOP")
        pdf.cell(col_item, row_h, f" {desc}", border=1, align='L', new_x="RIGHT", new_y="TOP")
        pdf.cell(col_qty, row_h, "1", border=1, align='R', new_x="RIGHT", new_y="TOP")
        pdf.cell(col_unit, row_h, "式", border=1, align='C', new_x="RIGHT", new_y="TOP")
        pdf.cell(col_price, row_h, fmt(price), border=1, align='R', new_x="RIGHT", new_y="TOP")
        pdf.cell(col_amount, row_h, fmt(price), border=1, align='R', new_x="RIGHT", new_y="TOP")
        pdf.ln()

    # 空行（明細が少ない場合に埋める、最大行まで）
    total_rows = max(len(items), 24)
    for _ in range(total_rows - len(items)):
        pdf.cell(col_no, row_h, "", border=1, new_x="RIGHT", new_y="TOP")
        pdf.cell(col_item, row_h, "", border=1, new_x="RIGHT", new_y="TOP")
        pdf.cell(col_qty, row_h, "", border=1, new_x="RIGHT", new_y="TOP")
        pdf.cell(col_unit, row_h, "", border=1, new_x="RIGHT", new_y="TOP")
        pdf.cell(col_price, row_h, "", border=1, new_x="RIGHT", new_y="TOP")
        pdf.cell(col_amount, row_h, "", border=1, new_x="RIGHT", new_y="TOP")
        pdf.ln()

    # ===== 小計・消費税・合計（明細テーブル右下に配置）=====
    # 入金期日・振込先（左側）
    summary_y = pdf.get_y()

    pdf.set_font('IPAGothic', '', 9)
    pdf.cell(col_no + col_item + col_qty, row_h, "", new_x="RIGHT", new_y="TOP")
    pdf.set_font('IPAPGothic', '', 9)
    pdf.cell(col_unit, row_h, "小計", border=1, align='C', new_x="RIGHT", new_y="TOP")
    pdf.set_font('IPAGothic', '', 9)
    pdf.cell(col_price + col_amount, row_h, fmt(subtotal), border=1, align='R', new_x="RIGHT", new_y="TOP")
    pdf.ln()

    pdf.cell(col_no + col_item + col_qty, row_h, "", new_x="RIGHT", new_y="TOP")
    pdf.set_font('IPAPGothic', '', 8)
    pdf.cell(col_unit, row_h, "", border=1, align='C', new_x="RIGHT", new_y="TOP")
    pdf.set_font('IPAGothic', '', 9)
    pdf.cell(col_price, row_h, "消費税(10%)", border=1, align='C', new_x="RIGHT", new_y="TOP")
    pdf.cell(col_amount, row_h, fmt(tax), border=1, align='R', new_x="RIGHT", new_y="TOP")
    pdf.ln()

    pdf.cell(col_no + col_item + col_qty, row_h, "", new_x="RIGHT", new_y="TOP")
    pdf.set_font('IPAPGothic', '', 9)
    pdf.cell(col_unit, row_h, "", border=1, align='C', new_x="RIGHT", new_y="TOP")
    pdf.set_font('IPAGothic', '', 9)
    pdf.cell(col_price, row_h, "合計", border=1, align='C', new_x="RIGHT", new_y="TOP")
    pdf.set_font('IPAPGothic', '', 10)
    pdf.cell(col_amount, row_h, fmt(total), border=1, align='R', new_x="RIGHT", new_y="TOP")
    pdf.ln()

    # ===== 入金期日・振込先（左下）=====
    pdf.set_y(summary_y)
    pdf.set_font('IPAGothic', '', 9)
    pdf.cell(20, row_h, "入金期日", border=1, align='C', new_x="RIGHT", new_y="TOP")
    pdf.cell(70, row_h, " 末締め翌月末支払い", border=1, align='L', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(20, row_h, "振込先", border=1, align='C', new_x="RIGHT", new_y="TOP")
    pdf.cell(70, row_h, " GMOあおぞらネット銀行", border=1, align='L', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(20, row_h, "", border=1, new_x="RIGHT", new_y="TOP")
    pdf.cell(70, row_h, " 法人営業部支店 普通 1978099", border=1, align='L', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(20, row_h, "", border=1, new_x="RIGHT", new_y="TOP")
    pdf.cell(70, row_h, " 合同会社安江", border=1, align='L', new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)

    # ===== 備考 =====
    pdf.set_font('IPAPGothic', '', 10)
    pdf.cell(20, 7, "備考", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(180, 180, 180)
    pdf.rect(10, pdf.get_y(), 190, 20)

    pdf.output(output_path)
    return output_path


if __name__ == "__main__":
    # デンキチ工事 2026年2月分 明細
    # スプレッドシートL列の合計: 920,546円（税込）
    # 税抜小計から個別明細が不明のため一括計上
    items_feb = [
        ("デンキチさま2026年2月施工分 一式", 836860),
    ]

    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "invoices")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "納品書兼御請求書_ROCKEDGE宛_安江_デンキチ工事2026年2月分.pdf")
    result = generate_invoice(out_path, items=items_feb)
    print(f"PDF生成完了: {result}")
