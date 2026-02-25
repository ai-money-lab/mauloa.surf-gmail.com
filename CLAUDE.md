# HIROKI AI EMPIRE — Claude Code プロジェクトガイド

## プロジェクト概要
自律型マルチシステムAI収益生成プラットフォーム。不動産×AI×デジタルアセットで複数収益チャネルを自動運用。

## アーキテクチャ
```
System E (メタ知性) → 全体最適化・自己進化
    ↕
NEXUS V2 (収益エンジン) → 市場調査→コンテンツ生成→配信→フィードバック
    ↕
System A (X投稿) → P1:JPバズ / P2:データ駆動 / P3:AI創作 / P4:NEXUS戦略
    ↕
System B (受注) → ランサーズ/ココナラ自動処理
System C (情報収集) → 不動産・市場・規制・技術エージェント
System D (実績) → 成果コンテンツ→X投稿連携
Inquiry Bot → LINE/Web問い合わせ自動応答
```

## 開発コマンド
```bash
# テスト（467テスト）
PYTHONPATH=. pytest tests/ -v --tb=short

# Lint
ruff check .

# 個別システム実行
make system-a          # X投稿パイプライン
make system-c          # 情報収集
make system-e-debate   # AI討論
make nexus-v2          # NEXUS V2 日次サイクル

# Bot
make bot-dev           # 開発サーバー起動
make bot-test          # Botテスト
```

## CI/CD ワークフロー（GitHub Actions）
| ワークフロー | トリガー | 内容 |
|---|---|---|
| `x-auto-post.yml` | 07:00/12:00/19:00 JST | X自動投稿（P1-P5選択→QC→投稿） |
| `nexus-v2.yml` | 09:00 JST日次 + 月曜週次 | 収益エンジンサイクル |
| `system-e-meta.yml` | 23:00 JST日次 + 日曜22:00週次 | メタ知性（診断・進化・フルサイクル） |
| `bot-health.yml` | 21:00 JST日次 + 月曜09:00週次 | Botヘルスチェック・レポート・FAQ |
| `deploy-bot.yml` | push to master (inquiry_bot/*) | Bot CI/CD + Render.comデプロイ |
| `auto-merge.yml` | push to claude/* | テスト→master自動マージ |
| `suno-generate.yml` | 手動ディスパッチ | AI音楽生成 |

## コード規約
- Python 3.12、型ヒント使用
- linter: ruff (E,W,F、E501無視)
- テスト: pytest、tests/conftest.pyにフィクスチャ集約
- ログ: logging モジュール使用（print非推奨）
- 設定: config/config.yaml + .env（環境変数）
- エラー処理: try/except + logging、グレースフルデグラデーション

## ディレクトリ構造
```
config/          設定ファイル（config.yaml, .env.example）
core/            共通モジュール（ClaudeClient, QC, Notifier, Sheets, PDF）
system_a/        X投稿パイプライン（14モジュール）
system_b/        受注処理（3モジュール）
system_c/        情報収集エージェント（6モジュール）
system_d/        実績コンテンツ（2モジュール）
system_e/        メタ知性エンジン（7モジュール）
nexus/           自律収益エンジン（36+モジュール、v1/v2）
inquiry_bot/     LINE/Webチャットbot（12モジュール）
prompts/         AIプロンプトテンプレート
tests/           ユニットテスト（21ファイル）
data/            ランタイムデータ（生成ファイル、ログ）
scripts/         ユーティリティスクリプト
```

## 厳守ルール
- **System A / B / C / D は一切使用禁止**（新規ワークフロー作成・CI追加・自動化対象にしないこと）
- 稼働対象は **System E / NEXUS V2 / Inquiry Bot / Suno** のみ

## 重要な注意事項
- `ANTHROPIC_API_KEY` 必須（全システム共通）
- X API投稿には4キー+ベアラートークン必要
- Google Sheets連携はオプション（credentials.json要設定）
- NEXUS V2のデータは `nexus/data/v2/` に永続化
- テスト実行時は `PYTHONPATH=.` が必須
