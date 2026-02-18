# n8n セットアップ手順（オプション）

n8n はワークフロー自動化ツールです。本プロジェクトでは cron による直接実行を基本としますが、
n8n を使えばワークフローの可視化・監視・エラーハンドリングが容易になります。

## 1. n8n インストール

### Docker（推奨）
```bash
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

### npm
```bash
npm install n8n -g
n8n start
```

## 2. ワークフロー構成

### Workflow A: X投稿パイプライン（毎日 06:00）
1. **Schedule Trigger**: 06:00 JST
2. **Execute Command**: `python system_a/daily_pipeline.py`
3. **IF**: 投稿成功 → Slack通知 / 失敗 → LINE通知

### Workflow B: パフォーマンス分析（毎日 21:00）
1. **Schedule Trigger**: 21:00 JST
2. **Execute Command**: `python system_a/analyze_performance.py`

### Workflow C: 情報収集（毎日 07:00）
1. **Schedule Trigger**: 07:00 JST
2. **Execute Command**: `python system_c/scheduler.py --task daily_watch`

### Workflow D: 案件処理（Webhook）
1. **Webhook Trigger**: POST /order
2. **Execute Command**: `python -c "from system_b.order_intake import OrderIntake; ..."`

## 3. 環境変数

n8n の Credentials 機能で以下を設定:
- Anthropic API Key
- X API Keys
- Google Sheets Credentials
- LINE Notify Token

## 4. 監視

n8n ダッシュボードで:
- 実行履歴の確認
- エラーログの監視
- ワークフローの手動実行
- 実行統計の確認
