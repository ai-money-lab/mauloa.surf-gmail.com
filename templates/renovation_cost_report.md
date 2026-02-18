---
title: "{{ report_title }}"
date: "{{ date }}"
client: "{{ client_name }}"
type: "renovation_cost"
---

<!-- ============================================================ -->
<!--  ROCKEDGE Property Management | HIROKI                       -->
<!--  リノベーション費用比較レポート                                   -->
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
2. [物件現況調査](#2-物件現況調査)
3. [リノベーションプラン比較](#3-リノベーションプラン比較)
4. [工事項目別費用明細](#4-工事項目別費用明細)
5. [施工業者比較](#5-施工業者比較)
6. [スケジュール計画](#6-スケジュール計画)
7. [投資対効果分析](#7-投資対効果分析)
8. [補助金・減税制度](#8-補助金減税制度)
9. [リスクと注意事項](#9-リスクと注意事項)
10. [プロフェッショナル所見](#10-プロフェッショナル所見)

---

## 1. エグゼクティブサマリー

{{ executive_summary }}

### 推奨プラン概要

| 項目 | 内容 |
|------|------|
| 推奨プラン | {{ recommended_plan_name }} |
| 概算総額 | **{{ recommended_plan_cost }}** |
| 工事期間 | {{ recommended_plan_duration }} |
| 期待賃料アップ | {{ expected_rent_increase }} |
| 投資回収期間 | {{ payback_period }} |

---

## 2. 物件現況調査

### 2.1 物件基本情報

| 項目 | 詳細 |
|------|------|
| 物件名 | {{ property_name }} |
| 所在地 | {{ property_address }} |
| 構造 | {{ building_structure }} |
| 築年数 | {{ building_age }}年 |
| 専有面積 | {{ floor_area }} m2 |
| 間取り | {{ current_layout }} |
| 現状賃料 | {{ current_rent }} |

### 2.2 現況写真・調査結果

{{ current_condition_survey }}

### 2.3 劣化・損傷箇所一覧

| 箇所 | 状態 | 緊急度 | 対応内容 |
|------|------|:------:|---------|
{% for damage in damage_list %}| {{ damage.location }} | {{ damage.condition }} | {{ damage.urgency }} | {{ damage.action }} |
{% endfor %}

### 2.4 設備状況

{{ equipment_condition }}

---

## 3. リノベーションプラン比較

### 3.1 プランA: {{ plan_a_name }}

{{ plan_a_description }}

| 項目 | 内容 |
|------|------|
| コンセプト | {{ plan_a_concept }} |
| 概算費用 | {{ plan_a_cost }} |
| 工事期間 | {{ plan_a_duration }} |
| 期待賃料 | {{ plan_a_expected_rent }} |
| ターゲット入居者 | {{ plan_a_target_tenant }} |

### 3.2 プランB: {{ plan_b_name }}

{{ plan_b_description }}

| 項目 | 内容 |
|------|------|
| コンセプト | {{ plan_b_concept }} |
| 概算費用 | {{ plan_b_cost }} |
| 工事期間 | {{ plan_b_duration }} |
| 期待賃料 | {{ plan_b_expected_rent }} |
| ターゲット入居者 | {{ plan_b_target_tenant }} |

### 3.3 プランC: {{ plan_c_name }}

{{ plan_c_description }}

| 項目 | 内容 |
|------|------|
| コンセプト | {{ plan_c_concept }} |
| 概算費用 | {{ plan_c_cost }} |
| 工事期間 | {{ plan_c_duration }} |
| 期待賃料 | {{ plan_c_expected_rent }} |
| ターゲット入居者 | {{ plan_c_target_tenant }} |

### 3.4 プラン比較総括

| 比較項目 | プランA | プランB | プランC |
|---------|---------|---------|---------|
| 総費用 | {{ plan_a_cost }} | {{ plan_b_cost }} | {{ plan_c_cost }} |
| 工事期間 | {{ plan_a_duration }} | {{ plan_b_duration }} | {{ plan_c_duration }} |
| 期待賃料アップ | {{ plan_a_rent_up }} | {{ plan_b_rent_up }} | {{ plan_c_rent_up }} |
| 投資回収期間 | {{ plan_a_payback }} | {{ plan_b_payback }} | {{ plan_c_payback }} |
| ROI (5年) | {{ plan_a_roi }} | {{ plan_b_roi }} | {{ plan_c_roi }} |

---

## 4. 工事項目別費用明細

### 4.1 推奨プラン費用明細

| 工事区分 | 工事内容 | 数量 | 単価 | 金額 |
|---------|---------|------|------|------|
{% for item in cost_breakdown %}| {{ item.category }} | {{ item.description }} | {{ item.quantity }} | {{ item.unit_price }} | {{ item.amount }} |
{% endfor %}
| | | | **小計** | **{{ subtotal }}** |
| | | | 諸経費 ({{ overhead_rate }}) | {{ overhead_cost }} |
| | | | 消費税 | {{ tax_amount }} |
| | | | **総合計** | **{{ grand_total }}** |

### 4.2 オプション工事

{% for opt in optional_works %}
- **{{ opt.name }}**: {{ opt.description }} ({{ opt.cost }})
{% endfor %}

---

## 5. 施工業者比較

### 5.1 候補業者一覧

{% for contractor in contractors %}
#### {{ contractor.name }}

| 項目 | 評価 |
|------|------|
| 見積金額 | {{ contractor.quote_amount }} |
| 工事期間 | {{ contractor.duration }} |
| 不動産リノベ実績 | {{ contractor.experience }} |
| 保証内容 | {{ contractor.warranty }} |
| アフターサービス | {{ contractor.after_service }} |
| 総合評価 | {{ contractor.rating }} |

{% endfor %}

### 5.2 推奨業者

{{ recommended_contractor }}

---

## 6. スケジュール計画

### 6.1 全体スケジュール

{{ overall_schedule }}

| フェーズ | 期間 | 内容 |
|---------|------|------|
| 設計・プランニング | {{ design_period }} | {{ design_tasks }} |
| 見積・契約 | {{ quote_period }} | {{ quote_tasks }} |
| 着工準備 | {{ prep_period }} | {{ prep_tasks }} |
| 工事施工 | {{ construction_period }} | {{ construction_tasks }} |
| 検査・引渡し | {{ inspection_period }} | {{ inspection_tasks }} |
| 入居募集開始 | {{ listing_start }} | {{ listing_tasks }} |

### 6.2 工事中の入居者対応

{{ tenant_during_construction }}

---

## 7. 投資対効果分析

### 7.1 賃料アップ効果

{{ rent_increase_analysis }}

### 7.2 資産価値向上効果

{{ asset_value_improvement }}

### 7.3 5年間収支シミュレーション

| 年度 | 賃料収入 | 管理費用 | ローン返済 | 手取り収入 | 累計収支 |
|------|----------|---------|-----------|-----------|---------|
{% for year in five_year_projection %}| {{ year.year }} | {{ year.rent_income }} | {{ year.management_cost }} | {{ year.loan_payment }} | {{ year.net_income }} | {{ year.cumulative }} |
{% endfor %}

### 7.4 リノベ前後比較

| 項目 | リノベ前 | リノベ後 |
|------|---------|---------|
| 賃料 | {{ before_rent }} | {{ after_rent }} |
| 空室率 | {{ before_vacancy }} | {{ after_vacancy }} |
| 年間収入 | {{ before_annual_income }} | {{ after_annual_income }} |
| 表面利回り | {{ before_yield }} | {{ after_yield }} |

---

## 8. 補助金・減税制度

### 8.1 活用可能な補助金

{% for subsidy in subsidies %}
#### {{ subsidy.name }}

- **概要**: {{ subsidy.description }}
- **補助額**: {{ subsidy.amount }}
- **申請期限**: {{ subsidy.deadline }}
- **要件**: {{ subsidy.requirements }}

{% endfor %}

### 8.2 税制優遇

{{ tax_benefits }}

---

## 9. リスクと注意事項

### 9.1 工事リスク

{{ construction_risks }}

### 9.2 追加費用発生リスク

{{ additional_cost_risks }}

### 9.3 法的注意事項

{{ legal_considerations }}

---

## 10. プロフェッショナル所見

{{ professional_insight }}

### 最終推奨事項

{{ final_recommendations }}

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
