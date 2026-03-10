# Cloudflare Workers セットアップ

Cloudflare Workers の Cron Triggers を使って、Render.com 上の inquiry_bot に対する定期タスク実行を管理する。

## なぜ Cloudflare Workers？

| 項目 | cron-job.org（旧） | Cloudflare Workers（新） |
|------|-------------------|------------------------|
| 信頼性 | 外部無料サービス依存 | Cloudflare インフラ |
| cron 精度 | ±数分のズレあり | 秒単位の精度 |
| 監視 | なし | Workers Analytics + Tail |
| コスト | 無料 | 無料（10万リクエスト/日） |
| Keep-alive | 別途設定が必要 | Cron Triggers で統合管理 |

## 前提条件

- [Cloudflare アカウント](https://dash.cloudflare.com/sign-up)（無料）
- Node.js 18+
- npm

## セットアップ手順

### 1. wrangler インストール

```bash
npm install
```

### 2. Cloudflare にログイン

```bash
npx wrangler login
```

ブラウザが開くので Cloudflare アカウントで認証する。

### 3. 環境変数（シークレット）を設定

```bash
# Render.com のアプリURL
npx wrangler secret put RENDER_APP_URL
# 入力: https://rockedge-inquiry-bot.onrender.com

# トリガーAPI認証シークレット（Render側の TRIGGER_SECRET と同じ値）
npx wrangler secret put TRIGGER_SECRET
```

### 4. デプロイ

```bash
# 本番デプロイ
npm run worker:deploy

# ステージング
npm run worker:deploy:staging
```

### 5. 動作確認

```bash
# リアルタイムログ監視
npm run worker:tail

# ステータス確認（ブラウザで開く）
# https://hiroki-ai-cron.<your-subdomain>.workers.dev/status

# 手動トリガーテスト
# https://hiroki-ai-cron.<your-subdomain>.workers.dev/trigger/keep-alive
# https://hiroki-ai-cron.<your-subdomain>.workers.dev/trigger/daily-post
```

## Cron スケジュール一覧

| cron (UTC) | JST | タスク | 説明 |
|------------|-----|--------|------|
| `*/14 * * * *` | 14分毎 | keep-alive | Render スリープ防止 |
| `30 9 * * *` | 18:30 | daily-post | System A 投稿パイプライン |
| `0 12 * * *` | 21:00 | daily-analysis | System A パフォーマンス分析 |
| `0 22 * * *` | 07:00 | daily-collect | System C 日次情報収集 |
| `0 0 * * 1` | 月曜 09:00 | weekly-analysis | System A 週次分析 |
| `0 23 * * 0` | 月曜 08:00 | weekly-tech | System C テックトレンド |

## cron-job.org からの移行

1. Cloudflare Workers をデプロイ
2. `npm run worker:tail` でログを監視して正常動作を確認
3. 1〜2日間並行稼働させて問題がないことを確認
4. cron-job.org のジョブを無効化 → 削除

## トラブルシューティング

### Worker のログを確認

```bash
npm run worker:tail
```

### Cron が実行されているか確認

Cloudflare ダッシュボード → Workers & Pages → hiroki-ai-cron → Triggers → Cron Triggers で実行履歴を確認。

### Render がスリープしている場合

keep-alive の `*/14 * * * *` が正常に動作しているか確認。
Render のダッシュボードで最終リクエスト時刻を確認。

### 手動でタスクを実行

```bash
curl https://hiroki-ai-cron.<your-subdomain>.workers.dev/trigger/daily-post
```
