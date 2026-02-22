# X (Twitter) API セットアップ手順

本ドキュメントでは、System A（X自動投稿システム）に必要なX APIおよび関連サービスのセットアップ手順を説明します。

---

## 1. X Developer Portal アカウント作成

### 1-1. 前提条件
- Xアカウント（電話番号認証済み）を保有していること
- **X Premium（旧Twitter Blue）に加入済みであること**（API v2のRead & Write権限に必要）

### 1-2. Developer Portal への申請手順

1. [X Developer Portal](https://developer.x.com/) にアクセス
2. Xアカウントでログイン
3. 「Sign up for Free Account」または「Pro/Enterprise」を選択
4. Developer Agreement に同意
5. 利用用途を記入:
   - **Use case:** 「Automated posting for real estate content」
   - **Description:** 「不動産業界の情報発信を自動化するBot。投稿は1日3回程度、スパム行為は行わない」
6. 申請を送信（通常は即時〜数時間で承認）

### 1-3. Project と App の作成

1. Developer Portal ダッシュボードから「Projects & Apps」へ
2. 「+ Create Project」をクリック
3. Project 名を入力（例: `ROCKEDGE-Content`）
4. Use case: 「Making a bot」を選択
5. Project description を入力
6. App 名を入力（例: `rockedge-x-bot`）

---

## 2. API キー / アクセストークンの取得

### 2-1. App 設定の確認

Developer Portal > 対象 App > Settings で以下を設定:

| 設定項目 | 推奨値 |
|---------|--------|
| App permissions | **Read and Write** |
| Type of App | **Web App, Automated App or Bot** |
| Callback URI | `https://localhost:3000/callback`（使用しない場合も設定必須） |
| Website URL | `https://rockedge.jp`（ご自身のサイトURL） |

### 2-2. Keys and Tokens の取得

Developer Portal > 対象 App > 「Keys and Tokens」タブで以下の5つを取得・保存:

| キー名 | 説明 | 用途 |
|--------|------|------|
| **API Key** (Consumer Key) | アプリ識別キー | OAuth 1.0a 認証 |
| **API Key Secret** (Consumer Secret) | アプリ秘密鍵 | OAuth 1.0a 認証 |
| **Access Token** | ユーザーアクセストークン | 投稿・読み取り |
| **Access Token Secret** | ユーザー秘密トークン | 投稿・読み取り |
| **Bearer Token** | アプリ専用トークン | v2 API 読み取り専用 |

> **重要:** Access Token と Access Token Secret は「Read and Write」権限で生成すること。権限変更後はトークンの再生成が必要です。

### 2-3. X Premium に関する注意事項

- 2024年以降、X API v2 で投稿（POST）を行うには **X Premium（有料サブスクリプション）** が必要です
- Free プランでは月間1,500ツイートまで（投稿のみ）
- Basic プランでは月間3,000ツイートまで（投稿＋読み取り拡張）
- 本プロジェクトのSystem Aは1日3投稿（月間約90投稿）のため、**Free プランでも運用可能**
- ただし、Pipeline 1（バズツイート収集）で大量の読み取りが必要な場合は Basic 以上を推奨

---

## 3. TwitterAPI.io セットアップ

System A の Pipeline 1（日本語バズツイート収集）では、X公式APIの制限を回避するため [TwitterAPI.io](https://twitterapi.io/) を併用しています。

### 3-1. アカウント作成

1. [TwitterAPI.io](https://twitterapi.io/) にアクセス
2. 「Get Started」からアカウント作成
3. プランを選択（Starter プランで十分）

### 3-2. API キーの取得

1. ダッシュボードにログイン
2. 「API Keys」セクションから API キーをコピー
3. レート制限の確認: **1,000 requests/second**（十分な余裕あり）

### 3-3. 利用用途（System A Pipeline 1）

- 日本語のバズツイート（いいね10,000以上）を収集
- 過去72時間以内の投稿を検索
- 最大30件を取得し、不動産関連の話題を抽出

---

## 4. 環境変数の設定

### 4-1. `.env` ファイルの作成

```bash
# プロジェクトルートで実行
cp config/.env.example .env
```

### 4-2. X API 関連の環境変数を設定

`.env` ファイルに以下を追記:

```env
# ===== X (Twitter) API =====
X_API_KEY=your_api_key_here
X_API_SECRET_KEY=your_api_secret_key_here
X_ACCESS_TOKEN=your_access_token_here
X_ACCESS_TOKEN_SECRET=your_access_token_secret_here
X_BEARER_TOKEN=your_bearer_token_here

# ===== TwitterAPI.io =====
TWITTERAPI_IO_KEY=your_twitterapi_io_key_here
```

> **注意:** `.env` ファイルは `.gitignore` に登録されており、Git にコミットされません。キーの漏洩に十分ご注意ください。

---

## 5. MCP Server 設定（Claude Desktop / Claude Code 用）

Claude Desktop または Claude Code から直接 X API を操作するために、MCP Server を設定します。

### 5-1. 設定ファイルの場所

`config/claude_desktop_config.json` を編集します。

### 5-2. 設定内容

プレースホルダーを実際のキーに置き換えてください:

```json
{
  "mcpServers": {
    "x-twitter": {
      "command": "npx",
      "args": ["-y", "@mbelinky/x-mcp-server"],
      "env": {
        "API_KEY": "your_actual_api_key",
        "API_SECRET_KEY": "your_actual_api_secret_key",
        "ACCESS_TOKEN": "your_actual_access_token",
        "ACCESS_TOKEN_SECRET": "your_actual_access_token_secret"
      }
    }
  }
}
```

### 5-3. Claude Desktop への適用

1. Claude Desktop の設定画面を開く
2. 「MCP Servers」セクションに上記の設定を追加
3. Claude Desktop を再起動

### 5-4. Claude Code への適用

```bash
# Claude Code 使用時は、プロジェクトルートに config/claude_desktop_config.json が
# 存在すれば自動的に MCP Server 設定が読み込まれます
```

---

## 6. 動作確認

### 6-1. Bearer Token（読み取り権限）の確認

```bash
python -c "
from dotenv import load_dotenv
import os, requests
load_dotenv()
token = os.getenv('X_BEARER_TOKEN')
r = requests.get('https://api.x.com/2/users/me',
    headers={'Authorization': f'Bearer {token}'})
print('Status:', r.status_code)
print('Response:', r.json())
"
```

期待される出力:
```json
{"data": {"id": "123456789", "name": "あなたの表示名", "username": "your_username"}}
```

### 6-2. OAuth 1.0a（投稿権限）の確認

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
me = client.get_me()
print('認証成功:', me.data.username)
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
    headers={'X-API-Key': key},
    params={'query': 'lang:ja min_faves:10000', 'count': 5})
print('Status:', r.status_code)
print('Results:', len(r.json().get('tweets', [])))
"
```

### 6-4. MCP Server の確認

Claude Desktop で以下のプロンプトを入力:

```
X APIを使ってアカウント情報を取得してください
```

正常に動作すれば、アカウント情報が表示されます。

### 6-5. System A パイプラインの動作確認

```bash
# ドライラン（実際の投稿は行わない）
python system_a/daily_pipeline.py --dry-run
```

---

## 7. トラブルシューティング

### 認証エラー（401 Unauthorized）
- API Key / Access Token が正しく設定されているか確認
- Access Token の権限が「Read and Write」になっているか確認
- X Premium の加入状況を確認

### レート制限エラー（429 Too Many Requests）
- X API v2 の制限: 15分あたりのリクエスト数に上限あり
- 投稿: 1日あたりのツイート数に上限あり
- `config/config.yaml` の `min_interval_hours: 3` を遵守すること

### MCP Server が接続できない
- Node.js がインストールされているか確認（`node --version`）
- npx が利用可能か確認（`npx --version`）
- ファイアウォール設定を確認

---

## 8. セキュリティに関する注意事項

- API キーは **絶対に** Git リポジトリにコミットしない
- `.env` ファイルは `.gitignore` に登録済みであることを確認
- 定期的に API キーをローテーション（再生成）する
- 不要になったアプリ・キーは Developer Portal から削除する
- 投稿間隔は最低3時間を維持し、スパム判定を回避する
- X の利用規約（Automation Rules）を遵守する
