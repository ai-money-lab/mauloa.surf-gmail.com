---
title: "{{ report_title }}"
date: "{{ date }}"
client: "{{ client_name }}"
type: "area_analysis"
---

<!-- ============================================================ -->
<!--  ROCKEDGE Property Management | HIROKI                       -->
<!--  不動産投資エリア分析レポート                                    -->
<!-- ============================================================ -->

# {{ report_title }}

**ROCKEDGE Property Management**
**担当: HIROKI**

| 項目 | 内容 |
|------|------|
| レポート作成日 | {{ date }} |
| クライアント | {{ client_name }} |
| 対象エリア | {{ target_area }} |
| 分析対象期間 | {{ analysis_period }} |
| レポートID | {{ report_id }} |

---

## 目次

1. [エグゼクティブサマリー](#1-エグゼクティブサマリー)
2. [エリア概要](#2-エリア概要)
3. [人口動態分析](#3-人口動態分析)
4. [賃貸市場分析](#4-賃貸市場分析)
5. [売買市場分析](#5-売買市場分析)
6. [競合物件分析](#6-競合物件分析)
7. [交通・インフラ分析](#7-交通インフラ分析)
8. [将来性評価](#8-将来性評価)
9. [投資リスク評価](#9-投資リスク評価)
10. [プロフェッショナル所見](#10-プロフェッショナル所見)

---

## 1. エグゼクティブサマリー

{{ executive_summary }}

### 総合評価スコア

| 評価項目 | スコア (5段階) | 備考 |
|----------|:--------------:|------|
| 収益性 | {{ score_profitability }} | {{ note_profitability }} |
| 安定性 | {{ score_stability }} | {{ note_stability }} |
| 成長性 | {{ score_growth }} | {{ note_growth }} |
| 流動性 | {{ score_liquidity }} | {{ note_liquidity }} |
| **総合評価** | **{{ score_overall }}** | {{ note_overall }} |

---

## 2. エリア概要

### 2.1 基本情報

{{ area_overview }}

| 項目 | データ |
|------|--------|
| 所在地 | {{ area_location }} |
| 最寄駅 | {{ nearest_station }} |
| 主要駅までの所要時間 | {{ travel_time_to_major_station }} |
| 用途地域 | {{ zoning_type }} |
| 平均地価 (円/m2) | {{ avg_land_price }} |

### 2.2 生活利便施設

{{ area_amenities }}

---

## 3. 人口動態分析

### 3.1 人口推移

{{ population_trend }}

### 3.2 世帯構成

{{ household_composition }}

### 3.3 年齢別人口構成

{{ age_distribution }}

---

## 4. 賃貸市場分析

### 4.1 賃料相場

| 間取り | 平均賃料 | 前年比 | 空室率 |
|--------|----------|--------|--------|
{% for unit in rental_market_data %}| {{ unit.layout }} | {{ unit.avg_rent }} | {{ unit.yoy_change }} | {{ unit.vacancy_rate }} |
{% endfor %}

### 4.2 需給バランス

{{ supply_demand_analysis }}

### 4.3 入居者属性

{{ tenant_demographics }}

---

## 5. 売買市場分析

### 5.1 取引価格推移

{{ transaction_price_trend }}

### 5.2 利回り分析

| 物件タイプ | 表面利回り | 実質利回り |
|-----------|-----------|-----------|
{% for prop in yield_data %}| {{ prop.type }} | {{ prop.gross_yield }} | {{ prop.net_yield }} |
{% endfor %}

### 5.3 売買取引動向

{{ sales_transaction_trend }}

---

## 6. 競合物件分析

{{ competitor_analysis }}

### 主要競合物件一覧

{% for comp in competitor_properties %}
#### {{ comp.name }}

- 所在地: {{ comp.address }}
- 築年数: {{ comp.age }}
- 賃料帯: {{ comp.rent_range }}
- 空室率: {{ comp.vacancy_rate }}
- 特徴: {{ comp.features }}

{% endfor %}

---

## 7. 交通・インフラ分析

### 7.1 交通アクセス

{{ transportation_access }}

### 7.2 再開発計画

{{ redevelopment_plans }}

### 7.3 インフラ整備状況

{{ infrastructure_status }}

---

## 8. 将来性評価

### 8.1 中期予測 (3-5年)

{{ mid_term_forecast }}

### 8.2 長期予測 (5-10年)

{{ long_term_forecast }}

### 8.3 注目ポイント

{{ key_highlights }}

---

## 9. 投資リスク評価

### 9.1 主要リスク要因

{{ risk_factors }}

### 9.2 リスク軽減策

{{ risk_mitigation }}

### 9.3 災害リスク

| リスク種別 | 評価 | 詳細 |
|-----------|------|------|
| 地震リスク | {{ earthquake_risk }} | {{ earthquake_detail }} |
| 水害リスク | {{ flood_risk }} | {{ flood_detail }} |
| 液状化リスク | {{ liquefaction_risk }} | {{ liquefaction_detail }} |

---

## 10. プロフェッショナル所見

{{ professional_insight }}

### 推奨アクション

{{ recommended_actions }}

### 投資判断サマリー

| 項目 | 判断 |
|------|------|
| 投資推奨度 | {{ investment_recommendation }} |
| 推奨投資タイプ | {{ recommended_investment_type }} |
| 推奨保有期間 | {{ recommended_holding_period }} |
| 想定ROI | {{ expected_roi }} |

---

{{ content }}

---

> **ROCKEDGE Property Management | HIROKI**
> 作成日: {{ date }}
> 本レポートは {{ client_name }} 様専用に作成された機密資料です。
> 無断転載・複製・第三者への開示を固く禁じます。
> (C) ROCKEDGE Property Management. All Rights Reserved.
