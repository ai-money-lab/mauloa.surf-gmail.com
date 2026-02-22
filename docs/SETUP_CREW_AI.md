# CrewAI セットアップ手順

本ドキュメントでは、System C（AIエージェントによるデータ収集・分析システム）で使用するCrewAIのセットアップ手順を解説します。

---

## 1. Python 環境構築

### 1-1. Python バージョン確認

```bash
# Python 3.11+ 推奨
python --version
# Python 3.11.x 以上であることを確認
```

Python 3.11未満の場合は、[pyenv](https://github.com/pyenv/pyenv) でインストール：

```bash
# pyenvによるPythonインストール
pyenv install 3.11.7
pyenv local 3.11.7
```

### 1-2. 仮想環境の作成

```bash
# 仮想環境を作成
python -m venv venv

# 仮想環境をアクティベート
source venv/bin/activate  # Linux / macOS
# venv\Scripts\activate   # Windows

# pipのアップグレード
pip install --upgrade pip
```

### 1-3. 依存パッケージのインストール

```bash
# requirements.txt から一括インストール
pip install -r requirements.txt
```

主要パッケージ一覧：

| パッケージ | 用途 |
|-----------|------|
| `crewai` | AIエージェントフレームワーク |
| `anthropic` | Claude API クライアント |
| `tweepy` | X API クライアント |
| `requests` | HTTP リクエスト |
| `beautifulsoup4` | Webスクレイピング |
| `pandas` | データ分析 |
| `python-dotenv` | 環境変数管理 |
| `gspread` | Google Sheets 連携 |
| `schedule` | タスクスケジューリング |

---

## 2. Claude API キー設定

CrewAIのバックエンドLLMとしてClaude（Anthropic）を使用します。

### 2-1. Anthropic Console でAPIキーを発行

1. [Anthropic Console](https://console.anthropic.com/) にアクセス
2. アカウントを作成（またはログイン）
3. 「API Keys」→「Create Key」でAPIキーを発行
4. キーをコピーして安全な場所に保管

### 2-2. 環境変数に設定

`.env` ファイルに以下を追加：

```env
ANTHROPIC_API_KEY=your_anthropic_api_key
```

### 2-3. 使用モデル

`config/config.yaml` で設定済み：

```yaml
system_c:
  agents:
    default_model: "claude-sonnet-4-20250514"
```

---

## 3. CrewAI エージェント設定

### 3-1. エージェント構成

`system_c/crew_config.yaml` に4つの専門エージェントが定義されています：

| エージェント名 | 役割 | 主な用途 | 実行タイミング |
|--------------|------|---------|--------------|
| `realestate_data_agent` | 不動産データリサーチャー | 物件情報・成約事例・地価データの収集 | オンデマンド |
| `market_analysis_agent` | 不動産マーケットアナリスト | 人口動態・金利・供給量から市場予測 | 毎日 07:00 |
| `regulation_watch_agent` | 不動産法規ウォッチャー | 法改正・補助金・規制変更の監視 | 毎日 07:00 |
| `tech_trend_agent` | PropTechスカウト | AI×不動産・MATTERPORT最新動向 | 毎週月曜 08:00 |

### 3-2. タスク構成

| タスク名 | 説明 | 使用エージェント | 出力先 |
|---------|------|----------------|--------|
| `area_analysis` | エリア分析（物件相場・人口動態・再開発） | data_agent + market_agent | `data/system_c/reports/` |
| `daily_watch` | 日次マーケットウォッチ | regulation_agent + market_agent | `data/system_c/daily/` |
| `weekly_tech` | 週次テックトレンド | tech_trend_agent | `data/system_c/weekly/` |
| `rental_valuation` | 賃料査定用データ収集 | data_agent | `data/system_c/valuations/` |
| `renovation_cost` | リフォーム費用相場調査 | data_agent | `data/system_c/costs/` |

### 3-3. エージェントのカスタマイズ

`system_c/crew_config.yaml` を編集してエージェントの動作を調整できます：

```yaml
agents:
  - name: "realestate_data_agent"
    role: "不動産データリサーチャー"
    goal: "指定エリアの物件情報・成約事例・地価データを網羅的に収集し構造化する"
    backstory: "不動産のプロが必要とするデータを正確に収集する専門AI"
    tools: [web_search, web_scraper, sheets_writer]
    max_iterations: 10    # 最大反復回数（増やすと精度UP・コストUP）
    verbose: true          # デバッグログの出力
```

---

## 4. データソース API キーの取得

### 4-1. e-Stat API キー（政府統計データ）

e-Stat は人口動態・世帯数・経済指標などの政府統計データを提供する公式APIです。

1. [e-Stat](https://www.e-stat.go.jp/) にアクセス
2. 「新規登録」からアカウントを作成
3. ログイン後、「マイページ」→「API機能」→「アプリケーションIDの取得」
4. アプリケーション名と利用目的を入力して申請
5. 即座にアプリケーションID（APIキー）が発行される

`.env` に設定：

```env
ESTAT_API_KEY=your_estat_api_key
```

主な利用データ：
- 国勢調査（人口・世帯構成）
- 住民基本台帳人口移動報告
- 建築着工統計
- 消費者物価指数

### 4-2. 国土交通省 不動産情報ライブラリ（MLIT）

[不動産情報ライブラリ](https://www.reinfolib.mlit.go.jp/) は認証不要（APIキー不要）で利用可能です。

- **エンドポイント:** `https://www.reinfolib.mlit.go.jp`
- **認証:** なし
- **提供データ:** 不動産取引価格情報、地価公示、都道府県地価調査

`system_c/data_sources.yaml` で設定済み：

```yaml
mlit_stats:
  type: api
  url: "https://www.reinfolib.mlit.go.jp"
  description: "国交省 不動産情報ライブラリ"
  auth: none
```

### 4-3. 地価公示・都道府県地価調査 API

[国土交通省 土地総合情報システム](https://www.land.mlit.go.jp/webland/) のAPIも認証不要です。

- **エンドポイント:** `https://www.land.mlit.go.jp/webland/api/TradeListSearch`
- **認証:** なし
- **提供データ:** 不動産取引価格情報の検索

### 4-4. その他のデータソース

`system_c/data_sources.yaml` に定義されている全データソース：

| ソース名 | 種類 | 認証 | 用途 |
|---------|------|------|------|
| SUUMO | Webスクレイパー | 不要 | 賃貸・売買物件一覧、相場情報 |
| HOME'S | Webスクレイパー | 不要 | 物件検索、賃料相場、地域情報 |
| 不動産情報ライブラリ | API | 不要 | 不動産取引価格情報 |
| 地価公示API | API | 不要 | 地価公示・都道府県地価調査 |
| e-Stat | API | APIキー必要 | 人口動態等の政府統計 |
| Google Trends | API | 不要 | 検索トレンド |

> **注意:** Webスクレイピングはレート制限（2リクエスト/秒）を遵守すること。`config/config.yaml` の `scraping.rate_limit_per_second: 2` で設定済み。

---

## 5. Google Sheets / Drive 連携

### 5-1. Google Cloud Console の設定

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新規プロジェクトを作成（例: `ROCKEDGE-AI`）
3. 以下のAPIを有効化：
   - Google Sheets API
   - Google Drive API
4. 「認証情報」→「サービスアカウント」を作成
5. サービスアカウントのキーファイル（JSON）をダウンロード
6. ダウンロードしたファイルを `config/credentials.json` として保存

### 5-2. スプレッドシートの準備

以下のスプレッドシートを作成し、サービスアカウントのメールアドレスに編集権限を付与：

**投稿管理シート:**

| カラム | 説明 |
|--------|------|
| 日時 | 投稿日時 |
| 柱番号 | コンテンツの柱番号 |
| パイプライン | 使用パイプライン（1/2/3） |
| パターン | 投稿パターン |
| テキスト | 投稿本文 |
| 品質スコア | Quality Checkerのスコア |
| ステータス | 投稿済み/予約中/エラー |

**案件管理シート:**

| カラム | 説明 |
|--------|------|
| 案件ID | ユニークID |
| 商品ID | products.yamlのID |
| クライアント名 | 顧客名 |
| 納期 | 納品期限 |
| プラットフォーム | Lancers/Coconala |
| ステータス | 受注/作業中/納品済み |
| 作成日時 | 受注日時 |

### 5-3. 環境変数の設定

```env
# Google Sheets / Drive
GOOGLE_SHEETS_CREDENTIALS_PATH=./config/credentials.json
SHEETS_POST_MANAGEMENT_ID=your_post_management_sheet_id
SHEETS_ORDER_MANAGEMENT_ID=your_order_management_sheet_id
GOOGLE_DRIVE_DELIVERABLES_FOLDER_ID=your_deliverables_folder_id
```

---

## 6. LINE Notify 設定

エージェントの実行結果やエラー通知をLINEで受信するための設定です。

### 6-1. トークンの発行

1. [LINE Notify](https://notify-bot.line.me/) にLINEアカウントでログイン
2. 「トークンを発行する」をクリック
3. トークン名を入力（例: `ROCKEDGE AI通知`）
4. 通知先のトークルームを選択（1:1 または グループ）
5. 発行されたトークンをコピー

### 6-2. 環境変数に設定

```env
LINE_NOTIFY_TOKEN=your_line_notify_token
```

---

## 7. 動作確認

### 7-1. CrewAI エージェント単体テスト

```bash
# 仮想環境がアクティブであることを確認
source venv/bin/activate

# System C の日次ウォッチタスクを手動実行
python system_c/scheduler.py --task daily_watch
```

期待される結果:
- `data/system_c/daily/market_watch_YYYY-MM-DD.json` が生成される
- コンソールにエージェントの実行ログが出力される

### 7-2. テーマDB初期化

```bash
# System A のテーマローテーション初期化
python system_a/theme_rotator.py
```

期待される結果:
- `data/system_a/theme_db.json` が更新される

### 7-3. e-Stat API 接続テスト

```bash
python -c "
from dotenv import load_dotenv
import os, requests
load_dotenv()
key = os.getenv('ESTAT_API_KEY')
r = requests.get('https://api.e-stat.go.jp/rest/3.0/app/json/getStatsList',
    params={'appId': key, 'searchWord': '人口'})
print(f'ステータス: {r.status_code}')
print(f'統計数: {len(r.json().get(\"GET_STATS_LIST\", {}).get(\"DATALIST_INF\", {}).get(\"TABLE_INF\", []))}')
"
```

### 7-4. Google Sheets 接続テスト

```bash
python -c "
import gspread
gc = gspread.service_account(filename='config/credentials.json')
sh = gc.open_by_key('your_sheet_id')
print(f'接続成功: {sh.title}')
"
```

---

## 8. cron 設定（本番運用）

各タスクのスケジュール実行を設定します。

```bash
# crontab 編集画面を開く
crontab -e

# crontab_config.txt の内容をコピー＆ペースト
# パスを実際のプロジェクトパスに置き換える
```

主なスケジュール：

| タスク | cron式 | 説明 |
|--------|--------|------|
| daily_watch | `0 7 * * *` | 毎日 07:00 - 法改正・市場動向 |
| weekly_tech | `0 8 * * 1` | 毎週月曜 08:00 - テックトレンド |
| daily_pipeline | `0 6 * * *` | 毎日 06:00 - X投稿パイプライン |
| analyze_performance | `0 21 * * *` | 毎日 21:00 - パフォーマンス分析 |

---

## 9. トラブルシューティング

| 症状 | 原因 | 対処法 |
|------|------|--------|
| `ModuleNotFoundError` | パッケージ未インストール | `pip install -r requirements.txt` |
| `AuthenticationError` | Anthropic APIキーが無効 | APIキーの再発行・`.env`確認 |
| e-Stat API エラー | アプリケーションIDが無効 | e-Statマイページで再確認 |
| Google Sheets 接続失敗 | credentials.jsonが不正 | サービスアカウント再作成 |
| スクレイピングがブロック | レート制限超過 | `rate_limit_per_second` を下げる |
| エージェントがタイムアウト | `max_iterations` 不足 | `crew_config.yaml` で値を増やす |

---

## 10. 注意事項

- 全てのAPIキーは `.env` に保存し、**Gitにコミットしない**こと
- Webスクレイピングは対象サイトの利用規約・robots.txtを遵守すること
- e-Stat APIの利用は「政府統計の総合窓口の利用規約」に従うこと
- エージェントの実行にはAnthropicのAPI利用料が発生する（月額予算は `config/config.yaml` の `monthly_api_budget_jpy: 50000` で管理）
- 本番運用前にはテスト環境で十分に動作確認を行うこと
