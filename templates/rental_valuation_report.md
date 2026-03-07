# 賃料査定AI分析レポート

## {{ property_name | default("対象物件") }}

作成者: {{ header }} / {{ author }}
作成日: {{ date }}
CONFIDENTIAL

---

## 目次

1. 査定結果サマリー
2. 対象物件概要
3. 周辺賃料相場分析
4. 比較物件データ
5. 適正賃料の算出
6. 賃料設定シミュレーション
7. 競合物件との差別化ポイント
8. 賃料最大化のための改善提案
9. プロフェッショナル所見
10. 付録

---

## 1. 査定結果サマリー

| 項目 | 結果 |
|------|------|
| 推定適正賃料 | {{ estimated_rent | default("¥---,---") }} |
| 賃料レンジ | {{ rent_range | default("¥---,--- 〜 ¥---,---") }} |
| 対周辺相場 | {{ vs_market | default("---") }} |
| 推奨募集賃料 | {{ recommended_rent | default("¥---,---") }} |
| 想定空室期間 | {{ expected_vacancy | default("---") }} |

---

## 2. 対象物件概要

{{ property_overview | default("（物件情報）") }}

### 2.1 設備・仕様一覧

{{ equipment_list | default("（設備詳細リスト）") }}

---

## 3. 周辺賃料相場分析

### 3.1 駅距離別・築年別相場

{{ market_analysis | default("（相場分析データ）") }}

![賃料相場ヒートマップ]({{ chart_rental_heatmap | default("") }})

### 3.2 エリア別賃料比較

{{ area_comparison | default("（周辺エリアとの賃料比較）") }}

### 3.3 賃料トレンド（過去3年）

{{ rental_trend | default("（賃料の上昇/下降トレンド）") }}

---

## 4. 比較物件データ

### 4.1 成約事例（直近6ヶ月）

{{ comparable_properties | default("（比較物件一覧）") }}

### 4.2 現在募集中の競合物件

{{ current_listings | default("（現在募集中の類似物件）") }}

### 4.3 比較物件の個別データシート

{{ comparable_details | default("（各比較物件の詳細情報）") }}

---

## 5. 適正賃料の算出

### 5.1 取引事例比較法

{{ rent_comparison_method | default("（取引事例による算出）") }}

### 5.2 賃料利回り法

{{ rent_yield_method | default("（利回りからの逆算）") }}

### 5.3 AI回帰分析法

{{ rent_ai_method | default("（機械学習モデルによる予測）") }}

### 5.4 総合判定

{{ rent_calculation | default("（3手法の統合結果）") }}

---

## 6. 賃料設定シミュレーション

{{ rent_simulation | default("（シミュレーション結果）") }}

![賃料設定シミュレーション]({{ chart_rent_simulation | default("") }})

### 6.1 推奨賃料戦略

{{ rent_strategy | default("（募集開始価格と改定タイミングの提案）") }}

---

## 7. 競合物件との差別化ポイント

{{ differentiation_points | default("（競合と比較した本物件の強み・弱み）") }}

---

## 8. 賃料最大化のための改善提案

### 8.1 費用対効果の高い設備投資

{{ improvement_suggestions | default("（設備投資の提案と期待効果）") }}

### 8.2 ターゲット層の最適化

{{ target_optimization | default("（ターゲット入居者層の提案）") }}

---

## 9. プロフェッショナル所見

{{ professional_insight | default("（HIROKI所見）") }}

---

## 10. 付録

### A. データソース一覧

{{ data_sources | default("（使用データの出典一覧）") }}

### B. AI分析モデルの精度情報

{{ model_accuracy | default("（回帰モデルのR²、MAE等）") }}

### C. 免責事項

本レポートは{{ header }}が作成したものです。
査定額は参考値であり、実際の成約賃料を保証するものではありません。
{{ date }} 作成 | CONFIDENTIAL
