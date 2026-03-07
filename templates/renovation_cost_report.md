<div class="cover-page">

# リフォーム費用比較レポート

## {{ project_name | default("リフォームプロジェクト") }}

<p class="author">{{ header }}<br>作成者: {{ author }}</p>
<p class="date">{{ date }}</p>

</div>

---

## 目次

1. 費用サマリー
2. 工事概要
3. 費用内訳
4. プラン比較
5. コストダウンのポイント
6. 工期・スケジュール
7. プロフェッショナル所見

---

## 1. 費用サマリー

| プラン | 費用レンジ | 工期 |
|--------|----------|------|
| スタンダード | {{ standard_cost | default("¥---万〜¥---万") }} | {{ standard_duration | default("---週間") }} |
| グレードアップ | {{ upgrade_cost | default("¥---万〜¥---万") }} | {{ upgrade_duration | default("---週間") }} |
| プレミアム | {{ premium_cost | default("¥---万〜¥---万") }} | {{ premium_duration | default("---週間") }} |

## 2. 工事概要

{{ project_overview | default("（工事概要）") }}

## 3. 費用内訳

{{ cost_breakdown | default("（費用内訳テーブル）") }}

## 4. プラン比較

{{ plan_comparison | default("（プラン比較詳細）") }}

## 5. コストダウンのポイント

{{ cost_reduction_tips | default("（コスト削減アドバイス）") }}

## 6. 工期・スケジュール

{{ schedule | default("（工程表）") }}

## 7. プロフェッショナル所見

<div class="insight-box">

{{ professional_insight | default("（HIROKI所見）") }}

</div>

---

<small>{{ header }} | {{ date }} 作成 | CONFIDENTIAL</small>
