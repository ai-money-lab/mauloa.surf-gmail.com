---
title: "{{ report_title }}"
date: "{{ date }}"
client: "{{ client_name }}"
type: "sns_content_plan"
---

<!-- ============================================================ -->
<!--  ROCKEDGE Property Management | HIROKI                       -->
<!--  不動産会社向けSNSコンテンツプラン                                -->
<!-- ============================================================ -->

# {{ report_title }}

**ROCKEDGE Property Management**
**担当: HIROKI**

| 項目 | 内容 |
|------|------|
| レポート作成日 | {{ date }} |
| クライアント | {{ client_name }} |
| 対象期間 | {{ plan_period }} |
| 対象SNSプラットフォーム | {{ target_platforms }} |
| レポートID | {{ report_id }} |

---

## 目次

1. [エグゼクティブサマリー](#1-エグゼクティブサマリー)
2. [現状分析・アカウント診断](#2-現状分析アカウント診断)
3. [ターゲットペルソナ設定](#3-ターゲットペルソナ設定)
4. [コンテンツ戦略](#4-コンテンツ戦略)
5. [プラットフォーム別計画](#5-プラットフォーム別計画)
6. [月間コンテンツカレンダー](#6-月間コンテンツカレンダー)
7. [コンテンツ制作ガイドライン](#7-コンテンツ制作ガイドライン)
8. [KPI・効果測定計画](#8-kpi効果測定計画)
9. [運用体制・予算](#9-運用体制予算)
10. [プロフェッショナル所見](#10-プロフェッショナル所見)

---

## 1. エグゼクティブサマリー

{{ executive_summary }}

### SNS戦略ハイライト

| 項目 | 内容 |
|------|------|
| 主要目的 | {{ primary_objective }} |
| ターゲット層 | {{ target_audience }} |
| 重点プラットフォーム | {{ primary_platform }} |
| 月間投稿目標 | {{ monthly_post_target }} |
| 目標フォロワー増加数 | {{ follower_growth_target }} |

---

## 2. 現状分析・アカウント診断

### 2.1 現在のSNSアカウント状況

| プラットフォーム | フォロワー数 | エンゲージメント率 | 投稿頻度 | 評価 |
|---------------|:-----------:|:-----------------:|:--------:|:----:|
{% for account in current_accounts %}| {{ account.platform }} | {{ account.followers }} | {{ account.engagement_rate }} | {{ account.post_frequency }} | {{ account.rating }} |
{% endfor %}

### 2.2 コンテンツ分析

{{ content_analysis }}

### 2.3 競合アカウント分析

{% for comp in competitor_accounts %}
#### {{ comp.name }} ({{ comp.platform }})

| 項目 | データ |
|------|--------|
| フォロワー数 | {{ comp.followers }} |
| エンゲージメント率 | {{ comp.engagement_rate }} |
| 投稿頻度 | {{ comp.post_frequency }} |
| 主要コンテンツ | {{ comp.main_content }} |
| 強み | {{ comp.strengths }} |

{% endfor %}

### 2.4 業界トレンド

{{ industry_trends }}

---

## 3. ターゲットペルソナ設定

{% for persona in target_personas %}
### 3.{{ loop.index }} ペルソナ{{ loop.index }}: {{ persona.name }}

| 項目 | 詳細 |
|------|------|
| 年齢層 | {{ persona.age_range }} |
| 性別 | {{ persona.gender }} |
| 職業 | {{ persona.occupation }} |
| 年収帯 | {{ persona.income_range }} |
| 居住エリア | {{ persona.location }} |
| 家族構成 | {{ persona.family }} |
| SNS利用傾向 | {{ persona.sns_behavior }} |
| 不動産ニーズ | {{ persona.real_estate_needs }} |
| 情報収集方法 | {{ persona.info_gathering }} |
| 響くコンテンツ | {{ persona.preferred_content }} |

{% endfor %}

---

## 4. コンテンツ戦略

### 4.1 コンテンツピラー (柱)

{% for pillar in content_pillars %}
#### {{ pillar.name }}

- **目的**: {{ pillar.purpose }}
- **コンテンツ例**: {{ pillar.examples }}
- **配分比率**: {{ pillar.ratio }}
- **期待効果**: {{ pillar.expected_effect }}

{% endfor %}

### 4.2 コンテンツミックス

| コンテンツ種別 | 配分 | 目的 |
|-------------|:----:|------|
| 教育・情報提供 | {{ mix_educational }} | {{ purpose_educational }} |
| 物件紹介 | {{ mix_property }} | {{ purpose_property }} |
| お客様の声・事例 | {{ mix_testimonial }} | {{ purpose_testimonial }} |
| 会社・スタッフ紹介 | {{ mix_company }} | {{ purpose_company }} |
| エリア情報 | {{ mix_area }} | {{ purpose_area }} |
| キャンペーン・告知 | {{ mix_campaign }} | {{ purpose_campaign }} |

### 4.3 ブランドボイス・トーン

{{ brand_voice }}

---

## 5. プラットフォーム別計画

### 5.1 Instagram

{{ instagram_strategy }}

| 項目 | 計画 |
|------|------|
| 投稿頻度 | {{ ig_post_frequency }} |
| ストーリーズ頻度 | {{ ig_story_frequency }} |
| リール頻度 | {{ ig_reel_frequency }} |
| 主要ハッシュタグ | {{ ig_hashtags }} |
| 最適投稿時間 | {{ ig_best_time }} |

### 5.2 X (Twitter)

{{ twitter_strategy }}

| 項目 | 計画 |
|------|------|
| 投稿頻度 | {{ tw_post_frequency }} |
| リプライ方針 | {{ tw_reply_policy }} |
| 引用RT方針 | {{ tw_retweet_policy }} |
| 主要ハッシュタグ | {{ tw_hashtags }} |
| 最適投稿時間 | {{ tw_best_time }} |

### 5.3 YouTube / TikTok

{{ video_strategy }}

| 項目 | 計画 |
|------|------|
| 動画投稿頻度 | {{ video_frequency }} |
| ショート動画頻度 | {{ short_video_frequency }} |
| 動画テーマ | {{ video_themes }} |
| 目標再生回数 | {{ view_target }} |

### 5.4 LINE公式アカウント

{{ line_strategy }}

| 項目 | 計画 |
|------|------|
| 配信頻度 | {{ line_frequency }} |
| リッチメニュー | {{ line_rich_menu }} |
| 自動応答 | {{ line_auto_reply }} |
| セグメント配信 | {{ line_segmentation }} |

---

## 6. 月間コンテンツカレンダー

### 6.1 {{ calendar_month }} コンテンツカレンダー

| 週 | 月 | 火 | 水 | 木 | 金 | 土 | 日 |
|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
{% for week in calendar_weeks %}| {{ week.week_num }} | {{ week.mon }} | {{ week.tue }} | {{ week.wed }} | {{ week.thu }} | {{ week.fri }} | {{ week.sat }} | {{ week.sun }} |
{% endfor %}

### 6.2 季節イベント・テーマ

{{ seasonal_themes }}

### 6.3 投稿テーマ詳細

{% for post in planned_posts %}
#### {{ post.title }}

| 項目 | 内容 |
|------|------|
| 投稿日 | {{ post.date }} |
| プラットフォーム | {{ post.platform }} |
| コンテンツ種別 | {{ post.type }} |
| 投稿文案 | {{ post.caption }} |
| ビジュアル指示 | {{ post.visual_direction }} |
| ハッシュタグ | {{ post.hashtags }} |
| CTA | {{ post.cta }} |

{% endfor %}

---

## 7. コンテンツ制作ガイドライン

### 7.1 ビジュアルガイドライン

{{ visual_guidelines }}

### 7.2 写真撮影ガイド

{{ photography_guide }}

### 7.3 動画制作ガイド

{{ video_production_guide }}

### 7.4 文章スタイルガイド

{{ writing_style_guide }}

### 7.5 NG事項・コンプライアンス

{{ compliance_guidelines }}

---

## 8. KPI・効果測定計画

### 8.1 KPI設定

| KPI | 現状値 | 1ヶ月目標 | 3ヶ月目標 | 6ヶ月目標 |
|-----|--------|:--------:|:--------:|:--------:|
| フォロワー数 | {{ kpi_followers_current }} | {{ kpi_followers_1m }} | {{ kpi_followers_3m }} | {{ kpi_followers_6m }} |
| エンゲージメント率 | {{ kpi_engagement_current }} | {{ kpi_engagement_1m }} | {{ kpi_engagement_3m }} | {{ kpi_engagement_6m }} |
| リーチ数 | {{ kpi_reach_current }} | {{ kpi_reach_1m }} | {{ kpi_reach_3m }} | {{ kpi_reach_6m }} |
| Web誘導数 | {{ kpi_web_current }} | {{ kpi_web_1m }} | {{ kpi_web_3m }} | {{ kpi_web_6m }} |
| 問い合わせ数 | {{ kpi_inquiry_current }} | {{ kpi_inquiry_1m }} | {{ kpi_inquiry_3m }} | {{ kpi_inquiry_6m }} |

### 8.2 レポーティング体制

{{ reporting_structure }}

### 8.3 PDCA運用

{{ pdca_cycle }}

---

## 9. 運用体制・予算

### 9.1 運用体制

{{ operation_structure }}

### 9.2 月間予算

| 費目 | 金額 |
|------|------|
{% for item in monthly_budget_items %}| {{ item.description }} | {{ item.amount }} |
{% endfor %}
| **月額合計** | **{{ monthly_budget_total }}** |

### 9.3 推奨ツール

{{ recommended_tools }}

---

## 10. プロフェッショナル所見

{{ professional_insight }}

### SNS成功のための重要ポイント

{{ success_factors }}

### 注意事項

{{ cautions }}

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
