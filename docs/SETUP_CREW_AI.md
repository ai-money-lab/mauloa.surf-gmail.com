# CrewAI セットアップ手順

## 1. Python 環境構築

```bash
# Python 3.11+ 推奨
python --version

# 仮想環境作成
python -m venv venv
source venv/bin/activate  # Linux/Mac

# 依存パッケージインストール
pip install -r requirements.txt
```

## 2. Claude API キー設定

1. [Anthropic Console](https://console.anthropic.com/) でアカウント作成
2. API キーを発行
3. `.env` に設定:

```
ANTHROPIC_API_KEY=your_anthropic_api_key
```

## 3. CrewAI エージェント設定

`system_c/crew_config.yaml` に4つのエージェントが定義済み:

| エージェント | 役割 | 実行タイミング |
|---|---|---|
| realestate_data_agent | 不動産データ収集 | オンデマンド |
| market_analysis_agent | 市場分析 | 毎日 07:00 |
| regulation_watch_agent | 法規制監視 | 毎日 07:00 |
| tech_trend_agent | テックトレンド | 毎週月曜 08:00 |

## 4. e-Stat API キー取得

1. [e-Stat](https://www.e-stat.go.jp/) にアカウント登録
2. アプリケーションIDを取得
3. `.env` に設定:

```
ESTAT_API_KEY=your_estat_api_key
```

## 5. Google Sheets / Drive 連携

### 5-1. Google Cloud Console
1. プロジェクト作成
2. Google Sheets API / Google Drive API を有効化
3. サービスアカウント作成
4. キーファイル (JSON) をダウンロード → `config/credentials.json`

### 5-2. スプレッドシート準備
- 投稿管理シート: カラム（日時/柱番号/パイプライン/パターン/テキスト/品質スコア/ステータス）
- 案件管理シート: カラム（案件ID/商品ID/クライアント名/納期/プラットフォーム/ステータス/作成日時）

### 5-3. 環境変数設定
```
GOOGLE_SHEETS_CREDENTIALS_PATH=./config/credentials.json
SHEETS_POST_MANAGEMENT_ID=your_sheet_id
SHEETS_ORDER_MANAGEMENT_ID=your_sheet_id
GOOGLE_DRIVE_DELIVERABLES_FOLDER_ID=your_folder_id
```

## 6. LINE Notify 設定

1. [LINE Notify](https://notify-bot.line.me/) にログイン
2. トークンを発行
3. `.env` に設定:

```
LINE_NOTIFY_TOKEN=your_line_token
```

## 7. 動作確認

```bash
# System C 日次タスク実行
python system_c/scheduler.py --task daily_watch

# テーマDB初期化
python system_a/theme_rotator.py
```

## 8. cron 設定

```bash
# crontab 編集
crontab -e

# crontab_config.txt の内容をコピー
# /path/to/hiroki-ai-empire を実際のパスに置換
```
