# CLAUDE.md — プロジェクトメモリ

## プロジェクト概要
**HIROKI AI EMPIRE** — 4つの自動化システムによる統合収益プラットフォーム。
不動産・施工コーディネーター HIROKIの知見をAIで拡張。

## システム構成
- **System A**: Xハイブリッド投稿パイプライン（日本語X投稿を自動生成・投稿）
- **System B**: 案件処理エンジン（ランサーズ/ココナラ案件を自動処理）
- **System C**: 情報収集エージェント軍団（市場データ・法規制・テックトレンド）
- **System D**: 実績発信エンジン（B/Cの成果をコンテンツ化）
- **System E**: AIバーチャルキャラクター収益化（Maia — ウェルネス/フィットネス系）

## System E — AIキャラクター「Maia」
- 26歳、東京生まれ、LA留学経験あり、現在東京拠点
- ウェルネス/フィットネス系コンテンツクリエイター
- 英語メイン（高CPM）、日本語サブ
- 収益: Fanvue（サブスク4層）+ アフィリエイト + ブランド案件
- 画像生成: Flux.1 Dev（ComfyUI/RunPod）
- FTCコンプライアンス対応済み（AI開示ハッシュタグ自動付与）

### キャラ命名に関する議論（進行中）
- 「Maia」は仮名として使用中
- 日本語名（コハル等）→ 商標競合多い
- ハワイ語名（マヒナ等）→ 競合多い
- **現在の方向: 頭文字・略語型アプローチ**で独自名を作る
- 候補: MAIA, LANI, HALO, NAMI, KAIA, WABI（まだ決定していない）

## 技術スタック
- Python（メインロジック）
- Node.js（一部ツール）
- GitHub Actions（CI/CD）
- Render（デプロイ）
- RunPod（GPU画像生成）
- X API（投稿）
- Fanvue API

## 開発ルール
- テスト: `make test` または `pytest`
- リント: `ruff check`
- フォーマット: `ruff format`
- 品質ゲート: 全出力を自動採点、閾値未満は再生成/却下

## リポジトリ構造
```
config/       — 設定ファイル
core/         — 共通コアモジュール
data/         — データファイル
docs/         — ドキュメント
inquiry_bot/  — 問い合わせボット
prompts/      — プロンプトテンプレート
research/     — リサーチ資料
scripts/      — ユーティリティスクリプト
system_a/     — X投稿パイプライン
system_b/     — 案件処理エンジン
system_c/     — 情報収集エージェント
system_d/     — 実績発信エンジン
system_e/     — AIキャラクター収益化
templates/    — テンプレート
tests/        — テスト
```
