# 自動スケジュール設定ガイド（cron-job.org）

Render無料プランではcronジョブが有料のため、**cron-job.org（無料）** を使って定期実行する。

## 前提条件

- Renderにinquiry botがデプロイ済み
- RenderのURLが `https://rockedge-inquiry-bot.onrender.com` のような形式で取得済み
- Renderの環境変数に `TRIGGER_SECRET` を設定済み

## 手順

### 1. cron-job.org にアカウント作成

https://cron-job.org にアクセスしてアカウントを作成（無料、メールのみ）。

### 2. 以下の6つのジョブを作成

ダッシュボードの「CREATE CRONJOB」から、以下を1つずつ作成する。

---

#### ジョブ1: Keep-alive（スリープ防止）

Render無料プランは15分間アクセスがないとスリープする。これを防ぐ。

| 項目 | 設定値 |
|------|--------|
| Title | `keep-alive` |
| URL | `https://あなたのURL/api/keep-alive` |
| Schedule | Every 14 minutes |
| Request method | GET |

---

#### ジョブ2: System C 日次情報収集（07:00 JST）

| 項目 | 設定値 |
|------|--------|
| Title | `daily-collect` |
| URL | `https://あなたのURL/api/trigger/daily-collect` |
| Schedule | `0 22 * * *` (22:00 UTC = 07:00 JST) |
| Request method | POST |
| Header | `X-Trigger-Secret: あなたのTRIGGER_SECRET値` |

---

#### ジョブ3: System A 日次投稿（18:30 JST）

| 項目 | 設定値 |
|------|--------|
| Title | `daily-post` |
| URL | `https://あなたのURL/api/trigger/daily-post` |
| Schedule | `30 9 * * *` (09:30 UTC = 18:30 JST) |
| Request method | POST |
| Header | `X-Trigger-Secret: あなたのTRIGGER_SECRET値` |

---

#### ジョブ4: System A 日次分析（21:00 JST）

| 項目 | 設定値 |
|------|--------|
| Title | `daily-analysis` |
| URL | `https://あなたのURL/api/trigger/daily-analysis` |
| Schedule | `0 12 * * *` (12:00 UTC = 21:00 JST) |
| Request method | POST |
| Header | `X-Trigger-Secret: あなたのTRIGGER_SECRET値` |

---

#### ジョブ5: System C 週次テックトレンド（月曜 08:00 JST）

| 項目 | 設定値 |
|------|--------|
| Title | `weekly-tech` |
| URL | `https://あなたのURL/api/trigger/weekly-tech` |
| Schedule | `0 23 * * 0` (日曜 23:00 UTC = 月曜 08:00 JST) |
| Request method | POST |
| Header | `X-Trigger-Secret: あなたのTRIGGER_SECRET値` |

---

#### ジョブ6: System A 週次分析（月曜 09:00 JST）

| 項目 | 設定値 |
|------|--------|
| Title | `weekly-analysis` |
| URL | `https://あなたのURL/api/trigger/weekly-analysis` |
| Schedule | `0 0 * * 1` (月曜 00:00 UTC = 月曜 09:00 JST) |
| Request method | POST |
| Header | `X-Trigger-Secret: あなたのTRIGGER_SECRET値` |

---

## 全体スケジュール（JST）

| 時刻 | 頻度 | タスク |
|------|------|--------|
| 毎14分 | 常時 | Keep-alive（スリープ防止） |
| 07:00 | 毎日 | System C: 市場動向+法規制チェック |
| 18:30 | 毎日 | System A: 投稿生成→画像→X投稿 |
| 21:00 | 毎日 | System A: パフォーマンス分析→LINE通知 |
| 月曜 08:00 | 週1 | System C: テックトレンド収集 |
| 月曜 09:00 | 週1 | System A: 週次分析+パイプライン比率調整 |

## トラブルシューティング

- **投稿されない**: Renderの環境変数（X_API_KEY等）を確認
- **403エラー**: `X-Trigger-Secret` ヘッダーとRenderの `TRIGGER_SECRET` 環境変数が一致しているか確認
- **タイムアウト**: cron-job.orgのタイムアウトを60秒以上に設定（投稿生成は時間がかかる）
- **スリープで遅延**: keep-aliveジョブが動いているか確認
