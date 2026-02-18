---
title: "{{ report_title }}"
date: "{{ date }}"
client: "{{ client_name }}"
type: "rental_valuation"
---

<!-- ============================================================ -->
<!--  ROCKEDGE Property Management | HIROKI                       -->
<!--  賃料査定AI分析レポート                                         -->
<!-- ============================================================ -->

# {{ report_title }}

**ROCKEDGE Property Management**
**担当: HIROKI**

| 項目 | 内容 |
|------|------|
| レポート作成日 | {{ date }} |
| クライアント | {{ client_name }} |
| 対象物件 | {{ property_name }} |
| 物件所在地 | {{ property_address }} |
| レポートID | {{ report_id }} |

---

## 目次

1. [エグゼクティブサマリー](#1-エグゼクティブサマリー)
2. [物件概要](#2-物件概要)
3. [AI査定結果](#3-ai査定結果)
4. [比較物件分析](#4-比較物件分析)
5. [賃料設定要因分析](#5-賃料設定要因分析)
6. [エリアマーケット分析](#6-エリアマーケット分析)
7. [収益シミュレーション](#7-収益シミュレーション)
8. [賃料最適化提案](#8-賃料最適化提案)
9. [リスク分析](#9-リスク分析)
10. [プロフェッショナル所見](#10-プロフェッショナル所見)

---

## 1. エグゼクティブサマリー

{{ executive_summary }}

### AI査定結果ハイライト

| 項目 | 結果 |
|------|------|
| 推奨賃料 | **{{ recommended_rent }}** |
| 査定賃料レンジ | {{ rent_range_low }} 〜 {{ rent_range_high }} |
| 市場平均との比較 | {{ market_comparison }} |
| 信頼度スコア | {{ confidence_score }} |

---

## 2. 物件概要

### 2.1 基本情報

| 項目 | 詳細 |
|------|------|
| 物件名 | {{ property_name }} |
| 所在地 | {{ property_address }} |
| 最寄駅 | {{ nearest_station }} (徒歩 {{ walk_minutes }}分) |
| 構造 | {{ building_structure }} |
| 築年数 | {{ building_age }}年 ({{ construction_year }}年築) |
| 階数 | {{ floor_count }}階建 / {{ target_floor }}階 |
| 専有面積 | {{ floor_area }} m2 |
| 間取り | {{ layout }} |
| 向き | {{ direction }} |
| 駐車場 | {{ parking }} |

### 2.2 設備・仕様

{{ equipment_details }}

### 2.3 物件写真・状態評価

{{ property_condition }}

---

## 3. AI査定結果

### 3.1 査定モデル概要

{{ ai_model_description }}

### 3.2 査定結果詳細

| 査定手法 | 算出賃料 | 重み |
|---------|----------|:----:|
| 取引事例比較法 (AI) | {{ comp_based_rent }} | {{ comp_weight }} |
| 収益還元法 (AI) | {{ income_based_rent }} | {{ income_weight }} |
| ヘドニック法 (AI) | {{ hedonic_rent }} | {{ hedonic_weight }} |
| **加重平均推奨賃料** | **{{ recommended_rent }}** | - |

### 3.3 査定精度指標

| 指標 | 値 |
|------|------|
| 予測精度 (R2) | {{ r2_score }} |
| 平均誤差率 | {{ mean_error_rate }} |
| 使用データ件数 | {{ data_count }}件 |
| データ取得期間 | {{ data_period }} |

### 3.4 賃料感応度分析

{{ sensitivity_analysis }}

---

## 4. 比較物件分析

### 4.1 類似物件一覧

{% for comp in comparable_properties %}
#### {{ comp.name }}

| 項目 | 詳細 |
|------|------|
| 所在地 | {{ comp.address }} |
| 最寄駅 | {{ comp.station }} (徒歩 {{ comp.walk_min }}分) |
| 築年数 | {{ comp.age }}年 |
| 間取り / 面積 | {{ comp.layout }} / {{ comp.area }} m2 |
| 賃料 | {{ comp.rent }} |
| 管理費 | {{ comp.management_fee }} |
| 賃料単価 | {{ comp.rent_per_sqm }} 円/m2 |

{% endfor %}

### 4.2 比較分析サマリー

{{ comparison_summary }}

---

## 5. 賃料設定要因分析

### 5.1 プラス要因

{{ positive_factors }}

### 5.2 マイナス要因

{{ negative_factors }}

### 5.3 要因別影響度

| 要因 | 影響度 | 金額換算 |
|------|:------:|----------|
{% for factor in rent_factors %}| {{ factor.name }} | {{ factor.impact_level }} | {{ factor.amount_impact }} |
{% endfor %}

---

## 6. エリアマーケット分析

### 6.1 エリア賃料トレンド

{{ area_rent_trend }}

### 6.2 空室率推移

{{ vacancy_trend }}

### 6.3 需要動向

{{ demand_trend }}

### 6.4 競合供給状況

{{ supply_situation }}

---

## 7. 収益シミュレーション

### 7.1 シナリオ別収益予測

| シナリオ | 設定賃料 | 想定空室率 | 年間収入 | 実質利回り |
|---------|----------|:---------:|----------|:---------:|
| 強気 | {{ scenario_high_rent }} | {{ scenario_high_vacancy }} | {{ scenario_high_income }} | {{ scenario_high_yield }} |
| 標準 | {{ scenario_mid_rent }} | {{ scenario_mid_vacancy }} | {{ scenario_mid_income }} | {{ scenario_mid_yield }} |
| 保守的 | {{ scenario_low_rent }} | {{ scenario_low_vacancy }} | {{ scenario_low_income }} | {{ scenario_low_yield }} |

### 7.2 長期収益予測 (5年間)

{{ long_term_projection }}

### 7.3 キャッシュフロー分析

{{ cashflow_analysis }}

---

## 8. 賃料最適化提案

### 8.1 推奨賃料設定

{{ recommended_rent_strategy }}

### 8.2 付加価値向上施策

{{ value_add_suggestions }}

### 8.3 募集条件の最適化

{{ listing_optimization }}

---

## 9. リスク分析

### 9.1 賃料下落リスク

{{ rent_decline_risk }}

### 9.2 空室長期化リスク

{{ vacancy_risk }}

### 9.3 外部環境リスク

{{ external_risk }}

---

## 10. プロフェッショナル所見

{{ professional_insight }}

### 最終推奨賃料

| 項目 | 金額 |
|------|------|
| 推奨賃料 | **{{ final_recommended_rent }}** |
| 推奨管理費 | {{ final_recommended_mgmt_fee }} |
| 推奨敷金 | {{ final_recommended_deposit }} |
| 推奨礼金 | {{ final_recommended_key_money }} |

### 次のステップ

{{ next_steps }}

---

{{ content }}

---

> **ROCKEDGE Property Management | HIROKI**
> 作成日: {{ date }}
> 本レポートは {{ client_name }} 様専用に作成された機密資料です。
> 無断転載・複製・第三者への開示を固く禁じます。
> (C) ROCKEDGE Property Management. All Rights Reserved.
