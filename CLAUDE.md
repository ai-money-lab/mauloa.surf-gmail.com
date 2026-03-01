# CLAUDE.md — プロジェクトルール

## 命名規則
- **「System A / B / C / D / E」という命名を使わない。** ディレクトリ名・変数名・コメント・会話すべてにおいて禁止。
- 各モジュールは**機能を表す英語名**で呼ぶ:
  - `system_a/` → X投稿パイプライン（既存コード。リネーム未実施）
  - `system_b/` → 案件処理エンジン（既存コード。リネーム未実施）
  - `system_c/` → 情報収集エージェント（既存コード。リネーム未実施）
  - `system_d/` → 実績発信エンジン（既存コード。リネーム未実施）
  - `monetize/` → マネタイズエンジン（新規）
  - `inquiry_bot/` → 問い合わせBot
  - `core/` → 共通モジュール
  - `tools/` → CLIツール（nano-banana等）

## コーディング規約
- 日本語コメント推奨
- 既存のコードパターン（ClaudeClient, QualityChecker, Notifier等）を踏襲する
- YAMLで設定、JSONLでログ

## Git
- コミットメッセージは英語、feat/fix/refactor/wip プレフィクス付き
