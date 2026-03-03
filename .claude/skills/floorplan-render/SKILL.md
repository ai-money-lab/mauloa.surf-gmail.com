---
name: floorplan-render
description: "間取り図画像をチャットにドロップするだけで、フォトリアルな内観パース＆トップダウン俯瞰レンダリングを自動生成する。画像を添付して「/floorplan-render」と入力するだけで動作。"
---

# /floorplan-render — 間取り図→フォトリアルレンダリング

チャットに添付された間取り図画像から、フォトリアルなレンダリングを自動生成するスキル。

## 仕組み

Claude Code では**チャットに添付された画像はファイルシステムに保存されない**（base64としてメモリ上のみ）。
そのため nano-banana の `-r`（リファレンス画像）に直接渡せない。

このスキルは以下のパイプラインでこの制約を回避する:

```
[ユーザーが間取り図をドロップ]
    ↓  Claude が画像を目視分析
[寸法・レイアウト・設備を読み取り]
    ↓  JSON設定ファイルとして構造化
[assets/generate-floorplan.py で SVG/PNG を生成]
    ↓  正確な間取り図ファイルが完成
[nano-banana -r assets/floorplan.png で各ビュー生成]
    ↓  リファレンス付き高精度レンダリング
[完成画像を表示]
```

## 実行手順（Claudeが自動実行する）

### Step 1: 間取り図を分析

添付された間取り図画像から以下を正確に読み取る:

- **総面積**（m²）
- **外形寸法**（横mm × 縦mm）
- **各部屋の位置・サイズ**: type（room/bath/kitchen/balcony/closet/hallway/bedroom/living）、座標(x,y)、サイズ(w,h)、ラベル
- **内壁の位置**: 始点(x1,y1)→終点(x2,y2)
- **窓の位置**: 始点→終点
- **ドアの位置**: 始点→終点、ラベル
- **設備**: bathtub, toilet, sink, kitchen_counter, washer 等の位置・サイズ
- **寸法線**: 表示値、位置、向き(h/v)

**重要**: 原点(0,0)は左上。全ての座標はmm単位。

### Step 2: JSON設定ファイルを作成

読み取ったデータを `assets/<物件名>.json` に保存:

```json
{
  "name": "物件名",
  "area_sqm": 35.83,
  "total_w": 8636,
  "total_h": 6370,
  "rooms": [
    {"type": "room", "x": 0, "y": 0, "w": 8636, "h": 6370, "label": "居室"}
  ],
  "walls": [
    {"x1": 0, "y1": 2730, "x2": 2275, "y2": 2730}
  ],
  "windows": [
    {"x1": 7726, "y1": 200, "x2": 7726, "y2": 6170}
  ],
  "doors": [
    {"x1": 2285, "y1": 6370, "x2": 3195, "y2": 6370, "label": "玄関"}
  ],
  "fixtures": [
    {"type": "bathtub", "x": 1720, "y": 100, "w": 450, "h": 2480}
  ],
  "dimensions": [
    {"value": "8,636", "x": 4318, "y": -150, "orientation": "h"}
  ]
}
```

### Step 3: SVG/PNG間取り図を生成

```bash
python assets/generate-floorplan.py assets/<物件名>.json -o floorplan
```

生成されたPNGをReadツールで表示し、元の間取り図と比較して精度を確認する。
大きな差異があればJSONを修正して再生成する。

### Step 4: フォトリアルレンダリングを生成

**内観パース（玄関からの視点）:**
```bash
nano-banana "Generate a photorealistic eye-level interior perspective of this Japanese apartment from the entrance looking into the main room. Use the provided floor plan as the exact layout reference. [部屋の特徴を記述]. Wooden flooring, white walls, modern Japanese minimalist style. Warm natural daylight. Architectural photography." -r assets/floorplan.png -s 2K -a 4:3 -o <物件名>-interior
```

**トップダウン俯瞰:**
```bash
nano-banana "Analyze the provided floor plan and generate a photorealistic top-down (true 90° orthographic) rendering of the entire apartment, keeping the exact same dimensions, proportions, walls, doors, windows as shown. [面積・レイアウト概要]. Style: Modern Japanese (Japandi) light natural wood, warm neutral tones, minimalist furniture, clean lines, matte black accents, soft natural daylight. Architectural visualization, ultra-realistic materials, no perspective distortion." -r assets/floorplan.png -s 2K -a 4:3 -o <物件名>-topdown
```

### Step 5: 結果を表示

Readツールで生成された画像を表示する。

## オプション

ユーザーが追加指示を出した場合:

| 指示 | 対応 |
|------|------|
| 「家具付きで」 | プロンプトに家具配置の指示を追加 |
| 「Proモデルで」 | `-m pro` を追加 |
| 「4Kで」 | `-s 4K` を追加 |
| 「スカンジナビアンスタイルで」 | プロンプトのスタイル記述を変更 |
| 「リビングからの視点で」 | パースの視点記述を変更 |
| 「バルコニーからの眺めも」 | 追加のレンダリングを生成 |

## 対応する部屋タイプ

| type | 色 | 用途 |
|------|-----|------|
| room | ベージュ | メイン居室 |
| bath | 水色 | 浴室・トイレ |
| kitchen | オレンジ | キッチン |
| balcony | 緑 | バルコニー |
| closet | グレー | 収納 |
| hallway | 黄色 | 廊下 |
| bedroom | 紫 | 寝室 |
| living | ベージュ | リビング |

## 対応する設備タイプ

bathtub, toilet, sink, kitchen_counter, washer

## 出力ファイル

- `assets/<物件名>.json` — 構造化データ（再利用可能）
- `assets/floorplan.svg` — ベクター間取り図
- `assets/floorplan.png` — リファレンス用PNG
- `<物件名>-interior.png` — 内観パースレンダリング
- `<物件名>-topdown.png` — トップダウン俯瞰レンダリング
