# HIROKI AI EMPIRE

4つの自動化システムによる統合収益プラットフォーム。

## システム概要

| System | 名称 | 目的 |
|--------|------|------|
| **A** | Xハイブリッド投稿パイプライン | フォロワー増加・影響力構築 |
| **B** | 案件自動処理エンジン | ランサーズ/ココナラでの自動納品 |
| **C** | 情報収集エージェント軍団 | 競合に追いつけない情報優位性 |
| **D** | 実績発信エンジン | B/Cの成果をXで発信し案件を呼び込む好循環 |

## アーキテクチャ

```
System C (情報収集) ──データ供給──→ System A (X投稿)
       │                              ↑
       └──データ供給──→ System B (案件処理) ──実績──→ System D (実績発信) ──投稿──→ System A
```

## セットアップ

### 1. 環境構築

```bash
# Python 仮想環境
python -m venv venv
source venv/bin/activate

# 依存パッケージ
pip install -r requirements.txt

# Node.js パッケージ（MCP Server用）
npm install
```

### 2. 環境変数設定

```bash
cp config/.env.example .env
# .env ファイルを編集し、各APIキーを設定
```

### 3. 初期データ生成

```bash
# テーマDB初期化
python system_a/theme_rotator.py
```

### 4. 詳細セットアップ

- [X API セットアップ](docs/SETUP_X_API.md)
- [CrewAI セットアップ](docs/SETUP_CREW_AI.md)
- [n8n セットアップ](docs/SETUP_N8N.md)

## 使い方

### System A: X投稿パイプライン

```bash
# デイリーパイプライン実行（3パイプライン → 品質チェック → 3本投稿）
python system_a/daily_pipeline.py

# パフォーマンス分析（日次）
python system_a/analyze_performance.py

# パフォーマンス分析（週次 + パイプライン比率自動調整）
python system_a/analyze_performance.py --weekly

# 各パイプライン個別実行
python system_a/pipeline1_jp_buzz.py
python system_a/pipeline2_data_driven.py
python system_a/pipeline3_ai_original.py
```

### System B: 案件処理

```bash
# 案件処理（JSON入力）
python system_b/process_order.py
```

### System C: 情報収集

```bash
# 日次市場ウォッチ
python system_c/scheduler.py --task daily_watch

# 週次テックトレンド
python system_c/scheduler.py --task weekly_tech

# エリア分析（オンデマンド）
python system_c/scheduler.py --task area_analysis --area "港区赤坂"
```

### System D: 実績発信

```bash
# 実績コンテンツ生成
python system_d/generate_results_content.py

# System Aのスケジュールに統合
python system_d/schedule_results_posts.py
```

## cron 設定

```bash
crontab -e
# crontab_config.txt の内容をコピー
```

| 時刻 | タスク |
|------|--------|
| 06:00 毎日 | System A デイリーパイプライン |
| 07:00 毎日 | System C 日次市場ウォッチ |
| 08:00 毎週月曜 | System C 週次テックトレンド |
| 09:00 毎週月曜 | System A 週次パフォーマンス分析 |
| 20:00 毎週金曜 | System D 実績コンテンツ生成 |
| 21:00 毎日 | System A 日次パフォーマンス分析 |

## コンテンツ5本柱

| # | 柱名 | 投稿比率 |
|---|------|---------|
| 1 | 不動産の裏側 | 30% |
| 2 | 住環境・暮らしの知恵 | 25% |
| 3 | お金・資産・不動産投資 | 20% |
| 4 | 経営者の日常 | 15% |
| 5 | テクノロジー×不動産 | 10% |

## 品質管理

すべての出力は `core/quality_checker.py` を通過:

| プロファイル | 用途 | 閾値 |
|---|---|---|
| x_post | X投稿（12項目/120点満点） | 84点 |
| report | レポート納品物（10項目/100点満点） | 75点 |
| data_collection | 情報収集結果（10項目/100点満点） | 70点 |

## テスト

```bash
python -m pytest tests/ -v
```

## ディレクトリ構成

```
hiroki-ai-empire/
├── config/          # 設定ファイル
├── core/            # 共通モジュール（品質チェッカー等）
├── prompts/         # AIプロンプトテンプレート
├── templates/       # レポートテンプレート
├── system_a/        # X投稿パイプライン
├── system_b/        # 案件自動処理
├── system_c/        # 情報収集エージェント
├── system_d/        # 実績発信
├── data/            # データ保存（.gitignore）
├── reports/         # 生成レポート（.gitignore）
├── docs/            # セットアップ手順書
└── tests/           # ユニットテスト
```
