# X (Twitter) API セットアップ手順

## 1. X Developer Portal アカウント作成

1. [X Developer Portal](https://developer.x.com/) にアクセス
2. X Premium アカウントでログイン
3. Developer Portal に申請（用途: Bot / Automation）
4. 承認後、Project と App を作成

## 2. API キーの取得

### 2-1. App 設定
- App permissions: **Read and Write**
- Type of App: **Web App, Automated App or Bot**

### 2-2. Keys and Tokens
以下の4つのキーを取得:
- **API Key** (Consumer Key)
- **API Key Secret** (Consumer Secret)
- **Access Token**
- **Access Token Secret**

加えて:
- **Bearer Token**（v2 API 読み取り用）

## 3. TwitterAPI.io セットアップ

1. [TwitterAPI.io](https://twitterapi.io/) にアクセス
2. アカウント作成
3. API キーを取得
4. レート制限: 1000 requests/second

## 4. 環境変数設定

`.env` ファイルを作成（`config/.env.example` をコピー）:

```bash
cp config/.env.example .env
```

以下を設定:

```
X_API_KEY=your_api_key
X_API_SECRET_KEY=your_api_secret_key
X_ACCESS_TOKEN=your_access_token
X_ACCESS_TOKEN_SECRET=your_access_token_secret
X_BEARER_TOKEN=your_bearer_token
TWITTERAPI_IO_KEY=your_twitterapi_io_key
```

## 5. MCP Server 設定（Claude Desktop 用）

`config/claude_desktop_config.json` のプレースホルダーを実際のキーに置き換え:

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

## 6. 動作確認

```bash
# Bearer Token の確認
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

## 注意事項

- API キーは `.env` に保存し、Git にコミットしない
- レート制限に注意: X API v2 は 15分あたり制限あり
- 投稿間隔は最低3時間を維持（スパム判定回避）
- X Premium 加入でより高い API 制限が利用可能
