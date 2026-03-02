# CLAUDE.md — プロジェクトルール

## 命名規則
- **「System A / B / C / D / E」という命名を使わない。** ディレクトリ名・変数名・コメント・会話すべてにおいて禁止。
- 各モジュールは**機能を表す英語名**で呼ぶ:
  - `system_a/` → X投稿パイプライン（既存コード。リネーム未実施）
  - `system_b/` → 案件処理エンジン（既存コード。リネーム未実施）
  - `system_c/` → 情報収集エージェント（既存コード。リネーム未実施）
  - `system_d/` → 実績発信エンジン（既存コード。リネーム未実施）
  - `monetize/` → マネタイズエンジン
  - `inquiry_bot/` → 問い合わせBot
  - `core/` → 共通モジュール
  - `tools/` → CLIツール（nano-banana等）

## コーディング規約
- 日本語コメント推奨
- 既存のコードパターン（ClaudeClient, QualityChecker, Notifier等）を踏襲する
- YAMLで設定、JSONLでログ

## Git
- コミットメッセージは英語、feat/fix/refactor/wip プレフィクス付き

## スキル（Skills）活用ガイド

このプロジェクトには以下のスキルが設定済み。どのセッションでも使える。

### `/nano-banana` — AI画像生成
画像を生成したいときに使う。`monetize/asset_generator.py` の裏側でも使用。
```
「ロゴを生成して」「バナー画像を作って」「透過PNGのアイコンを5枚」
```
- Gemini Flash（安い・速い）とPro（高品質）を選択可能
- 512〜4K解像度、任意のアスペクト比対応
- 透過PNG、参考画像によるスタイル転写にも対応
- コスト: Flash ¥1〜5/枚、Pro ¥10〜20/枚

### `/simplify` — コード品質レビュー
コードを書いた後に使う。3つの観点で自動レビュー → 問題を即修正。
```
「コードを書き終わったので /simplify して」
```
- **再利用**: 既存ユーティリティとの重複検出
- **品質**: コピペ、マジックストリング、抽象化漏れ
- **効率**: N+1、メモリ、不要な計算

### `/setup-vertex-ai` — Vertex AI認証セットアップ
nano-banana が403エラーを返すとき（TLS inspection環境）に使う。
```
「nano-bananaが403になる」「Vertex AIをセットアップして」
```
- サービスアカウント設定 → aiplatform.googleapis.com 経由に切替

### `/session-start-hook` — セッション起動フックの管理
`.claude/hooks/session-start.sh` を編集・拡張したいときに使う。
```
「セッション起動時にXXXもインストールしたい」
```

### `/keybindings-help` — キーボードショートカット設定
Claude Code のキーバインドをカスタマイズしたいときに使う。

## 推奨ワークフロー

1. **実装** → コードを書く
2. **`/simplify`** → 品質チェック＆自動修正
3. **画像が必要なら** → `/nano-banana` で生成
4. **テスト** → `make test`
5. **コミット** → `feat/fix/refactor` プレフィクス付き
