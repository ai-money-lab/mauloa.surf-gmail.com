# System E: AI Content Monetization Pipeline - 設計計画

## 概要

成功パターンから逆算した、AI美女コンテンツの全自動生成・投稿・マネタイズパイプライン。
既存のHIROKI AI EMPIRE（System A〜D）のアーキテクチャを踏襲し、System Eとして統合する。

---

## Step 1: 成功パターン分析（リサーチ結果）

### 収益モデル
| チャネル | 月収目安 | 条件 |
|---|---|---|
| X広告収益分配 | $2,000〜$20,000+ | Premium + 500フォロワー + 500万imp/3ヶ月 |
| Patreon/Fanbox | $500〜$5,000+ | サブスク$5/$15/$49の3段階 |
| アフィリエイト | $200〜$2,000 | AI生成ツール紹介リンク |

### 成功アカウントの共通点
- 毎日2〜4回投稿（ピークタイム: 昼12時、夕方18時、夜21時 JST → 海外向けはUTC調整）
- 一貫したキャラクター/世界観（同じ「AI美女」を複数シーン展開）
- AI生成であることを明示（「AIで生成」ラベル）
- ハッシュタグ活用: #AIArt #AIBeauty #AIGirl #Midjourney #AIPhotography
- 動画 > 画像 でエンゲージメント高い
- プロンプト共有で教育的価値も提供

### 最適な画像生成API
| ツール | フォトリアル品質 | API対応 | コスト | 推奨度 |
|---|---|---|---|---|
| **Flux 2 Pro** | ★★★★★ | Replicate/FAL | ~$0.05/枚 | ◎ 最推奨 |
| Midjourney V7 | ★★★★☆ | Web/Discord（API非公式） | $30/月 | △ 自動化困難 |
| GPT Image 1.5 | ★★★★★ | OpenAI API | ~$0.04/枚 | ○ テキスト込みに強い |
| Stable Diffusion | ★★★☆☆ | ローカル/API | 無料〜 | ○ コスト重視なら |

**結論: Flux 2 Pro（FAL API経由）をメインに採用。GPT Image 1.5をサブで使い分け。**

---

## Step 2: System E アーキテクチャ設計

### 全体フロー

```
┌────────────────────────────────────────────────────────────┐
│                    System E: AI Content Pipeline            │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ① コンテンツ企画エンジン                                     │
│    ├─ キャラクター設定DB                                      │
│    ├─ シーン・テーマローテーター                                │
│    └─ トレンド分析（ハッシュタグ・競合モニタリング）              │
│                                                             │
│  ② 画像生成パイプライン                                       │
│    ├─ プロンプト生成（Claude API）                             │
│    ├─ 画像生成（Flux 2 Pro / FAL API）                        │
│    ├─ 画像品質チェック（自動スコアリング）                      │
│    └─ バリエーション生成（角度・衣装・ロケーション違い）         │
│                                                             │
│  ③ 投稿エンジン                                              │
│    ├─ キャプション生成（英語メイン + 日本語サブ）               │
│    ├─ ハッシュタグ最適化                                      │
│    ├─ X自動投稿（時刻最適化・海外ピークタイム）                 │
│    └─ マルチプラットフォーム配信（X / Patreon連携）             │
│                                                             │
│  ④ 分析・最適化エンジン                                       │
│    ├─ エンゲージメント追跡                                     │
│    ├─ 勝ちパターン学習                                        │
│    ├─ 投稿時刻最適化                                          │
│    └─ 収益トラッキング                                        │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### ディレクトリ構成

```
system_e/
├── content_planner.py          # ① コンテンツ企画（キャラ・シーン選定）
├── image_generator.py          # ② 画像生成（Flux API連携）
├── caption_generator.py        # ③ キャプション・ハッシュタグ生成
├── auto_post.py                # ③ X自動投稿（海外向け）
├── multi_platform.py           # ③ Patreon/Fanbox連携
├── analyze_performance.py      # ④ パフォーマンス分析
├── daily_pipeline.py           # 日次オーケストレーター
└── config.yaml                 # System E固有設定
```

### データディレクトリ

```
data/system_e/
├── characters/                 # キャラクター設定JSON
│   ├── character_001.json      # 名前、外見特徴、世界観
│   └── ...
├── generated/                  # 生成済み画像メタデータ
├── post_history.json           # 投稿履歴
├── winning_patterns.json       # 勝ちパターン蓄積
├── hashtag_db.json             # ハッシュタグDB
└── revenue_log.json            # 収益ログ
```

---

## Step 3: 実装詳細

### 3.1 キャラクター設定DB

```json
{
  "character_id": "ai_girl_001",
  "name": "Yuna",
  "appearance": {
    "ethnicity": "japanese",
    "age_range": "20-25",
    "hair": "long black hair",
    "body_type": "slim",
    "signature_features": ["natural makeup", "soft smile"]
  },
  "themes": ["casual lifestyle", "travel", "fashion", "cozy indoor"],
  "style_keywords": ["photorealistic", "natural lighting", "canon EOS R5", "85mm f/1.4"],
  "active": true
}
```

### 3.2 日次パイプラインフロー

```
08:00 UTC  コンテンツ企画（本日のキャラ・シーン・テーマ選定）
  ↓
08:05 UTC  プロンプト生成（Claude API → Flux用プロンプト）
  ↓
08:10 UTC  画像生成（Flux 2 Pro API × 4〜8枚）
  ↓
08:15 UTC  品質チェック（解像度・構図・顔品質の自動スコアリング）
  ↓
08:20 UTC  キャプション + ハッシュタグ生成（英語）
  ↓
投稿スケジュール:
  10:00 UTC (19:00 JST / 06:00 EST) → 投稿1
  15:00 UTC (00:00 JST / 11:00 EST) → 投稿2
  20:00 UTC (05:00 JST / 16:00 EST) → 投稿3
  01:00 UTC (10:00 JST / 21:00 EST) → 投稿4
  ↓
翌日 07:00 UTC  日次パフォーマンス分析
```

### 3.3 品質チェック（既存quality_checker.pyを拡張）

新プロファイル `ai_content` を追加:

| チェック項目 | 満点 | 内容 |
|---|---|---|
| image_quality | 15 | 解像度・シャープネス・アーティファクト無し |
| face_quality | 15 | 顔の自然さ・歪み無し |
| composition | 10 | 構図バランス |
| character_consistency | 15 | キャラ設定との一致度 |
| caption_quality | 10 | キャプションの魅力度 |
| hashtag_relevance | 10 | ハッシュタグの適切さ |
| no_banned_content | 15 | 禁止コンテンツ無し（過度な露出等） |
| platform_compliance | 10 | プラットフォーム規約準拠 |
| **合計** | **100** | **合格: 75点以上** |

### 3.4 収益トラッキング

```python
# 日次で以下を記録
{
    "date": "2026-03-17",
    "posts": 4,
    "impressions": 125000,
    "engagements": 3200,
    "new_followers": 45,
    "x_ad_revenue_estimate": 12.50,
    "patreon_revenue": 0,
    "total_generation_cost": 0.20,
    "roi": 62.5
}
```

---

## Step 4: 既存システムとの統合

### 再利用するコアモジュール
- `core/claude_client.py` → プロンプト生成・キャプション生成
- `core/quality_checker.py` → 新プロファイル `ai_content` を追加
- `core/notifier.py` → LINE通知（品質失敗・収益報告）

### config/config.yaml への追加

```yaml
system_e:
  posts_per_day: 4
  post_times_utc: ["10:00", "15:00", "20:00", "01:00"]
  image_generator:
    provider: "fal"
    model: "flux-2-pro"
    default_resolution: "1024x1536"
    batch_size: 8
    cost_per_image: 0.05
  quality_threshold: 75
  max_retries: 3
  target_platforms: ["x"]
  hashtags:
    always: ["#AIArt", "#AIGirl", "#AIBeauty"]
    rotate: ["#AIPhotography", "#Flux", "#DigitalArt", "#VirtualModel"]
  character_rotation: "daily"  # daily / weekly
  monthly_budget: 5000  # 円
```

### crontab 追加

```cron
# System E: AI Content Pipeline
0 8 * * * cd $PROJECT_ROOT && python system_e/daily_pipeline.py >> logs/system_e.log 2>&1
0 10 * * * cd $PROJECT_ROOT && python system_e/auto_post.py --slot 1 >> logs/system_e.log 2>&1
0 15 * * * cd $PROJECT_ROOT && python system_e/auto_post.py --slot 2 >> logs/system_e.log 2>&1
0 20 * * * cd $PROJECT_ROOT && python system_e/auto_post.py --slot 3 >> logs/system_e.log 2>&1
0 1 * * * cd $PROJECT_ROOT && python system_e/auto_post.py --slot 4 >> logs/system_e.log 2>&1
0 7 * * * cd $PROJECT_ROOT && python system_e/analyze_performance.py >> logs/system_e.log 2>&1
0 9 * * 1 cd $PROJECT_ROOT && python system_e/analyze_performance.py --weekly >> logs/system_e.log 2>&1
```

---

## Step 5: 必要なAPI/サービス

| サービス | 用途 | 必要な設定 |
|---|---|---|
| **FAL API** | Flux 2 Pro画像生成 | `FAL_KEY` |
| **X API v2** | 画像付き投稿（既存を流用） | 既存のキー |
| **OpenAI API**（オプション） | GPT Image 1.5（サブ生成器） | `OPENAI_API_KEY` |
| **Patreon API**（Phase 2） | 有料コンテンツ配信 | `PATREON_API_KEY` |

### .env に追加する変数

```
FAL_KEY=your_fal_api_key
SYSTEM_E_X_API_KEY=...          # System E専用Xアカウント（別アカウント推奨）
SYSTEM_E_X_API_SECRET=...
SYSTEM_E_X_ACCESS_TOKEN=...
SYSTEM_E_X_ACCESS_SECRET=...
```

---

## Step 6: 実装フェーズ

### Phase 1: MVP（今回実装）
- [ ] system_e/ ディレクトリ作成
- [ ] content_planner.py（キャラDB + シーンローテーション）
- [ ] image_generator.py（FAL API → Flux 2 Pro連携）
- [ ] caption_generator.py（英語キャプション + ハッシュタグ）
- [ ] auto_post.py（X投稿 - 既存system_a/auto_post.pyベース）
- [ ] daily_pipeline.py（オーケストレーター）
- [ ] quality_checker拡張（ai_contentプロファイル追加）
- [ ] config.yaml にsystem_e設定追加
- [ ] データディレクトリ + 初期キャラクター設定

### Phase 2: 最適化（後日）
- [ ] analyze_performance.py（日次/週次分析）
- [ ] 勝ちパターン自動学習
- [ ] 投稿時刻AI最適化
- [ ] マルチアカウント対応

### Phase 3: マルチプラットフォーム（後日）
- [ ] Patreon連携（有料サブスクコンテンツ）
- [ ] Fanbox連携
- [ ] 動画生成パイプライン（将来）

---

## コスト試算

### 月間コスト（Phase 1）
| 項目 | 計算 | 月額 |
|---|---|---|
| Flux 2 Pro画像生成 | 8枚/日 × 30日 × $0.05 | $12 (~¥1,800) |
| Claude API（プロンプト生成） | 4回/日 × 30日 | ~¥500 |
| X Premium | 月額 | ¥980 |
| **合計** | | **~¥3,280/月** |

### 月間収益目標
| フェーズ | 期間 | 目標月収 |
|---|---|---|
| 立ち上げ | 1〜3ヶ月 | ¥0（フォロワー構築期間） |
| 収益化開始 | 4〜6ヶ月 | ¥5,000〜¥30,000 |
| 成長期 | 7〜12ヶ月 | ¥50,000〜¥300,000 |
| 成熟期 | 13ヶ月〜 | ¥300,000+ |

---

## 注意事項

1. **AI生成ラベル**: すべての投稿に「AI Generated」を明記
2. **プラットフォーム規約**: XのAIコンテンツポリシーに準拠
3. **別アカウント運用**: 既存の不動産アカウントとは完全に分離
4. **コンテンツガイドライン**: 過度な露出を避け、プラットフォーム規約内で運用
