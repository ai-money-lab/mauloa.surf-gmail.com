---
title: "{{ report_title }}"
date: "{{ date }}"
client: "{{ client_name }}"
type: "sell_strategy"
---

<!-- ============================================================ -->
<!--  ROCKEDGE Property Management | HIROKI                       -->
<!--  物件売却戦略レポート                                           -->
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
2. [物件概要・評価](#2-物件概要評価)
3. [市場環境分析](#3-市場環境分析)
4. [売却価格査定](#4-売却価格査定)
5. [ターゲットバイヤー分析](#5-ターゲットバイヤー分析)
6. [売却戦略立案](#6-売却戦略立案)
7. [マーケティング計画](#7-マーケティング計画)
8. [売却スケジュール](#8-売却スケジュール)
9. [税務・法務アドバイス](#9-税務法務アドバイス)
10. [プロフェッショナル所見](#10-プロフェッショナル所見)

---

## 1. エグゼクティブサマリー

{{ executive_summary }}

### 売却戦略ハイライト

| 項目 | 内容 |
|------|------|
| 推奨売出価格 | **{{ recommended_listing_price }}** |
| 想定成約価格 | {{ expected_selling_price }} |
| 推奨売却時期 | {{ recommended_timing }} |
| 想定売却期間 | {{ expected_duration }} |
| 手取り予想額 | {{ estimated_net_proceeds }} |

---

## 2. 物件概要・評価

### 2.1 基本情報

| 項目 | 詳細 |
|------|------|
| 物件名 | {{ property_name }} |
| 所在地 | {{ property_address }} |
| 最寄駅 | {{ nearest_station }} (徒歩 {{ walk_minutes }}分) |
| 構造 | {{ building_structure }} |
| 築年数 | {{ building_age }}年 ({{ construction_year }}年築) |
| 延床面積 | {{ total_floor_area }} m2 |
| 土地面積 | {{ land_area }} m2 |
| 間取り / 戸数 | {{ layout_or_units }} |
| 現行賃料収入 | {{ current_rental_income }} |
| 現行利回り | {{ current_yield }} |
| 取得価格 | {{ acquisition_price }} |
| 取得年月 | {{ acquisition_date }} |

### 2.2 物件の強み

{{ property_strengths }}

### 2.3 物件の課題

{{ property_weaknesses }}

### 2.4 遵法性・権利関係

{{ legal_compliance }}

---

## 3. 市場環境分析

### 3.1 マクロ経済環境

{{ macro_economic_analysis }}

### 3.2 不動産市場動向

{{ real_estate_market_trend }}

### 3.3 エリア市場分析

{{ area_market_analysis }}

### 3.4 類似物件取引事例

| 物件 | 所在地 | 面積 | 成約価格 | 利回り | 成約日 |
|------|--------|------|---------|:------:|--------|
{% for case in transaction_cases %}| {{ case.name }} | {{ case.address }} | {{ case.area }} | {{ case.price }} | {{ case.yield }} | {{ case.date }} |
{% endfor %}

---

## 4. 売却価格査定

### 4.1 査定手法別結果

| 査定手法 | 査定価格 | 備考 |
|---------|----------|------|
| 取引事例比較法 | {{ comp_valuation }} | {{ comp_note }} |
| 収益還元法 (直接還元) | {{ direct_cap_valuation }} | {{ direct_cap_note }} |
| 収益還元法 (DCF) | {{ dcf_valuation }} | {{ dcf_note }} |
| 原価法 | {{ cost_valuation }} | {{ cost_note }} |
| **総合査定価格** | **{{ total_valuation }}** | {{ valuation_note }} |

### 4.2 価格レンジ分析

{{ price_range_analysis }}

| 価格帯 | 金額 | 成約確率 | 想定期間 |
|--------|------|:--------:|---------|
| 上限価格 | {{ upper_price }} | {{ upper_probability }} | {{ upper_duration }} |
| 推奨価格 | {{ recommended_price }} | {{ recommended_probability }} | {{ recommended_duration }} |
| 下限価格 | {{ lower_price }} | {{ lower_probability }} | {{ lower_duration }} |

### 4.3 収益分析

{{ yield_analysis }}

---

## 5. ターゲットバイヤー分析

### 5.1 想定バイヤープロファイル

{% for buyer in target_buyers %}
#### {{ buyer.type }}

- **属性**: {{ buyer.profile }}
- **購入動機**: {{ buyer.motivation }}
- **予算感**: {{ buyer.budget_range }}
- **重視ポイント**: {{ buyer.priorities }}
- **アプローチ方法**: {{ buyer.approach }}

{% endfor %}

### 5.2 バイヤー候補リスト

{{ buyer_candidates }}

---

## 6. 売却戦略立案

### 6.1 推奨売却戦略

{{ recommended_strategy }}

### 6.2 戦略オプション比較

| 戦略 | 概要 | メリット | デメリット |
|------|------|---------|-----------|
| {{ strategy_a_name }} | {{ strategy_a_overview }} | {{ strategy_a_merit }} | {{ strategy_a_demerit }} |
| {{ strategy_b_name }} | {{ strategy_b_overview }} | {{ strategy_b_merit }} | {{ strategy_b_demerit }} |
| {{ strategy_c_name }} | {{ strategy_c_overview }} | {{ strategy_c_merit }} | {{ strategy_c_demerit }} |

### 6.3 価格戦略

{{ pricing_strategy }}

### 6.4 売却前改善提案

{{ pre_sale_improvements }}

---

## 7. マーケティング計画

### 7.1 販売チャネル

{{ marketing_channels }}

| チャネル | 施策 | 予算 | 期待効果 |
|---------|------|------|---------|
{% for channel in marketing_plan %}| {{ channel.name }} | {{ channel.measures }} | {{ channel.budget }} | {{ channel.expected_effect }} |
{% endfor %}

### 7.2 販売資料・ツール

{{ sales_materials }}

### 7.3 内覧対策

{{ showing_strategy }}

---

## 8. 売却スケジュール

### 8.1 全体タイムライン

| フェーズ | 期間 | 主要アクション |
|---------|------|--------------|
| 準備期間 | {{ prep_phase_period }} | {{ prep_phase_actions }} |
| 販売活動開始 | {{ sales_phase_period }} | {{ sales_phase_actions }} |
| 交渉・条件調整 | {{ negotiation_phase_period }} | {{ negotiation_phase_actions }} |
| 契約・決済 | {{ closing_phase_period }} | {{ closing_phase_actions }} |
| 引渡し | {{ handover_phase_period }} | {{ handover_phase_actions }} |

### 8.2 価格見直しタイミング

{{ price_revision_plan }}

---

## 9. 税務・法務アドバイス

### 9.1 譲渡所得税シミュレーション

| 項目 | 金額 |
|------|------|
| 売却想定価格 | {{ selling_price }} |
| 取得費 | {{ acquisition_cost }} |
| 譲渡費用 | {{ transfer_expenses }} |
| 譲渡所得 | {{ capital_gain }} |
| 所得税・住民税 | {{ tax_amount }} |
| **手取り予想額** | **{{ net_proceeds }}** |

### 9.2 節税対策

{{ tax_saving_strategies }}

### 9.3 法的留意事項

{{ legal_considerations }}

### 9.4 必要書類一覧

{{ required_documents }}

---

## 10. プロフェッショナル所見

{{ professional_insight }}

### 最終推奨事項

{{ final_recommendations }}

### 想定タイムライン

{{ recommended_timeline }}

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
