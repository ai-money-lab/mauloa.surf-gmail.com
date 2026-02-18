# 問い合わせ自動対応Bot — 納品レポート

**クライアント:** {{ client_name }}
**業種:** {{ industry }}
**納品日:** {{ delivery_date }}
**プラン:** {{ plan_name }}

---

## 1. システム概要

### 構築内容
{{ client_name }}様向けに、以下の問い合わせ自動対応システムを構築・納品いたしました。

| 項目 | 内容 |
|------|------|
| AIエンジン | Claude AI (Anthropic) |
| 対応チャネル | {{ channels }} |
| FAQナレッジベース | {{ faq_count }}問 |
| 対応カテゴリ | {{ category_count }}カテゴリ |
| エスカレーション | {{ escalation_config }} |

### アーキテクチャ
```
お客様 → LINE / Webチャット
         ↓
     AIエンジン（Claude API）
         ↓
    ナレッジベース検索
         ↓
   応答生成 → 返信
         ↓
   Google Sheets記録 + エスカレーション通知
```

---

## 2. FAQナレッジベース

### カテゴリ一覧

{% for category in categories %}
#### {{ category.name }}（{{ category.faq_count }}問）
- 自動応答率: {{ category.auto_rate }}%
- 優先度: {{ category.priority }}

{% endfor %}

### FAQ一覧（抜粋）

{% for faq in faq_samples %}
**Q: {{ faq.question }}**
A: {{ faq.answer }}

{% endfor %}

---

## 3. LINE連携設定

{% if line_enabled %}
| 設定項目 | 状態 |
|----------|------|
| LINE公式アカウント | {{ line_account_name }} |
| Webhook URL | {{ line_webhook_url }} |
| 署名検証 | 有効 |
| クイックリプライ | {{ quick_reply_status }} |
| リッチメニュー | {{ rich_menu_status }} |
{% else %}
※ LINE連携は本プランに含まれません。
{% endif %}

---

## 4. Webチャットウィジェット

{% if web_chat_enabled %}
### 埋め込みコード

以下のコードをWebサイトの `</body>` タグの直前に貼り付けてください。

```html
<script src="{{ widget_url }}/widget/embed.js"
        data-api="{{ api_url }}"
        data-position="bottom-right"
        data-color="{{ primary_color }}"
        data-accent="{{ accent_color }}">
</script>
```

### カスタマイズ項目
| 項目 | 設定値 |
|------|--------|
| タイトル | {{ widget_title }} |
| プライマリカラー | {{ primary_color }} |
| アクセントカラー | {{ accent_color }} |
| 表示位置 | {{ widget_position }} |
{% else %}
※ Webチャットは本プランに含まれません。
{% endif %}

---

## 5. エスカレーション設定

### トリガー条件
{% for trigger in escalation_triggers %}
- {{ trigger }}
{% endfor %}

### 通知先
{% for channel in notify_channels %}
- {{ channel }}
{% endfor %}

---

## 6. n8nワークフロー

{% if n8n_enabled %}
### 自動化フロー
1. **問い合わせ受信** → AI応答生成 → チャネル返信
2. **全問い合わせ** → Google Sheets自動記録
3. **エスカレーション発生** → LINE Notify / Slack通知
4. **毎日21:00** → 日次レポート自動送信

### n8nワークフローインポート
`inquiry_bot/n8n_workflow.json` をn8nにインポートしてご利用ください。
{% endif %}

---

## 7. 運用ガイド

### FAQ追加方法
1. `inquiry_bot/faq_data.yaml` をテキストエディタで開く
2. 以下の形式でFAQを追加:
```yaml
- id: "新しいID"
  category: "カテゴリ名"
  patterns:
    - "質問パターン1"
    - "質問パターン2"
  answer: >
    回答テキスト
  requires_data: []
```
3. サーバーを再起動

### サーバー起動方法
```bash
uvicorn inquiry_bot.server:app --host 0.0.0.0 --port 8080
```

### ログ確認
- Google Sheets「inquiry_log」シートで全問い合わせを確認可能
- `/api/analytics` エンドポイントで統計データを取得可能

---

## 8. ランニングコスト目安

| 項目 | 月額費用（税別） |
|------|-----------------|
| Claude AI API | 3,000〜10,000円（問い合わせ量による） |
| LINE公式アカウント | 0〜15,000円（メッセージ数による） |
| サーバー費用 | 1,000〜3,000円 |
| **合計目安** | **4,000〜28,000円/月** |

---

## 9. サポート

{% if premium_support %}
### プレミアムサポート（3ヶ月間）
- 月1回のFAQ追加・チューニング
- 応答精度の定期レビュー
- メール/チャットでのお問い合わせ対応
{% endif %}

### お問い合わせ
- メール: info@rockedge.jp
- LINE: @rockedge

---

*ROCKEDGE Property Management*
*Powered by Claude AI*
