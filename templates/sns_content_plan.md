# SNS投稿コンテンツプラン

**クライアント:** {{ client_name | default("クライアント名") }}
**対象月:** {{ target_month | default("YYYY年MM月") }}
**作成者:** {{ header }}（{{ author }}）
**作成日:** {{ date }}

---

## 月間投稿カレンダー

{{ monthly_calendar | default("（月間カレンダー）") }}

## 投稿一覧

| # | 投稿日 | 曜日 | 時間 | 媒体 | フォーマット | カテゴリ | 投稿テーマ |
|---|--------|------|------|------|-----------|---------|----------|
{% for post in posts | default([]) %}
| {{ loop.index }} | {{ post.date }} | {{ post.day }} | {{ post.time }} | {{ post.platform }} | {{ post.format }} | {{ post.category }} | {{ post.content }} |
{% endfor %}

## カテゴリ別比率

{{ category_breakdown | default("（カテゴリ別の投稿比率）") }}

## 投稿ガイドライン

{{ posting_guidelines | default("（投稿時の注意事項）") }}

---

<small>{{ header }} | {{ date }} 作成</small>
