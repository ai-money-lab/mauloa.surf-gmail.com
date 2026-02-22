# X (Twitter) API セットアップ手順

本ドキュメントでは、System A（X自動投稿システム）に必要なX APIおよびTwitterAPI.ioのセットアップ手順を解説します。

---

## 1. X Developer Portal アカウント作成

### 1-1. 前提条件
- Xアカウント（電話番号認証済み）を保有していること
- **X Premium（旧Twitter Blue）に加入していること**（API利用に必要）

### 1-2. Developer Portal 申請手順

1. [X Developer Portal](https://developer.x.com/) にアクセス
2. Xアカウントでログイン
3. 「Sign up for Free Account」または「Apply」をクリック
4. 利用目的を記入（以下を参考）：
   - **用途:** Bot / Automation
   - **説明例:** 「不動産業界の情報発信を目的としたBot運用。業界ニュース・データ分析に基づく投稿を自動生成・投稿する。」
5. Developer Agreement に同意して申請
6. メール認証を完了

### 1-3. Project と App の作成

1. Developer Portal ダッシュボードにログイン
2. 「Projects & Apps」→「+ New Project」をクリック
3. プロジェクト名を入力（例: `ROCKEDGE-AI-System`）
4. ユースケースを選択: **Making a bot**
5. プロジェクト概要を入力
6. App名を入力（例: `rockedge-x-poster`）

---

## 2. API キー・トークンの取得

### 2-1. App Settings の設定

Developer Portal で作成した App の設定画面を開き、以下を設定：

| 設定項目 | 設定値 |
|---------|--------|
| App permissions | **Read and Write** |
| Type of App | **Web App, Automated App or Bot** |
| Callback URI | `https://localhost` (未使用だが必須) |
| Website URL | 任意（自社サイト等） |

### 2-2. Keys and Tokens の生成

App の「Keys and Tokens」タブで以下の5つのキーを取得・保管：

| キー名 | 説明 | 用途 |
|--------|------|------|
| **API Key** (Consumer Key) | アプリ認証用 | OAuth 1.0a認証 |
| **API Key Secret** (Consumer Secret) | アプリ認証用シークレット | OAuth 1.0a認証 |
| **Access Token** | ユーザー認証用 | 投稿操作 |
| **Access Token Secret** | ユーザー認証用シークレット | 投稿操作 |
| **Bearer Token** | アプリ専用認証 | v2 API読み取り専用 |

> **重要:** Access Token / Access Token Secretは「Generate」ボタンを押した際に一度だけ表示されます。必ずその場でコピーし安全な場所に保管してください。再表示はできません（再生成は可能）。

### 2-3. X Premium サブスクリプションについて

X API の利用には **X Premium（旧Twitter Blue）** への加入が推奨されます。

| プラン | 月額 | API制限 |
|--------|------|---------|
| Free | 無料 | 投稿1,500件/月、読み取り制限あり |
| Basic | $100/月 | 投稿3,000件/月、読み取り10,000件/月 |
| Pro | $5,000/月 | 投稿300,000件/月、フルアクセス |

本システム（1日3投稿 = 月90投稿）では **Free** プランでも運用可能ですが、読み取り（バズポスト収集）を含めると **Basic** プラン以上を推奨します。

---

## 3. TwitterAPI.io セットアップ

[TwitterAPI.io](https://twitterapi.io/) は、X APIのレート制限を補完するサードパーティAPIサービスです。System Aのパイプライン1（バズポスト収集）で使用します。

### 3-1. アカウント作成

1. [TwitterAPI.io](https://twitterapi.io/) にアクセス
2. 「Get Started」からアカウントを作成
3. プランを選択（従量課金制）
4. ダッシュボードからAPIキーを取得

### 3-2. 主な利用用途

- 日本語バズポストの検索・取得（パイプライン1）
- いいね数10,000以上のポスト収集
- レート制限: 1,000 requests/second（X公式APIより大幅に緩い）

---

## 4. 環境変数の設定

`.env` ファイルを作成し、取得したキーを設定します。

```bash
# .envファイルの作成（テンプレートからコピー）
cp config/.env.example .env
```

以下の環境変数を設定：

```env
# ===== X API (公式) =====
X_API_KEY=your_api_key
X_API_SECRET_KEY=your_api_secret_key
X_ACCESS_TOKEN=your_access_token
X_ACCESS_TOKEN_SECRET=your_access_token_secret
X_BEARER_TOKEN=your_bearer_token

# ===== TwitterAPI.io =====
TWITTERAPI_IO_KEY=your_twitterapi_io_key
```

> **注意:** `.env` ファイルは `.gitignore` に含まれており、Gitにコミットされません。絶対にAPIキーをGitにコミットしないでください。

---

## 5. MCP Server 設定（Claude Desktop 用）

Claude Desktop でX APIを利用する場合、MCP（Model Context Protocol）サーバーの設定が必要です。

設定ファイル: `config/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "x-twitter": {
      "command": "npx",
      "args": ["-y", "@mbelinky/x-mcp-server"],
      "env": {
        "API_KEY": "your_actual_api_key",
        "API_SECRET_KEY": "your_actual_secret",
        "ACCESS_TOKEN": "your_actual_token",
        "ACCESS_TOKEN_SECRET": "your_actual_token_secret"
      }
    }
  }
}
```

### 設定手順

1. `config/claude_desktop_config.json` を開く
2. プレースホルダー（`YOUR_API_KEY_HERE` 等）を実際のキーに置き換え
3. Claude Desktop の設定画面 → MCP Servers → 設定ファイルのパスを指定
4. Claude Desktop を再起動

---

## 6. 動作確認

### 6-1. Bearer Token の確認（読み取りAPI）

```bash
python -c "
from dotenv import load_dotenv
import os, requests
load_dotenv()
token = os.getenv('X_BEARER_TOKEN')
r = requests.get('https://api.x.com/2/users/me',
    headers={'Authorization': f'Bearer {token}'})
print(r.json())
"
```

期待される出力:
```json
{
  "data": {
    "id": "123456789",
    "name": "あなたの表示名",
    "username": "your_handle"
  }
}
```

### 6-2. 投稿テスト（Write API）

```bash
python -c "
from dotenv import load_dotenv
import os, tweepy
load_dotenv()
client = tweepy.Client(
    consumer_key=os.getenv('X_API_KEY'),
    consumer_secret=os.getenv('X_API_SECRET_KEY'),
    access_token=os.getenv('X_ACCESS_TOKEN'),
    access_token_secret=os.getenv('X_ACCESS_TOKEN_SECRET')
)
# テスト投稿（投稿後すぐに削除してください）
response = client.create_tweet(text='API接続テスト - このポストは削除します')
print(f'投稿成功: {response.data}')
"
```

### 6-3. TwitterAPI.io の確認

```bash
python -c "
from dotenv import load_dotenv
import os, requests
load_dotenv()
key = os.getenv('TWITTERAPI_IO_KEY')
r = requests.get('https://api.twitterapi.io/twitter/tweet/search',
    params={'query': '不動産 lang:ja min_faves:10000', 'count': 5},
    headers={'X-API-Key': key})
print(r.json())
"
```

### 6-4. System A パイプライン全体テスト

```bash
# 日次パイプラインの手動実行テスト
python system_a/daily_pipeline.py --dry-run
```

---

## 7. トラブルシューティング

| 症状 | 原因 | 対処法 |
|------|------|--------|
| `401 Unauthorized` | APIキーが無効 | キーの再生成・`.env`の確認 |
| `403 Forbidden` | App permissionsが不足 | Read and Write に変更し、トークンを再生成 |
| `429 Too Many Requests` | レート制限超過 | 15分待機、またはBasicプランにアップグレード |
| 投稿が反映されない | Free Plan の月間制限 | Developer Portalで使用量を確認 |
| MCP接続エラー | npx / Node.js未インストール | `node -v` で確認、Node.js 18+をインストール |

---

## 8. 注意事項

- APIキーは `.env` に保存し、**絶対にGitにコミットしない**こと
- X API v2 のレート制限: 15分あたりの回数制限あり（エンドポイントごとに異なる）
- 投稿間隔は **最低3時間** を維持する（スパム判定回避のため、`config/config.yaml` の `min_interval_hours: 3` で設定済み）
- X Premium に加入することで、より高い API 制限が利用可能
- 本番運用前に必ず `--dry-run` オプションで動作確認すること
- APIキーが漏洩した場合は、即座に Developer Portal で再生成すること
