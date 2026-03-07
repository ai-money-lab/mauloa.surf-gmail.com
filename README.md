# HIROKI AI EMPIRE

4つの自動化システムによる統合収益プラットフォーム。
不動産・施工コーディネーター HIROKIの知見をAIで拡張し、コンテンツ生成から案件処理・情報収集・実績発信までを全自動で回す。

---

## アーキテクチャ概要

```
┌─────────────────────────────────────────────────────────────────────┐
│                      HIROKI AI EMPIRE                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────────┐       ┌──────────────┐                          │
│   │  System C     │       │  System B     │                          │
│   │ 情報収集      │       │ 案件処理      │                          │
│   │ エージェント  │       │ エンジン      │                          │
│   │ 軍団          │       │               │                          │
│   └──────┬───────┘       └──────┬───────┘                          │
│          │ データ供給            │ 実績データ                        │
│          ▼                      ▼                                   │
│   ┌──────────────┐       ┌──────────────┐                          │
│   │  System A     │◀──────│  System D     │                          │
│   │ Xハイブリッド │ 投稿  │ 実績発信      │                          │
│   │ 投稿          │ 統合  │ エンジン      │                          │
│   │ パイプライン  │       │               │                          │
│   └──────────────┘       └──────────────┘                          │
│                                                                     │
│   ┌─────────────────────────────────────────────┐                  │
│   │           品質チェッカー (Quality Gate)       │                  │
│   │  全出力を自動採点 → 閾値未満は再生成/却下    │                  │
│   └─────────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────┘
```

### システム間データフロー

```
System C (情報収集) ──データ供給──→ System A (X投稿)
       │                              ▲
       │                              │
       └──データ供給──→ System B (案件処理) ──実績──→ System D (実績発信) ──投稿統合──→ System A
```

1. **System C** が毎日市場データ・法規制変更・テックトレンドを収集
2. **System A** がそのデータを使って日本語X投稿を自動生成・投稿
3. **System B** がランサーズ/ココナラの案件を自動処理し、レポートをPDF納品
4. **System D** が B/C の成果を実績コンテンツ化し、System A 経由でXに投稿
5. 全ての出力は **品質チェッカー** を通過してから公開/納品

---

## System A: Xハイブリッド投稿パイプライン

毎日3本のX投稿を、3つの異なるパイプラインで生成し、品質チェックを通過したものだけを自動投稿する。

### 3つのパイプライン

| パイプライン | 名称 | 初期比率 | 概要 |
|---|---|---|---|
| **Pipeline 1** | JP Buzz 構文インポート | 40% | 日本語バズツイート（1万いいね以上）の構文を抽出し、HIROKIの専門知識で書き換え |
| **Pipeline 2** | データドリブン・オリジナル | 35% | Google Trends・Yahoo!ニュース・国交省データ等のリアルタイムデータから投稿を生成 |
| **Pipeline 3** | AI完全オリジナル | 25% | テーマDBから未使用テーマを選び、AIがゼロから作成 |

### パイプライン比率自動調整

- 週次パフォーマンス分析で各パイプラインのエンゲージメント率を計測
- 成績の良いパイプラインの比率を自動で上げ、悪いものを下げる
- 調整上限: 1週間あたり最大10%変動、各パイプライン最低15%〜最大60%

### 投稿フロー

```
06:00  3パイプライン並列実行（各パイプラインが投稿候補を生成）
  ↓
06:06  PostSelector が品質スコア・テーマバランスで3本選択
  ↓
07:00 / 12:00 / 19:00  AutoPoster が時刻指定で自動投稿
  ↓
21:00  日次パフォーマンス分析
  ↓
毎週月曜 09:00  週次分析 + パイプライン比率自動調整
```

---

## System B: 案件自動処理エンジン

ランサーズ・ココナラ等のフリーランスプラットフォームからの受注案件を、データ収集からPDF納品まで自動化する。

### 商品ラインナップ

| Tier | 商品名 | 価格帯 | 自動化率 |
|---|---|---|---|
| **Tier 1** | 不動産投資エリア分析レポート | 30〜50万円 | 80% |
| **Tier 1** | 不動産会社向けDXコンサル | 30〜50万円 | 60% |
| **Tier 2** | 賃料査定AI分析レポート | 5〜15万円 | 90% |
| **Tier 2** | リフォーム費用比較レポート | 5〜15万円 | 85% |
| **Tier 2** | 物件売却戦略レポート | 5〜15万円 | 85% |
| **Tier 2** | AI防犯カメラ導入提案書 | 5〜10万円 | 85% |
| **Tier 2** | 特殊清掃・遺品整理コーディネート提案書 | 3〜8万円 | 80% |
| **Tier 2** | 問い合わせ自動対応Bot構築 | 10〜30万円 | 70% |
| **Tier 3** | 不動産会社向けSNS投稿代行（月額） | 3万円/月 | 95% |
| **Tier 3** | 週刊不動産マーケットニュース | 1〜3万円/月 | 95% |

### 処理フロー

```
案件受注 → データ収集（System C連携） → レポート生成（Claude API）
  → 品質チェック（report プロファイル 75点以上） → PDF生成 → 自動納品
```

---

## System C: 情報収集エージェント軍団

4体の専門AIエージェントが、不動産市場データ・法規制・テックトレンドを自動収集する。

### エージェント一覧

| エージェント | 役割 | スケジュール |
|---|---|---|
| **RealEstateDataAgent** | SUUMO・HOME'S等から物件データ・賃料相場を収集 | 日次 |
| **MarketAnalysisAgent** | 地価公示・e-Stat等から市場動向を分析 | 日次 |
| **RegulationWatchAgent** | 国交省・法改正情報をウォッチ | 日次 |
| **TechTrendAgent** | 不動産テック・AI技術トレンドを収集 | 週次（月曜） |

### データソース

| ソース | 種別 | 対象データ |
|---|---|---|
| SUUMO | Webスクレイピング | 賃貸・売買物件、相場情報 |
| HOME'S | Webスクレイピング | 物件検索、賃料相場、地域情報 |
| 国交省 不動産情報ライブラリ | API | 不動産取引データ |
| 地価公示API | API | 公示地価・都道府県地価調査 |
| e-Stat | API | 政府統計（人口動態等） |
| Google Trends | API | 検索トレンド |

---

## System D: 実績発信エンジン

System B（案件処理）と System C（情報収集）の成果を、X投稿用の実績コンテンツに変換する。

- 週4本の実績投稿を生成
- 対象柱: 「売却・相続の判断と進め方」「賃貸オーナーの物件管理」
- 生成した投稿は System A のスケジュールに統合される

```
System B 納品実績 ──→ 実績コンテンツ生成 ──→ System A 投稿キューに追加
System C 収集データ ─┘
```

---

## コンテンツ5本柱

「誰が、何に困っているか」を起点に5つの柱を設計。投稿比率をコントロールする。

| # | 柱名 | 対象 | 投稿比率 | テーマ例 |
|---|------|------|---------|---------|
| 1 | **売却・相続の判断と進め方** | 売りたい人・相続した人 | 35% | 相続不動産の第一歩、売却の流れ、査定と実売価格の差、仲介vs買取、空き家リスク |
| 2 | **賃貸オーナーの物件管理** | 物件を持っている人 | 25% | 空室対策、管理会社選び、防犯カメラ効果、特殊清掃対応、遺品整理、クリーニング判断 |
| 3 | **部屋探し・住まいの知恵** | 部屋を探している人・住んでいて困っている人 | 20% | おとり物件、退去費用、騒音対策、防犯、原状回復 |
| 4 | **住まいとお金の判断軸** | 購入・投資を検討中の人 | 10% | 賃貸vs持ち家、利回りの読み方、エリア選び、ローン基礎 |
| 5 | **現場から見える景色** | HIROKIを知りたい人 | 10% | 不動産の仕事の気づき、サーフィン、愛犬KOA、ジム立ち上げ |

テーマDBには各柱ごとにサブテーマが登録されており、テーマローテーターが重複を避けて選択する（同一サブテーマは月2回まで）。

---

## 品質チェッカー (Quality Gate)

`core/quality_checker.py` がすべてのシステム出力を自動採点する。閾値未満の場合は再生成を試み、それでも通過しなければエスカレーション通知を送る。

### プロファイル

| プロファイル | 用途 | チェック項目数 | 満点 | 合格閾値 |
|---|---|---|---|---|
| **x_post** | X投稿 | 12項目 | 120点 | 84点（70%） |
| **report** | レポート納品物 | 10項目 | 100点 | 75点（75%） |
| **data_collection** | 情報収集結果 | 10項目 | 100点 | 70点（70%） |

### x_post チェック項目（12項目）

`hook_power` / `persona_match` / `pillar_alignment` / `usefulness` / `no_external_links` / `no_banned_content` / `character_limit` / `number_included` / `cta_ending` / `originality` / `tone_balance` / `problem_solving`

### report チェック項目（10項目）

`data_accuracy` / `structure` / `actionable` / `professional_tone` / `no_banned_content` / `hiroki_insight` / `visual_readability` / `completeness` / `market_relevance` / `deliverable_format`

### data_collection チェック項目（10項目）

`source_reliability` / `freshness` / `completeness` / `structure` / `no_banned_content` / `deduplication` / `relevance` / `numerical_validity` / `metadata_complete` / `usability`

### 品質チェックフロー

```
コンテンツ生成 → 品質チェック（Claude API, temperature=0.2）
  ├─ 84点以上（x_post） → auto_approved → 投稿キューへ
  ├─ 閾値未満 → 再生成（改善理由+提案つき） → 再チェック
  └─ 3回失敗 → escalated → LINE通知 → 人間が確認
```

品質ログは `data/quality_logs/` に全て保存される。

---

## セットアップ

### 1. Python環境構築

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Node.jsパッケージ（MCP Server用）

```bash
npm install
```

### 3. 環境変数設定

```bash
cp config/.env.example .env
```

以下のAPIキーを `.env` に設定:

| 変数名 | 用途 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API（全システム共通） |
| `X_API_KEY` / `X_API_SECRET` | X (Twitter) API |
| `X_ACCESS_TOKEN` / `X_ACCESS_SECRET` | X投稿用アクセストークン |
| `TWITTERAPI_IO_KEY` | twitterapi.io（バズツイート取得） |
| `LINE_CHANNEL_SECRET` / `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API（Bot + 通知） |
| `LINE_USER_ID` | LINE通知先ユーザーID |
| `GOOGLE_SHEETS_CREDENTIALS` | Google Sheets API（案件管理） |
| `ESTAT_API_KEY` | e-Stat API（政府統計） |

### 4. 初期データ生成

```bash
# テーマDB初期化（data/system_a/theme_db.json を生成）
python system_a/theme_rotator.py
```

### 5. cron設定

```bash
# PROJECT_ROOT を実際のパスに置換
sed -i "s|\$PROJECT_ROOT|$(pwd)|g" crontab_config.txt

# crontab登録
make cron-install
```

### 6. 詳細セットアップガイド

- [X API セットアップ](docs/SETUP_X_API.md)
- [CrewAI セットアップ](docs/SETUP_CREW_AI.md)
- [n8n セットアップ](docs/SETUP_N8N.md)
- [LINE Bot セットアップ](docs/SETUP_LINE_BOT.md)

---

## ディレクトリ構成

```
hiroki-ai-empire/
├── config/                          # 設定ファイル
│   ├── config.yaml                  #   全体設定（閾値・比率・スケジュール等）
│   └── claude_desktop_config.json   #   Claude Desktop MCP設定
├── core/                            # 共通モジュール
│   ├── claude_client.py             #   Claude API クライアント
│   ├── quality_checker.py           #   品質チェッカー（全システム共通ゲート）
│   ├── pdf_generator.py             #   PDF生成
│   ├── sheets_client.py             #   Google Sheets連携
│   └── notifier.py                  #   LINE Notify 通知
├── prompts/                         # AIプロンプトテンプレート
│   ├── quality_check.txt            #   品質チェック用プロンプト
│   ├── rewrite_jp_buzz.txt          #   Pipeline 1: バズ構文書き換え
│   ├── analyze_jp_buzz.txt          #   Pipeline 1: バズ構文分析
│   ├── data_to_post.txt             #   Pipeline 2: データ→投稿変換
│   ├── ai_original.txt              #   Pipeline 3: AI完全オリジナル
│   ├── professional_insight.txt     #   HIROKI所見生成
│   ├── generate_report.txt          #   レポート生成
│   └── results_to_post.txt          #   実績→投稿変換
├── templates/                       # レポートテンプレート（Markdown）
│   ├── area_analysis_report.md      #   エリア分析レポート
│   ├── rental_valuation_report.md   #   賃料査定レポート
│   ├── renovation_cost_report.md    #   リフォーム費用比較
│   ├── sell_strategy_report.md      #   売却戦略レポート
│   ├── security_camera_report.md    #   AI防犯カメラ提案書
│   ├── special_cleaning_report.md   #   特殊清掃提案書
│   ├── dx_consulting_report.md      #   DXコンサルレポート
│   ├── sns_content_plan.md          #   SNS投稿代行プラン
│   ├── inquiry_bot_report.md        #   問い合わせBot納品書
│   └── weekly_newsletter.md         #   週刊ニュースレター
├── system_a/                        # System A: Xハイブリッド投稿パイプライン
│   ├── daily_pipeline.py            #   デイリーオーケストレーター
│   ├── pipeline1_jp_buzz.py         #   Pipeline 1: バズ構文インポート
│   ├── pipeline2_data_driven.py     #   Pipeline 2: データドリブン
│   ├── pipeline3_ai_original.py     #   Pipeline 3: AI完全オリジナル
│   ├── collect_jp_trends.py         #   日本語トレンド収集
│   ├── theme_rotator.py             #   テーマローテーター
│   ├── post_selector.py             #   投稿選択・スケジューリング
│   ├── auto_post.py                 #   X自動投稿
│   ├── analyze_performance.py       #   パフォーマンス分析（日次/週次）
│   └── generate_and_post.py         #   生成+投稿一括実行
├── system_b/                        # System B: 案件自動処理エンジン
│   ├── order_intake.py              #   案件取り込み
│   ├── process_order.py             #   案件処理パイプライン
│   └── products.yaml                #   商品定義（Tier 1〜3）
├── system_c/                        # System C: 情報収集エージェント軍団
│   ├── scheduler.py                 #   エージェントスケジューラー
│   ├── crew_config.yaml             #   CrewAI設定
│   ├── data_sources.yaml            #   データソース定義
│   └── agents/                      #   エージェント群
│       ├── realestate_data_agent.py #     不動産データ収集
│       ├── market_analysis_agent.py #     市場分析
│       ├── regulation_watch_agent.py#     法規制ウォッチ
│       └── tech_trend_agent.py      #     テックトレンド
├── system_d/                        # System D: 実績発信エンジン
│   ├── generate_results_content.py  #   実績コンテンツ生成
│   └── schedule_results_posts.py    #   実績投稿スケジューリング
├── inquiry_bot/                     # 問い合わせ自動対応Bot
│   ├── server.py                    #   Webサーバー
│   ├── bot_engine.py                #   AI応答エンジン
│   ├── line_handler.py              #   LINE Messaging API連携
│   ├── web_chat_handler.py          #   Webチャット連携
│   ├── knowledge_base.py            #   ナレッジベース管理
│   ├── conversation_manager.py      #   会話管理
│   ├── analytics.py                 #   分析・レポート
│   ├── scheduler.py                 #   定期タスク
│   ├── results_to_x.py             #   実績→X投稿変換
│   ├── faq_data.yaml               #   FAQ定義
│   ├── properties.yaml             #   物件情報
│   └── config.yaml                 #   Bot設定
├── data/                            # データ保存
│   ├── system_a/                    #   System A データ
│   │   ├── theme_db.json            #     テーマDB（5本柱+サブテーマ）
│   │   ├── post_history.json        #     投稿履歴
│   │   ├── winning_patterns.json    #     勝ちパターン蓄積
│   │   ├── generated/               #     生成済み投稿
│   │   ├── pipeline1/               #     Pipeline 1 中間データ
│   │   │   ├── collected/           #       収集したバズツイート
│   │   │   └── generated/           #       書き換え後の投稿
│   │   ├── pipeline2/               #     Pipeline 2 中間データ
│   │   │   ├── sources/             #       データソース取得結果
│   │   │   └── generated/           #       生成した投稿
│   │   ├── pipeline3/               #     Pipeline 3 中間データ
│   │   │   └── generated/           #       生成した投稿
│   │   └── stock_pool/              #     ストックプール（品質合格済み未投稿）
│   ├── system_b/                    #   System B データ
│   │   └── deliverables/            #     納品物PDF
│   ├── system_c/                    #   System C データ
│   │   ├── reports/                 #     分析レポート
│   │   ├── daily/                   #     日次収集データ
│   │   ├── weekly/                  #     週次収集データ
│   │   ├── valuations/              #     査定データ
│   │   └── costs/                   #     費用データ
│   └── quality_logs/                #   品質チェックログ（全システム）
├── reports/                         # 生成レポート
│   ├── system_a/                    #   System A レポート（パフォーマンス分析等）
│   └── system_b/                    #   System B レポート（納品物コピー等）
├── docs/                            # セットアップ手順書
│   ├── SETUP_X_API.md
│   ├── SETUP_CREW_AI.md
│   ├── SETUP_N8N.md
│   └── SETUP_LINE_BOT.md
├── tests/                           # ユニットテスト
├── scripts/                         # ユーティリティスクリプト
├── crontab_config.txt               # cron設定テンプレート
├── Makefile                         # 開発用コマンド
├── requirements.txt                 # Python依存パッケージ
├── package.json                     # Node.js依存パッケージ（MCP Server）
└── render.yaml                      # Render.comデプロイ設定
```

---

## 使い方

### System A: X投稿パイプライン

```bash
# デイリーパイプライン実行（3パイプライン → 品質チェック → 3本投稿）
python system_a/daily_pipeline.py

# 各パイプライン個別実行
python system_a/pipeline1_jp_buzz.py     # バズ構文インポート
python system_a/pipeline2_data_driven.py # データドリブン
python system_a/pipeline3_ai_original.py # AI完全オリジナル

# パフォーマンス分析（日次）
python system_a/analyze_performance.py

# パフォーマンス分析（週次 + パイプライン比率自動調整）
python system_a/analyze_performance.py --weekly

# テーマローテーション確認
python system_a/theme_rotator.py
```

### System B: 案件処理

```bash
# 案件処理（JSON入力 → データ収集 → レポート生成 → 品質チェック → PDF納品）
python system_b/process_order.py
```

### System C: 情報収集

```bash
# 日次市場ウォッチ（市場動向 + 法規制チェック）
python system_c/scheduler.py --task daily_watch

# 週次テックトレンド
python system_c/scheduler.py --task weekly_tech

# エリア分析（オンデマンド）
python system_c/scheduler.py --task area_analysis --area "港区赤坂"
```

### System D: 実績発信

```bash
# 実績コンテンツ生成（B/Cの成果をX投稿用に変換）
python system_d/generate_results_content.py

# System Aのスケジュールに統合
python system_d/schedule_results_posts.py
```

### 問い合わせBot

```bash
# ローカル起動
python -m inquiry_bot.server

# ヘルスチェック
python -m inquiry_bot.scheduler health_check

# 日次レポート生成
python -m inquiry_bot.scheduler daily_report
```

### テスト

```bash
python -m pytest tests/ -v
```

---

## cronスケジュール

全タスクはJST（Asia/Tokyo）で実行される。

| 時刻 | 頻度 | タスク | システム |
|------|------|--------|---------|
| 06:00 | 毎日 | デイリーパイプライン（3パイプライン実行 → 品質チェック → 投稿スケジュール） | System A |
| 07:00 | 毎日 | 日次市場ウォッチ（市場動向 + 法規制チェック） | System C |
| 08:00 | 毎週月曜 | 週次テックトレンド収集 | System C |
| 09:00 | 毎週月曜 | 週次パフォーマンス分析 + パイプライン比率自動調整 | System A |
| 19:00 | 毎週金曜 | 実績→X投稿ドラフト生成（問い合わせBot連携） | 問い合わせBot |
| 20:00 | 毎週金曜 | 実績コンテンツ生成 | System D |
| 21:00 | 毎日 | 日次パフォーマンス分析 + 問い合わせBot日次レポート | System A / Bot |
| */5分 | 常時 | 問い合わせBotヘルスチェック | 問い合わせBot |
| 09:00 | 毎週月曜 | FAQ更新提案チェック（低信頼度質問パターン通知） | 問い合わせBot |

---

## システム間データフロー詳細

### System C → System A（データ供給）

```
data/system_c/daily/*.json     → Pipeline 2 がリアルタイムデータとして使用
data/system_c/weekly/*.json    → Pipeline 2 がトレンドデータとして使用
data/system_c/valuations/*.json → Pipeline 2 が市場データとして使用
```

### System C → System B（データ供給）

```
data/system_c/reports/*.json   → 案件処理時のデータソースとして使用
data/system_c/valuations/*.json → 賃料査定・エリア分析の基礎データ
data/system_c/costs/*.json     → リフォーム費用比較の基礎データ
```

### System B → System D（実績データ）

```
data/system_b/deliverables/*.pdf → 納品実績をコンテンツ化
reports/system_b/*.json          → 処理実績サマリー
```

### System D → System A（投稿統合）

```
実績コンテンツ → data/system_a/stock_pool/ に追加
  → PostSelector が通常投稿と混ぜてスケジューリング
```

### 品質チェックログ

```
data/quality_logs/{profile}_{timestamp}_attempt{n}.json
  例: x_post_20260222_072111_attempt1.json
  例: report_20260222_143000_attempt2.json
```

---

## 設定ファイル

主要な設定は `config/config.yaml` で一元管理:

| セクション | 主要パラメータ |
|---|---|
| `general` | タイムゾーン、言語、月間API予算（5万円） |
| `quality_checker` | 使用モデル、リトライ回数、各閾値 |
| `system_a` | 日次投稿数(3)、投稿時刻、パイプライン比率、各パイプライン設定 |
| `system_b` | 自動納品、PDF設定 |
| `system_c` | エージェント並列数(4)、スクレイピングレート制限 |
| `system_d` | 週間実績投稿数(4)、対象柱 |
| `inquiry_bot` | サーバーポート、使用モデル、チャンネル設定 |
