---
title: "{{ report_title }}"
date: "{{ date }}"
client: "{{ client_name }}"
type: "special_cleaning"
---

<!-- ============================================================ -->
<!--  ROCKEDGE Property Management | HIROKI                       -->
<!--  特殊清掃・遺品整理コーディネート提案書                            -->
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
2. [現地調査・状況報告](#2-現地調査状況報告)
3. [作業区分と対応範囲](#3-作業区分と対応範囲)
4. [特殊清掃計画](#4-特殊清掃計画)
5. [遺品整理・残置物撤去計画](#5-遺品整理残置物撤去計画)
6. [原状回復・リフォーム提案](#6-原状回復リフォーム提案)
7. [費用見積比較](#7-費用見積比較)
8. [スケジュール](#8-スケジュール)
9. [法的対応・保険手続き](#9-法的対応保険手続き)
10. [プロフェッショナル所見](#10-プロフェッショナル所見)

---

## 1. エグゼクティブサマリー

{{ executive_summary }}

### 対応概要

| 項目 | 内容 |
|------|------|
| 案件種別 | {{ case_type }} |
| 対応緊急度 | {{ urgency_level }} |
| 推奨対応プラン | {{ recommended_plan }} |
| 概算総額 | **{{ total_estimated_cost }}** |
| 想定工期 | {{ estimated_duration }} |
| 再貸出可能時期 | {{ re_rental_target_date }} |

---

## 2. 現地調査・状況報告

### 2.1 物件基本情報

| 項目 | 詳細 |
|------|------|
| 物件名 | {{ property_name }} |
| 所在地 | {{ property_address }} |
| 部屋番号 | {{ room_number }} |
| 間取り | {{ layout }} |
| 専有面積 | {{ floor_area }} m2 |
| 階数 | {{ floor_level }}階 |
| 構造 | {{ building_structure }} |

### 2.2 現場状況

{{ site_condition_report }}

### 2.3 状態評価

| 評価項目 | レベル (1-5) | 詳細 |
|---------|:-----------:|------|
| 汚損度 | {{ contamination_level }} | {{ contamination_detail }} |
| 臭気レベル | {{ odor_level }} | {{ odor_detail }} |
| 害虫発生状況 | {{ pest_level }} | {{ pest_detail }} |
| 残置物量 | {{ debris_level }} | {{ debris_detail }} |
| 構造躯体への影響 | {{ structural_level }} | {{ structural_detail }} |

### 2.4 周辺住民への影響

{{ neighbor_impact }}

---

## 3. 作業区分と対応範囲

### 3.1 対応作業一覧

| 作業区分 | 必要有無 | 優先度 | 備考 |
|---------|:-------:|:------:|------|
| 特殊清掃 | {{ need_special_cleaning }} | {{ priority_special_cleaning }} | {{ note_special_cleaning }} |
| 消臭・脱臭処理 | {{ need_deodorizing }} | {{ priority_deodorizing }} | {{ note_deodorizing }} |
| 害虫駆除 | {{ need_pest_control }} | {{ priority_pest_control }} | {{ note_pest_control }} |
| 遺品整理 | {{ need_estate_clearing }} | {{ priority_estate_clearing }} | {{ note_estate_clearing }} |
| 残置物撤去 | {{ need_debris_removal }} | {{ priority_debris_removal }} | {{ note_debris_removal }} |
| 原状回復工事 | {{ need_restoration }} | {{ priority_restoration }} | {{ note_restoration }} |
| リフォーム | {{ need_renovation }} | {{ priority_renovation }} | {{ note_renovation }} |

### 3.2 必要資格・許認可

{{ required_licenses }}

---

## 4. 特殊清掃計画

### 4.1 清掃工程

{{ cleaning_process }}

| 工程 | 内容 | 所要時間 |
|------|------|---------|
{% for step in cleaning_steps %}| {{ step.phase }} | {{ step.description }} | {{ step.duration }} |
{% endfor %}

### 4.2 使用薬剤・機材

{{ cleaning_materials }}

### 4.3 消臭・脱臭処理

{{ deodorizing_plan }}

| 処理方法 | 適用箇所 | 効果持続 |
|---------|---------|---------|
{% for method in deodorizing_methods %}| {{ method.name }} | {{ method.area }} | {{ method.duration }} |
{% endfor %}

### 4.4 安全対策

{{ safety_measures }}

---

## 5. 遺品整理・残置物撤去計画

### 5.1 遺品整理方針

{{ estate_clearing_policy }}

### 5.2 仕分け基準

| カテゴリ | 処理方針 | 推定量 |
|---------|---------|--------|
| 貴重品・重要書類 | {{ valuables_handling }} | {{ valuables_volume }} |
| 形見分け品 | {{ keepsakes_handling }} | {{ keepsakes_volume }} |
| リサイクル可能品 | {{ recyclables_handling }} | {{ recyclables_volume }} |
| 一般廃棄物 | {{ general_waste_handling }} | {{ general_waste_volume }} |
| 産業廃棄物 | {{ industrial_waste_handling }} | {{ industrial_waste_volume }} |

### 5.3 搬出計画

{{ removal_plan }}

### 5.4 廃棄物処理

{{ waste_disposal_plan }}

---

## 6. 原状回復・リフォーム提案

### 6.1 原状回復必要箇所

| 箇所 | 状態 | 対応内容 | 概算費用 |
|------|------|---------|---------|
{% for item in restoration_items %}| {{ item.location }} | {{ item.condition }} | {{ item.action }} | {{ item.cost }} |
{% endfor %}

### 6.2 推奨リフォーム

{{ renovation_recommendations }}

### 6.3 告知義務対応

{{ disclosure_obligation }}

### 6.4 再貸出に向けた提案

{{ re_rental_strategy }}

---

## 7. 費用見積比較

### 7.1 業者A: {{ contractor_a_name }}

| 作業項目 | 金額 |
|---------|------|
{% for item in contractor_a_items %}| {{ item.description }} | {{ item.amount }} |
{% endfor %}
| **合計 (税込)** | **{{ contractor_a_total }}** |

### 7.2 業者B: {{ contractor_b_name }}

| 作業項目 | 金額 |
|---------|------|
{% for item in contractor_b_items %}| {{ item.description }} | {{ item.amount }} |
{% endfor %}
| **合計 (税込)** | **{{ contractor_b_total }}** |

### 7.3 業者C: {{ contractor_c_name }}

| 作業項目 | 金額 |
|---------|------|
{% for item in contractor_c_items %}| {{ item.description }} | {{ item.amount }} |
{% endfor %}
| **合計 (税込)** | **{{ contractor_c_total }}** |

### 7.4 業者比較サマリー

| 比較項目 | 業者A | 業者B | 業者C |
|---------|-------|-------|-------|
| 見積金額 | {{ contractor_a_total }} | {{ contractor_b_total }} | {{ contractor_c_total }} |
| 対応速度 | {{ contractor_a_speed }} | {{ contractor_b_speed }} | {{ contractor_c_speed }} |
| 実績・信頼性 | {{ contractor_a_reliability }} | {{ contractor_b_reliability }} | {{ contractor_c_reliability }} |
| 保証内容 | {{ contractor_a_warranty }} | {{ contractor_b_warranty }} | {{ contractor_c_warranty }} |
| **総合評価** | **{{ contractor_a_rating }}** | **{{ contractor_b_rating }}** | **{{ contractor_c_rating }}** |

### 7.5 推奨業者

{{ recommended_contractor }}

---

## 8. スケジュール

### 8.1 全体スケジュール

| フェーズ | 期間 | 作業内容 |
|---------|------|---------|
| 事前準備 | {{ prep_period }} | {{ prep_tasks }} |
| 特殊清掃 | {{ cleaning_period }} | {{ cleaning_tasks }} |
| 遺品整理・撤去 | {{ clearing_period }} | {{ clearing_tasks }} |
| 消臭・除菌処理 | {{ deodorizing_period }} | {{ deodorizing_tasks }} |
| 原状回復工事 | {{ restoration_period }} | {{ restoration_tasks }} |
| 最終確認・引渡し | {{ final_check_period }} | {{ final_check_tasks }} |
| 募集開始 | {{ listing_start }} | {{ listing_tasks }} |

### 8.2 近隣対応スケジュール

{{ neighbor_communication_plan }}

---

## 9. 法的対応・保険手続き

### 9.1 法的対応事項

{{ legal_matters }}

### 9.2 保険適用範囲

{{ insurance_coverage }}

| 保険種別 | 適用可否 | 補償範囲 | 申請期限 |
|---------|:-------:|---------|---------|
{% for ins in insurance_items %}| {{ ins.type }} | {{ ins.applicable }} | {{ ins.coverage }} | {{ ins.deadline }} |
{% endfor %}

### 9.3 連帯保証人・相続人対応

{{ guarantor_heir_handling }}

### 9.4 必要書類

{{ required_documents }}

---

## 10. プロフェッショナル所見

{{ professional_insight }}

### 対応上の重要事項

{{ important_considerations }}

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
