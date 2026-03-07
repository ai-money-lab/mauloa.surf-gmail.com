<div class="cover-page">

# 週刊不動産マーケットニュース

## {{ week_label | default("YYYY年 第XX週") }}

<p class="author">{{ header }}<br>編集: {{ author }}</p>
<p class="date">{{ date }}</p>

</div>

---

## 今週のハイライト

{{ highlights | default("（今週の重要ニュース3選）") }}

## 金利・経済動向

{{ interest_rate_update | default("（金利動向）") }}

## 市場トレンド

{{ market_trends | default("（市場動向）") }}

## 法規制・政策

{{ regulation_updates | default("（法改正・補助金情報）") }}

## 注目の再開発

{{ redevelopment_news | default("（再開発ニュース）") }}

## PropTech最前線

{{ proptech_updates | default("（不動産テック動向）") }}

## HIROKI's Eye

<div class="insight-box">

{{ hiroki_commentary | default("（HIROKIの一言コメント）") }}

</div>

---

<small>
{{ header }} | {{ date }} 発行
本ニュースレターの内容は情報提供を目的としたものであり、投資助言ではありません。
</small>
