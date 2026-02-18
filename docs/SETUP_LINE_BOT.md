# LINE 問い合わせBot セットアップ手順

## 全体像

```
LINE公式アカウント → Messaging API → Webhook → inquiry_bot/server.py → Claude AI → LINE返信
```

必要なもの:
1. LINE公式アカウント（無料で作成可能）
2. LINE Messaging API チャネル
3. サーバー（Webhook受信用）

---

## Step 1: LINE公式アカウント作成

1. [LINE Official Account Manager](https://manager.line.biz/) にアクセス
2. 「アカウントを作成」をクリック
3. 以下を入力:
   - アカウント名: **ROCKEDGE Property Management**
   - 業種: **不動産** > **不動産仲介・管理**
   - メールアドレス: 会社のメールアドレス
4. 作成完了 → 管理画面にログイン

---

## Step 2: Messaging API を有効化

1. LINE Official Account Manager の管理画面
2. 右上「設定」→ 「Messaging API」
3. 「Messaging APIを利用する」をクリック
4. **プロバイダー** を選択（なければ新規作成: 「ROCKEDGE」）
5. 確認して有効化

---

## Step 3: LINE Developers でチャネル設定

1. [LINE Developers Console](https://developers.line.biz/console/) にアクセス
2. プロバイダー「ROCKEDGE」を選択
3. Messaging API チャネルを選択

### 3-1. チャネルシークレットを取得
- 「チャネル基本設定」タブ
- **チャネルシークレット** をコピー → `.env` の `LINE_CHANNEL_SECRET` に設定

### 3-2. チャネルアクセストークンを発行
- 「Messaging API設定」タブ
- **チャネルアクセストークン（長期）** の「発行」をクリック
- トークンをコピー → `.env` の `LINE_CHANNEL_ACCESS_TOKEN` に設定

### 3-3. Webhook URLを設定
- 「Messaging API設定」タブ
- **Webhook URL**: `https://あなたのドメイン/webhook/line`
  - ローカルテスト時: ngrok等を使用（後述）
- **Webhookの利用**: オン
- **応答メッセージ**: オフ（Botが代わりに返答するため）
- **あいさつメッセージ**: オフ（Botのウェルカムメッセージを使用）

---

## Step 4: 環境変数を設定

`.env` ファイルに以下を追加:

```bash
# ═══ LINE Messaging API（問い合わせBot用） ═══
LINE_CHANNEL_SECRET=取得したチャネルシークレット
LINE_CHANNEL_ACCESS_TOKEN=取得したチャネルアクセストークン

# ═══ LINE Notify（管理者通知用・既存） ═══
LINE_NOTIFY_TOKEN=既存のトークン（エスカレーション通知に使用）

# ═══ 問い合わせBot Google Sheets ═══
INQUIRY_BOT_SHEET_ID=（Step 5で作成）
```

---

## Step 5: Google Sheets（問い合わせログ用）を作成

1. Google Sheetsで新しいスプレッドシートを作成
2. シート名を「inquiry_log」に変更
3. A1行にヘッダーを入力:

| A | B | C | D | E | F | G |
|---|---|---|---|---|---|---|
| timestamp | channel | user_id | message | reply | category | escalated |

4. スプレッドシートのIDをコピー（URLの `/d/` と `/edit` の間の文字列）
5. `.env` の `INQUIRY_BOT_SHEET_ID` に設定
6. サービスアカウントにスプレッドシートの編集権限を共有

---

## Step 6: ローカルでテスト

### 6-1. ngrokのインストールと起動

```bash
# ngrokインストール（まだの場合）
# https://ngrok.com/ からダウンロード

# Bot サーバー起動
uvicorn inquiry_bot.server:app --host 0.0.0.0 --port 8080 --reload

# 別ターミナルでngrok起動
ngrok http 8080
```

ngrokが表示するURL（例: `https://xxxx-xx-xx.ngrok-free.app`）をコピー。

### 6-2. Webhook URLを更新

LINE Developers Console:
- Webhook URL: `https://xxxx-xx-xx.ngrok-free.app/webhook/line`
- 「検証」ボタンで接続テスト

### 6-3. テストメッセージ送信

LINEアプリで公式アカウントを友だち追加し、メッセージを送信:
- 「空いていますか？」
- 「内見したい」
- 「賃料を教えてください」

→ AIが自動で返答すれば成功！

---

## Step 7: リッチメニュー設定（任意）

LINE Official Account Manager で設定:

### おすすめメニュー構成（2×3）

| 空室確認 | 内見予約 |
|---------|---------|
| 賃料・費用 | 設備情報 |
| 3Dバーチャルツアー | お電話 |

各ボタンのアクション:
- テキスト送信: 「空室を確認したい」「内見を予約したい」等
- 3Dバーチャルツアー: URLリンク
- お電話: tel:000-0000-0000

---

## Step 8: 本番デプロイ

### Railway の場合

```bash
# Railway CLIインストール
npm install -g @railway/cli

# ログイン & プロジェクト作成
railway login
railway init

# 環境変数設定
railway variables set LINE_CHANNEL_SECRET=xxx
railway variables set LINE_CHANNEL_ACCESS_TOKEN=xxx
railway variables set ANTHROPIC_API_KEY=xxx
railway variables set LINE_NOTIFY_TOKEN=xxx

# デプロイ
railway up
```

### Render の場合

1. render.com でアカウント作成
2. 「New Web Service」→ GitHubリポジトリを接続
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn inquiry_bot.server:app --host 0.0.0.0 --port $PORT`
5. Environment Variables に上記の変数を設定

デプロイ後:
- Webhook URL を本番URLに更新
- LINE Developers Console で「検証」を実行

---

## LINE公式アカウント料金プラン

| プラン | 月額 | 無料メッセージ | 追加メッセージ |
|--------|------|---------------|--------------|
| コミュニケーション | 0円 | 200通/月 | 不可 |
| ライト | 5,000円 | 5,000通/月 | 不可 |
| スタンダード | 15,000円 | 30,000通/月 | 〜3円/通 |

**おすすめ:** まずは無料プランでテスト → 問い合わせが増えたらライトに移行

---

## トラブルシューティング

### Webhookが届かない
- Webhook URLが正しいか確認
- 「Webhookの利用」がオンになっているか確認
- サーバーが起動しているか確認
- ngrok使用時: ngrokが動いているか確認

### 署名検証エラー
- `LINE_CHANNEL_SECRET` が正しいか確認
- チャネルシークレットをコピーし直す

### 返信が来ない
- `LINE_CHANNEL_ACCESS_TOKEN` が正しいか確認
- `ANTHROPIC_API_KEY` が設定されているか確認
- サーバーログを確認: `uvicorn inquiry_bot.server:app --log-level debug`

### 「応答メッセージ」と競合する
- LINE Official Account Manager → 設定 → 応答設定
- 「応答メッセージ」を **オフ** にする
- 「あいさつメッセージ」を **オフ** にする（Botが代替）
