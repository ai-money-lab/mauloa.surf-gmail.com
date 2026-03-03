"""
岩崎ビル402号室 間取り図生成スクリプト
添付された間取り図の寸法データからSVG→PNGを生成し、
nano-banana のリファレンス画像として使えるようにする
"""
import subprocess
import os

# 寸法データ（添付間取り図から読み取り、単位: mm）
# 外形
TOTAL_W = 8636  # 東西方向（横幅）
TOTAL_H = 6370  # 南北方向（奥行き）  ※概算: 面積35.83m²から逆算

# バスルーム（左上）
BATH_W = 2275  # 幅
BATH_H = 2730  # 奥行き

# 玄関・廊下（下部中央〜左）
HALL_W = 1365  # 廊下幅
ENTRANCE_W = 910  # 玄関幅

# キッチン（廊下左壁沿い）
KITCHEN_W = 1820  # キッチンカウンター長さ

# バルコニー（東側、右壁全面）
BALCONY_DEPTH = 910

# スケール: 1mm = 0.1px → 全体 864x637px に収まる
SCALE = 0.08
MARGIN = 40

def mm(v):
    return v * SCALE

def generate_svg():
    w = mm(TOTAL_W) + MARGIN * 2
    h = mm(TOTAL_H) + MARGIN * 2
    ox, oy = MARGIN, MARGIN  # 原点オフセット

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}">
  <style>
    .wall {{ fill: none; stroke: #333; stroke-width: 3; }}
    .thin-wall {{ fill: none; stroke: #333; stroke-width: 1.5; }}
    .room {{ fill: #FFF8F0; stroke: none; }}
    .bath {{ fill: #E8F4F8; stroke: none; }}
    .kitchen {{ fill: #FFF0E0; stroke: none; }}
    .balcony {{ fill: #E8F8E8; stroke: none; }}
    .door {{ fill: none; stroke: #666; stroke-width: 1.5; stroke-dasharray: 4,2; }}
    .window {{ fill: none; stroke: #4A90D9; stroke-width: 3; }}
    .dim {{ font-family: sans-serif; font-size: 9px; fill: #666; text-anchor: middle; }}
    .label {{ font-family: sans-serif; font-size: 11px; fill: #333; text-anchor: middle; font-weight: bold; }}
    .area {{ font-family: sans-serif; font-size: 14px; fill: #333; text-anchor: middle; font-weight: bold; }}
  </style>

  <!-- 背景 -->
  <rect width="{w:.0f}" height="{h:.0f}" fill="white"/>

  <!-- メイン居室（床塗り） -->
  <rect class="room" x="{ox}" y="{oy}" width="{mm(TOTAL_W):.1f}" height="{mm(TOTAL_H):.1f}"/>

  <!-- バスルーム -->
  <rect class="bath" x="{ox}" y="{oy}" width="{mm(BATH_W):.1f}" height="{mm(BATH_H):.1f}"/>

  <!-- キッチンエリア -->
  <rect class="kitchen" x="{ox}" y="{oy + mm(BATH_H)}" width="{mm(BATH_W):.1f}" height="{mm(TOTAL_H - BATH_H):.1f}"/>

  <!-- バルコニー -->
  <rect class="balcony" x="{ox + mm(TOTAL_W - BALCONY_DEPTH)}" y="{oy}" width="{mm(BALCONY_DEPTH):.1f}" height="{mm(TOTAL_H):.1f}"/>

  <!-- 外壁 -->
  <rect class="wall" x="{ox}" y="{oy}" width="{mm(TOTAL_W):.1f}" height="{mm(TOTAL_H):.1f}"/>

  <!-- バスルーム壁 -->
  <line class="wall" x1="{ox}" y1="{oy + mm(BATH_H)}" x2="{ox + mm(BATH_W)}" y2="{oy + mm(BATH_H)}"/>
  <line class="wall" x1="{ox + mm(BATH_W)}" y1="{oy}" x2="{ox + mm(BATH_W)}" y2="{oy + mm(BATH_H)}"/>

  <!-- キッチン/廊下の仕切り壁 -->
  <line class="wall" x1="{ox + mm(BATH_W)}" y1="{oy + mm(BATH_H)}" x2="{ox + mm(BATH_W)}" y2="{oy + mm(TOTAL_H)}"/>

  <!-- バスルーム内部: トイレ -->
  <rect x="{ox + 8}" y="{oy + mm(BATH_H) - 35}" width="20" height="28" rx="3" fill="#DDD" stroke="#999" stroke-width="1"/>
  <!-- バスルーム内部: 浴槽 -->
  <rect x="{ox + mm(BATH_W) - 55}" y="{oy + 8}" width="45" height="{mm(BATH_H) - 50:.1f}" rx="5" fill="#D0E8F0" stroke="#999" stroke-width="1"/>
  <!-- バスルーム内部: 洗面台 -->
  <rect x="{ox + 8}" y="{oy + 8}" width="25" height="18" rx="2" fill="#DDD" stroke="#999" stroke-width="1"/>

  <!-- キッチンカウンター -->
  <rect x="{ox + 4}" y="{oy + mm(BATH_H) + 8}" width="14" height="{mm(KITCHEN_W):.1f}" rx="1" fill="#DDB" stroke="#999" stroke-width="1"/>

  <!-- バスルームドア -->
  <path class="door" d="M {ox + mm(BATH_W) - 5} {oy + mm(BATH_H) - 2} L {ox + mm(BATH_W) - 5} {oy + mm(BATH_H) - 40}"/>

  <!-- 玄関ドア -->
  <line class="door" x1="{ox + mm(BATH_W) + 10}" y1="{oy + mm(TOTAL_H)}" x2="{ox + mm(BATH_W) + 10 + mm(ENTRANCE_W)}" y2="{oy + mm(TOTAL_H)}"/>
  <text class="label" x="{ox + mm(BATH_W) + 10 + mm(ENTRANCE_W)/2}" y="{oy + mm(TOTAL_H) - 5}">玄関</text>

  <!-- 窓（東側・バルコニーの内側線） -->
  <line class="window" x1="{ox + mm(TOTAL_W - BALCONY_DEPTH)}" y1="{oy + 15}" x2="{ox + mm(TOTAL_W - BALCONY_DEPTH)}" y2="{oy + mm(TOTAL_H) - 15}"/>

  <!-- ラベル -->
  <text class="label" x="{ox + mm(BATH_W)/2}" y="{oy + mm(BATH_H)/2}">浴室・トイレ</text>
  <text class="dim" x="{ox + mm(BATH_W)/2}" y="{oy + mm(BATH_H)/2 + 14}">UB</text>

  <text class="label" x="{ox + mm(BATH_W)/2}" y="{oy + mm(BATH_H) + mm((TOTAL_H-BATH_H)/2)}">キッチン</text>

  <text class="label" x="{ox + mm(BATH_W) + mm((TOTAL_W - BATH_W - BALCONY_DEPTH)/2)}" y="{oy + mm(TOTAL_H)/2 - 10}">居室</text>
  <text class="area" x="{ox + mm(BATH_W) + mm((TOTAL_W - BATH_W - BALCONY_DEPTH)/2)}" y="{oy + mm(TOTAL_H)/2 + 10}">35.83m²</text>

  <text class="label" x="{ox + mm(TOTAL_W - BALCONY_DEPTH/2)}" y="{oy + mm(TOTAL_H)/2}">バルコニー</text>

  <!-- 寸法線 -->
  <!-- 横幅（上） -->
  <text class="dim" x="{ox + mm(TOTAL_W)/2}" y="{oy - 10}">8,636</text>
  <line x1="{ox}" y1="{oy - 5}" x2="{ox + mm(TOTAL_W)}" y2="{oy - 5}" stroke="#999" stroke-width="0.5"/>

  <!-- バスルーム幅 -->
  <text class="dim" x="{ox + mm(BATH_W)/2}" y="{oy - 22}">2,275</text>

  <!-- 縦（右） -->
  <text class="dim" x="{ox + mm(TOTAL_W) + 25}" y="{oy + mm(TOTAL_H)/2}" transform="rotate(90, {ox + mm(TOTAL_W) + 25}, {oy + mm(TOTAL_H)/2})">6,370</text>

</svg>'''
    return svg

def main():
    output_dir = os.path.dirname(os.path.abspath(__file__))
    svg_path = os.path.join(output_dir, "floorplan.svg")
    png_path = os.path.join(output_dir, "floorplan.png")

    # SVG生成
    svg = generate_svg()
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"SVG生成完了: {svg_path}")

    # SVG→PNG変換（ImageMagickまたはrsvg-convert）
    try:
        subprocess.run([
            "convert", "-density", "200", "-background", "white",
            svg_path, png_path
        ], check=True, capture_output=True)
        print(f"PNG変換完了: {png_path}")
    except FileNotFoundError:
        try:
            subprocess.run([
                "rsvg-convert", "-d", "200", "-p", "200",
                "-o", png_path, svg_path
            ], check=True, capture_output=True)
            print(f"PNG変換完了（rsvg）: {png_path}")
        except FileNotFoundError:
            print("警告: ImageMagick/rsvg-convert が未インストール。SVGのみ出力。")
            print("手動変換: convert -density 200 floorplan.svg floorplan.png")

if __name__ == "__main__":
    main()
