# n8n セットアップ手順

本ドキュメントでは、ワークフロー自動化ツール n8n のセットアップ手順を解説します。
本プロジェクトではcronによる直接実行を基本としますが、n8nを使えばワークフローの可視化・監視・エラーハンドリング・Webhook受信が容易になります。
特に System B（受注・納品管理）のWebhookによる案件受付や、問い合わせBotの連携に有用です。

---

## 1. n8n インストール

### 方法1: Docker（推奨）

Docker を使ったインストールが最も簡単で、環境汚染のリスクもありません。

```bash
# 基本的な起動
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

本番環境向け（docker-compose）：

```yaml
# docker-compose.yaml
version: '3.8'
services:
  n8n:
    image: n8nio/n8n
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=your_secure_password
      - N8N_HOST=your-domain.com
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - WEBHOOK_URL=https://your-domain.com/
      - GENERIC_TIMEZONE=Asia/Tokyo
      - TZ=Asia/Tokyo
    volumes:
      - n8n_data:/home/node/.n8n
    networks:
      - app_network

volumes:
  n8n_data:

networks:
  app_network:
```

```bash
# docker-compose で起動
docker-compose up -d
```

### 方法2: npm（グローバルインストール）

```bash
# Node.js 18+ が必要
node -v

# n8n をグローバルインストール
npm install n8n -g

# 起動
n8n start

# バックグラウンドで起動（PM2使用）
npm install pm2 -g
pm2 start n8n
pm2 save
pm2 startup
```

### インストール後の確認

ブラウザで `http://localhost:5678` にアクセスし、n8nのダッシュボードが表示されることを確認します。

---

## 2. 環境変数・認証情報の設定

n8n の「Credentials」機能で以下の認証情報を設定します。

### 2-1. n8n ダッシュボードから設定

1. `http://localhost:5678` にアクセス
2. 左メニュー → 「Credentials」→ 「+ Add Credential」

### 2-2. 設定する認証情報

| 認証情報名 | 種類 | 用途 |
|-----------|------|------|
| Anthropic API Key | Header Auth | Claude APIへのリクエスト |
| X API Keys | OAuth1 | X投稿の認証 |
| Google Sheets | OAuth2 / Service Account | スプレッドシート連携 |
| LINE Notify Token | Header Auth | LINE通知送信 |
| LINE Channel Access Token | Header Auth | LINE Messaging API |
| LINE Channel Secret | Generic | Webhook署名検証 |
| Slack Webhook | Slack API | エスカレーション通知 |

### 2-3. Webhook URL の設定

外部からn8nのWebhookにアクセスするため、以下のいずれかの方法でURLを公開します：

**開発環境（ngrokを使用）：**
```bash
# ngrokのインストール
npm install ngrok -g

# n8nのポートをトンネリング
ngrok http 5678
```

**本番環境（リバースプロキシ）：**
```nginx
# Nginx設定例
server {
    listen 443 ssl;
    server_name n8n.your-domain.com;

    location / {
        proxy_pass http://localhost:5678;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 3. ワークフロー構成

### Workflow A: X投稿パイプライン（毎日 06:00）

System Aの日次投稿パイプラインを自動実行するワークフローです。

```
[Schedule Trigger: 06:00 JST]
    → [Execute Command: python system_a/daily_pipeline.py]
    → [IF: 成功?]
        → 成功: [Slack通知: 投稿完了]
        → 失敗: [LINE Notify: エラー通知]
    → [Google Sheets: 実行ログ記録]
```

**設定手順：**
1. n8nで新しいワークフローを作成
2. 「Schedule Trigger」ノードを追加 → 06:00 JST に設定
3. 「Execute Command」ノードを追加 → `python system_a/daily_pipeline.py`
4. 「IF」ノードで実行結果を判定
5. 成功時・失敗時のそれぞれの通知ノードを接続

### Workflow B: パフォーマンス分析（毎日 21:00）

X投稿のエンゲージメント分析を自動実行します。

```
[Schedule Trigger: 21:00 JST]
    → [Execute Command: python system_a/analyze_performance.py]
    → [LINE Notify: 日次サマリー送信]
```

### Workflow C: 情報収集（毎日 07:00）

System Cのデータ収集エージェントを実行します。

```
[Schedule Trigger: 07:00 JST]
    → [Execute Command: python system_c/scheduler.py --task daily_watch]
    → [IF: 新着アラートあり?]
        → [LINE Notify: 重要ニュース通知]
```

### Workflow D: 案件処理（Webhook受付）

System Bの受注処理をWebhookで自動化します。ランサーズ・ココナラからの注文通知を受信し、案件を登録します。

```
[Webhook Trigger: POST /webhook/order]
    → [Code: リクエスト解析・バリデーション]
    → [Google Sheets: 案件台帳に登録]
    → [Execute Command: python system_b/order_intake.py --order-data ...]
    → [LINE Notify: 新規案件通知]
    → [Respond to Webhook: 200 OK]
```

**Webhook設定:**
- **パス:** `/webhook/order`
- **メソッド:** POST
- **認証:** Header Auth（独自トークン）

### Workflow E: 問い合わせBot連携

`inquiry_bot/n8n_workflow.json` に定義済みの問い合わせBot自動化ワークフローです。

```
[LINE Webhook受信: POST /webhook/line]
    → [LINE署名検証]
    → [LINEイベント解析]
    → [Bot API呼び出し: POST http://localhost:8080/api/chat]
    → [LINE返信送信]
    → [エスカレーション判定]
        → Yes: [Slack通知] + [LINE Notify通知]
    → [Google Sheets記録]

[日次レポートトリガー: 21:00]
    → [日次統計取得: GET http://localhost:8080/api/analytics]
    → [日次レポート整形]
    → [LINE Notify送信]
```

**インポート手順：**
1. n8n ダッシュボードで「Import from File」を選択
2. `inquiry_bot/n8n_workflow.json` をアップロード
3. 各ノードの認証情報（Credentials）を設定
4. 環境変数を n8n の Settings → Environment Variables に追加

必要な環境変数：
```
LINE_CHANNEL_SECRET=your_line_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_NOTIFY_TOKEN=your_line_notify_token
INQUIRY_BOT_SHEET_ID=your_google_sheets_id
```

---

## 4. System B との統合

### 4-1. 受注フロー

```
ランサーズ/ココナラで受注
    → メール通知 or Webhook
    → n8n Webhook Trigger
    → 案件情報の解析・構造化
    → Google Sheets 案件台帳に登録
    → System B order_intake.py 実行
    → LINE Notify で担当者に通知
    → 自動レポート生成開始（auto_rate に応じて）
```

### 4-2. 納品フロー

```
レポート生成完了
    → Quality Checker で品質チェック
    → IF スコア >= 閾値
        → Google Drive にPDFアップロード
        → 案件台帳のステータス更新
        → LINE Notify で納品準備完了通知
    → ELSE
        → 再生成 or 手動レビュー依頼
```

### 4-3. 自動化率と品質管理

`system_b/products.yaml` の `auto_rate` に基づき、各商品の自動化度合いを制御：

| 商品 | auto_rate | 説明 |
|------|-----------|------|
| エリア分析レポート | 80% | データ収集・分析は自動、所見は手動追加 |
| 賃料査定レポート | 90% | ほぼ全自動、最終確認のみ手動 |
| DXコンサル | 60% | ヒアリング・提案は手動、調査は自動 |
| SNS投稿代行 | 95% | ほぼ全自動 |
| ニュースレター | 95% | ほぼ全自動 |

---

## 5. 監視・運用

### 5-1. n8n ダッシュボード

n8n ダッシュボード（`http://localhost:5678`）で以下を確認できます：

- **実行履歴:** 全ワークフローの実行ログ
- **エラーログ:** 失敗した実行の詳細とスタックトレース
- **手動実行:** 任意のワークフローを手動でトリガー
- **実行統計:** 成功率・実行時間の統計

### 5-2. エラー通知の設定

n8n のSettings → 「Error Workflow」で、全ワークフローのエラー時に自動通知されるワークフローを設定できます：

```
[Error Trigger]
    → [Code: エラー情報の整形]
    → [LINE Notify: エラー通知]
    → [Google Sheets: エラーログ記録]
```

### 5-3. バックアップ

n8nのワークフロー・認証情報は定期的にバックアップします：

```bash
# ワークフローのエクスポート（全件）
n8n export:workflow --all --output=backups/n8n_workflows.json

# 認証情報のエクスポート
n8n export:credentials --all --output=backups/n8n_credentials.json
```

---

## 6. 動作確認

### 6-1. n8n の起動確認

```bash
# Dockerの場合
docker ps | grep n8n

# npmの場合
curl http://localhost:5678/healthz
```

### 6-2. Webhook テスト

```bash
# テスト用Webhookリクエストの送信
curl -X POST http://localhost:5678/webhook/order \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "lancers",
    "product_id": "tier2_rental_valuation",
    "client_name": "テスト太郎",
    "details": "東京都渋谷区のワンルーム",
    "deadline": "2026-03-01"
  }'
```

### 6-3. 問い合わせBot Webhook テスト

```bash
# LINE Webhookのシミュレーション
curl -X POST http://localhost:5678/webhook/line \
  -H "Content-Type: application/json" \
  -H "X-Line-Signature: test_signature" \
  -d '{
    "events": [{
      "type": "message",
      "message": {"type": "text", "text": "空き部屋はありますか？"},
      "source": {"userId": "test_user_123"},
      "replyToken": "test_reply_token",
      "timestamp": 1234567890
    }]
  }'
```

---

## 7. トラブルシューティング

| 症状 | 原因 | 対処法 |
|------|------|--------|
| n8n が起動しない | ポート5678が使用中 | `lsof -i :5678` で確認し、競合プロセスを停止 |
| Webhook が受信できない | URL が外部公開されていない | ngrok / リバースプロキシの設定を確認 |
| Google Sheets 連携エラー | 認証情報が無効 | n8n の Credentials を再設定 |
| ワークフローが実行されない | Inactiveになっている | ワークフローを「Active」に切り替え |
| Execute Command が失敗 | Python パスが不正 | フルパスで指定（例: `/home/user/project/venv/bin/python`） |
| タイムゾーンがずれる | TZ 未設定 | 環境変数 `GENERIC_TIMEZONE=Asia/Tokyo` を設定 |

---

## 8. 注意事項

- n8nのダッシュボードには必ず認証を設定すること（`N8N_BASIC_AUTH_ACTIVE=true`）
- Webhook URLを外部公開する場合はHTTPSを使用すること
- 認証情報（Credentials）はn8n内部で暗号化されるが、バックアップファイルの管理に注意
- ワークフローの実行ログにはAPIキー等が含まれる可能性があるため、アクセス制限を適切に設定すること
- 本番環境ではDocker + リバースプロキシ構成を推奨
- n8n のバージョンアップ時はワークフローのバックアップを必ず取得すること
