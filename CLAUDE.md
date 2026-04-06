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

### `/floorplan-render` — 間取り図→フォトリアルレンダリング
間取り図画像をチャットにドロップして使う。自動で内観パース＆俯瞰図を生成。
```
[間取り図PNGをドロップ] →「/floorplan-render」
[間取り図ドロップ] →「/floorplan-render 家具付き Proモデルで」
```
- 画像から寸法・レイアウトを自動読み取り → SVG/PNG再構築 → nano-banana -r で高精度生成
- JSON設定ファイルとして保存されるので、同じ物件の再生成が一瞬
- コスト: Flash ¥2〜10/枚、Pro ¥10〜40/枚

### `/keybindings-help` — キーボードショートカット設定
Claude Code のキーバインドをカスタマイズしたいときに使う。

## セッションログ

過去のセッションのコンテキストは `~/.claude/session-logs/` に保存されている。
新しいセッションの冒頭で前回の作業を引き継ぎたい場合:

```
~/.claude/session-logs/ にあるセッションログを読んでコンテキストを把握して
```

| ファイル | 内容 |
|---------|------|
| `2026-03-03-nano-banana-setup.md` | nano-banana/floorplan-render スキル構築、岩崎402レンダリング、マネタイズエンジン |

## AI美女コンテンツパイプライン

`monetize/ai_beauty/` にAI美女マネタイズ用の制作パイプラインがある。
Claudeに自然言語で指示するだけで、キャラ管理・画像生成・投稿スケジュールを操作できる。

### 指示例

```
「キャラ一覧を見せて」
「Mioのカフェ写真を5枚生成して」
「Fanvue用のビキニセットを10枚作って」
「FANZA用CG集をOLシチュで50枚作って」
「Mioの今週のX投稿スケジュールを作って」
「今日のタスクを見せて」
「新キャラ Runaを追加して — 22歳、ショートヘア、ボーイッシュ」
```

### ファイル構成

| ファイル | 役割 |
|---------|------|
| `monetize/ai_beauty/characters.yaml` | キャラクター定義（ペルソナ・ビジュアル・LoRA・プラットフォーム設定） |
| `monetize/ai_beauty/prompts.yaml` | プロンプトテンプレート（SFW/NSFW・シチュ別・差分定義） |
| `monetize/ai_beauty/pipeline.py` | 生成パイプライン（ComfyUI連携・nano-bananaフォールバック・スケジュール管理） |

### 対象プラットフォーム

| プラットフォーム | コンテンツ | 自動化レベル |
|---|---|---|
| **X（Twitter）** | SFW美女画像 + 投稿文 | プロンプト生成→手動投稿 |
| **Instagram** | SFWグラビア + Reels | プロンプト生成→手動投稿 |
| **Fanvue** | NSFW含むサブスクコンテンツ | セット生成→手動アップロード |
| **FANZA同人** | R18 CG集（50-100枚） | プロンプト一括生成→ComfyUIで実行 |

### キャラ一貫性の技術スタック

```
Layer 1: カスタムLoRA（体型・髪型・雰囲気）
Layer 2: PuLID / IP-Adapter FaceID Plus v2（顔の特徴ロック）
Layer 3: ControlNet OpenPose（ポーズ指定）
```

## 推奨ワークフロー

1. **実装** → コードを書く
2. **`/simplify`** → 品質チェック＆自動修正
3. **画像が必要なら** → `/nano-banana` で生成
4. **テスト** → `make test`
5. **コミット** → `feat/fix/refactor` プレフィクス付き
