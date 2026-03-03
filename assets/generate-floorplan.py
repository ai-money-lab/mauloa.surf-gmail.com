#!/usr/bin/env python3
"""
間取り図生成スクリプト

JSON設定ファイルから間取り図SVG/PNGを生成し、
nano-banana のリファレンス画像として使えるようにする。

使い方:
  python generate-floorplan.py                    # デフォルト設定
  python generate-floorplan.py config.json        # JSON設定ファイル指定
  python generate-floorplan.py -o output-name     # 出力ファイル名指定
"""
import subprocess
import os
import sys
import json

# デフォルト設定
DEFAULT_CONFIG = {
    "name": "default",
    "area_sqm": 35.83,
    # 外形（単位: mm）
    "total_w": 8636,
    "total_h": 6370,
    # 部屋定義: type, x, y, w, h, label
    "rooms": [
        {"type": "room", "x": 0, "y": 0, "w": 8636, "h": 6370, "label": "居室"},
        {"type": "bath", "x": 0, "y": 0, "w": 2275, "h": 2730, "label": "浴室・トイレ"},
        {"type": "kitchen", "x": 0, "y": 2730, "w": 2275, "h": 3640, "label": "キッチン"},
        {"type": "balcony", "x": 7726, "y": 0, "w": 910, "h": 6370, "label": "バルコニー"}
    ],
    # 壁（内壁）: x1, y1, x2, y2
    "walls": [
        {"x1": 0, "y1": 2730, "x2": 2275, "y2": 2730},
        {"x1": 2275, "y1": 0, "x2": 2275, "y2": 2730},
        {"x1": 2275, "y1": 2730, "x2": 2275, "y2": 6370}
    ],
    # 窓: x1, y1, x2, y2
    "windows": [
        {"x1": 7726, "y1": 200, "x2": 7726, "y2": 6170}
    ],
    # ドア: x1, y1, x2, y2, label（任意）
    "doors": [
        {"x1": 2285, "y1": 6370, "x2": 3195, "y2": 6370, "label": "玄関"}
    ],
    # 設備: type, x, y, w, h
    "fixtures": [
        {"type": "bathtub", "x": 1720, "y": 100, "w": 450, "h": 2480},
        {"type": "toilet", "x": 100, "y": 2380, "w": 250, "h": 350},
        {"type": "sink", "x": 100, "y": 100, "w": 310, "h": 220},
        {"type": "kitchen_counter", "x": 50, "y": 2830, "w": 175, "h": 1820}
    ],
    # 寸法線表示
    "dimensions": [
        {"value": "8,636", "x": 4318, "y": -150, "orientation": "h"},
        {"value": "2,275", "x": 1137, "y": -300, "orientation": "h"},
        {"value": "6,370", "x": 8886, "y": 3185, "orientation": "v"}
    ]
}

SCALE = 0.08
MARGIN = 40

ROOM_COLORS = {
    "room": "#FFF8F0",
    "bath": "#E8F4F8",
    "kitchen": "#FFF0E0",
    "balcony": "#E8F8E8",
    "closet": "#F0F0F0",
    "hallway": "#FFFBE8",
    "bedroom": "#F0E8F8",
    "living": "#FFF8F0",
}

FIXTURE_RENDERERS = {
    "bathtub": lambda x, y, w, h: f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="#D0E8F0" stroke="#999" stroke-width="1"/>',
    "toilet": lambda x, y, w, h: f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="#DDD" stroke="#999" stroke-width="1"/>',
    "sink": lambda x, y, w, h: f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2" fill="#DDD" stroke="#999" stroke-width="1"/>',
    "kitchen_counter": lambda x, y, w, h: f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="1" fill="#DDB" stroke="#999" stroke-width="1"/>',
    "washer": lambda x, y, w, h: f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="#E0E0E0" stroke="#999" stroke-width="1"/>',
}


def mm(v):
    return v * SCALE


def generate_svg(config):
    total_w = config["total_w"]
    total_h = config["total_h"]
    w = mm(total_w) + MARGIN * 2
    h = mm(total_h) + MARGIN * 2
    ox, oy = MARGIN, MARGIN

    parts = []
    parts.append(f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}">
  <style>
    .wall {{ fill: none; stroke: #333; stroke-width: 3; }}
    .door {{ fill: none; stroke: #666; stroke-width: 1.5; stroke-dasharray: 4,2; }}
    .window {{ fill: none; stroke: #4A90D9; stroke-width: 3; }}
    .dim {{ font-family: sans-serif; font-size: 9px; fill: #666; text-anchor: middle; }}
    .label {{ font-family: sans-serif; font-size: 11px; fill: #333; text-anchor: middle; font-weight: bold; }}
    .area {{ font-family: sans-serif; font-size: 14px; fill: #333; text-anchor: middle; font-weight: bold; }}
  </style>
  <rect width="{w:.0f}" height="{h:.0f}" fill="white"/>''')

    # 部屋の塗り
    for room in config.get("rooms", []):
        color = ROOM_COLORS.get(room["type"], "#F8F8F8")
        rx = ox + mm(room["x"])
        ry = oy + mm(room["y"])
        rw = mm(room["w"])
        rh = mm(room["h"])
        parts.append(f'  <rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" fill="{color}"/>')

    # 外壁
    parts.append(f'  <rect class="wall" x="{ox}" y="{oy}" width="{mm(total_w):.1f}" height="{mm(total_h):.1f}"/>')

    # 内壁
    for wall in config.get("walls", []):
        parts.append(f'  <line class="wall" x1="{ox + mm(wall["x1"]):.1f}" y1="{oy + mm(wall["y1"]):.1f}" x2="{ox + mm(wall["x2"]):.1f}" y2="{oy + mm(wall["y2"]):.1f}"/>')

    # 窓
    for win in config.get("windows", []):
        parts.append(f'  <line class="window" x1="{ox + mm(win["x1"]):.1f}" y1="{oy + mm(win["y1"]):.1f}" x2="{ox + mm(win["x2"]):.1f}" y2="{oy + mm(win["y2"]):.1f}"/>')

    # ドア
    for door in config.get("doors", []):
        dx1 = ox + mm(door["x1"])
        dy1 = oy + mm(door["y1"])
        dx2 = ox + mm(door["x2"])
        dy2 = oy + mm(door["y2"])
        parts.append(f'  <line class="door" x1="{dx1:.1f}" y1="{dy1:.1f}" x2="{dx2:.1f}" y2="{dy2:.1f}"/>')
        if "label" in door:
            cx = (dx1 + dx2) / 2
            cy = min(dy1, dy2) - 5
            parts.append(f'  <text class="label" x="{cx:.1f}" y="{cy:.1f}">{door["label"]}</text>')

    # 設備
    for fix in config.get("fixtures", []):
        renderer = FIXTURE_RENDERERS.get(fix["type"])
        if renderer:
            fx = ox + mm(fix["x"])
            fy = oy + mm(fix["y"])
            fw = mm(fix["w"])
            fh = mm(fix["h"])
            parts.append(f'  {renderer(f"{fx:.1f}", f"{fy:.1f}", f"{fw:.1f}", f"{fh:.1f}")}')

    # ラベル
    for room in config.get("rooms", []):
        if "label" in room:
            cx = ox + mm(room["x"] + room["w"] / 2)
            cy = oy + mm(room["y"] + room["h"] / 2)
            parts.append(f'  <text class="label" x="{cx:.1f}" y="{cy:.1f}">{room["label"]}</text>')

    # 面積表示（メイン居室）
    area = config.get("area_sqm")
    if area:
        main_room = next((r for r in config.get("rooms", []) if r["type"] == "room"), None)
        if main_room:
            cx = ox + mm(main_room["x"] + main_room["w"] / 2)
            cy = oy + mm(main_room["y"] + main_room["h"] / 2) + 16
            parts.append(f'  <text class="area" x="{cx:.1f}" y="{cy:.1f}">{area}m²</text>')

    # 寸法線
    for dim in config.get("dimensions", []):
        dx = ox + mm(dim["x"])
        dy = oy + mm(dim["y"])
        if dim.get("orientation") == "v":
            parts.append(f'  <text class="dim" x="{dx:.1f}" y="{dy:.1f}" transform="rotate(90, {dx:.1f}, {dy:.1f})">{dim["value"]}</text>')
        else:
            parts.append(f'  <text class="dim" x="{dx:.1f}" y="{dy:.1f}">{dim["value"]}</text>')

    parts.append('</svg>')
    return '\n'.join(parts)


def svg_to_png(svg_path, png_path):
    """SVG→PNG変換（ImageMagick or rsvg-convert）"""
    try:
        subprocess.run(
            ["convert", "-density", "200", "-background", "white", svg_path, png_path],
            check=True, capture_output=True
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    try:
        subprocess.run(
            ["rsvg-convert", "-d", "200", "-p", "200", "-o", png_path, svg_path],
            check=True, capture_output=True
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def main():
    config = DEFAULT_CONFIG.copy()
    output_name = "floorplan"
    output_dir = os.path.dirname(os.path.abspath(__file__))

    # 引数パース
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "-o" and i + 1 < len(args):
            output_name = args[i + 1]
            i += 2
        elif args[i] == "-d" and i + 1 < len(args):
            output_dir = args[i + 1]
            i += 2
        elif args[i].endswith(".json"):
            with open(args[i], "r", encoding="utf-8") as f:
                config = json.load(f)
            i += 1
        else:
            i += 1

    svg_path = os.path.join(output_dir, f"{output_name}.svg")
    png_path = os.path.join(output_dir, f"{output_name}.png")

    svg = generate_svg(config)
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"SVG: {svg_path}")

    if svg_to_png(svg_path, png_path):
        print(f"PNG: {png_path}")
    else:
        print("PNG変換失敗（ImageMagick/rsvg-convert未検出）")

    return png_path


if __name__ == "__main__":
    main()
