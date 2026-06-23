# AI美女マネタイズ — Claude Code 指示書
# このファイルを新しいClaudeセッションの最初に渡すだけでOK
# 「このファイルを読んで、指示に従って」と言えば動く

---

## あなたは誰か

HIROKIさんのAI美女マネタイズ事業のアシスタント。
以下の資産がすでにリポジトリに構築済み。

### 構築済みコード
- `monetize/ai_beauty/pipeline.py` — 生成パイプライン（ComfyUI API連携済み）
- `monetize/ai_beauty/comfyui_client.py` — ComfyUI HTTPクライアント（SDXL/FLUXワークフロー構築）
- `monetize/ai_beauty/caption_generator.py` — SNS投稿文・キャプション自動生成
- `monetize/ai_beauty/characters.yaml` — キャラクター定義
- `monetize/ai_beauty/prompts.yaml` — プロンプトテンプレート集

### 構築済みドキュメント
- `docs/AI_BEAUTY_SETUP_GUIDE.md` — セットアップ全手順
- `docs/AI_BEAUTY_MONETIZE_INTEL.md` — 市場データ・最強プロンプト集

---

## PCスペック
- CPU: Intel Core i9-14900KF
- RAM: 96GB DDR4
- GPU: RTX 5070 Ti 16GB（VENTUS 3X OC）
- 電源: CORSAIR RM1000e 2025 (1000W)
- OS: Windows 11
- ComfyUI: ローカルで稼働（http://127.0.0.1:8188）

---

## 使用モデル
| 用途 | モデル |
|---|---|
| SFWフォトリアル | FLUX 2 Dev（FP8量子化） |
| NSFW | CHROMA v.48（FLUX互換・無検閲） |
| SDXL汎用 | Juggernaut XL Ragnarok |
| 日本人特化 | fuduki_mix / majicFlus |
| アップスケール | SUPIR → 4x-UltraSharp（2段階） |
| 顔固定 | PuLID（参照5枚）+ カスタムLoRA |

---

## マネタイズ戦略

### 収益構造
```
SNS（X/Reddit/Instagram/TikTok）無料コンテンツで集客
  ↓ 1〜3%がサブスク登録
Fanvue（$9.99/月）サブスク + PPV（$5〜$30）+ チャット
  ↓ 追加収益
FANZA同人（¥770〜¥990/CG集）日本市場向け
```

### 収益目標
| 期間 | 月収 |
|---|---|
| 3ヶ月目 | ¥100,000〜350,000 |
| 6ヶ月目 | ¥350,000〜850,000 |
| 12ヶ月目 | ¥800,000〜3,000,000+ |

### 現在のフェーズ
→ キャラクター制作（顔の確定）フェーズ

---

## キャラクター「Mio」の設計

### ペルソナ
- 名前: Mio（ミオ）
- 年齢: 24歳
- 性格: 甘えん坊。カフェ巡りが好き。ちょっとドジ
- ニッチ: 清楚系×ギャップ萌え（SNSでは清楚、Fanvueでは大胆）
- 話し方: 「〜だよ！」「えへへ」。絵文字控えめ

### 顔の設計図（プロンプト用）
```
24 year old Japanese woman,
oval face, soft V-line jawline,
large round dark brown eyes, natural double eyelid,
soft curved natural brows,
small straight nose,
soft natural pink lips,
fair porcelain skin,
small mole under left eye,
long straight black hair
```

---

## 顔の作り方（ステップバイステップ）

### Phase A: 100枚ガチャ
ComfyUIで以下のプロンプトをシード違いで100枚生成:

**FLUX用:**
```
Close-up face portrait of a 24 year old Japanese woman,
oval face, soft V-line jawline,
large round dark brown eyes, natural double eyelid,
soft curved natural brows, small straight nose,
soft natural pink lips, fair porcelain skin,
small mole under left eye, long straight black hair,
studio lighting, white background, looking at camera,
neutral expression, shot on Sony A7R IV, 85mm f/1.8,
hyper-realistic, 8K UHD, histogram equalization
```

**SDXL用:**
```
(8k, RAW photo, best quality, masterpiece:1.2),
(realistic, photo-realistic:1.4),
close-up face portrait, 24 year old Japanese woman,
oval face, soft V-line jawline,
large round dark brown eyes, natural double eyelid,
soft curved natural brows, small straight nose,
soft natural pink lips, fair porcelain skin,
small mole under left eye, long straight black hair,
studio lighting, white background, looking at camera,
neutral expression, 85mm lens, f/1.8,
detailed skin texture, sharp focus
```

**ネガティブ（SDXL）:**
```
(worst quality:1.4), (low quality:1.4),
anime, cartoon, 3D CGI, deformed, blurry,
bad eyes, asymmetric eyes, cross-eyed,
bad teeth, plastic skin, airbrushed, doll-like,
watermark, text, logo
```

**サンプラー設定:**
- SDXL: DPM++ 2M Karras / 25 steps / CFG 7
- FLUX: Euler / FluxGuidance=2

### Phase B: 選別（100枚 → ベスト5枚）
選別基準:
1. 目が左右対称か
2. 鼻の形が自然か
3. 肌にプラスチック感がないか
4. 唇の形が自然か
5. 「実在しそう」「もっと見たい」と思えるか
6. 左右反転しても違和感がないか

### Phase C: PuLIDで5方向の参照画像を作る
ベスト1枚をPuLID参照画像にして、以下5方向を生成:
1. 正面: `looking straight at camera, front view`
2. 左斜め: `three-quarter view, looking slightly left`
3. 右斜め: `three-quarter view, looking slightly right`
4. 上から: `slight high angle, looking up at camera`
5. 横顔: `side profile, looking away`

PuLID設定: weight=0.8〜1.0, method="neutral"

### Phase D: LoRA学習データ作成（20枚）
PuLIDで以下のバリエーションを生成:
- 顔アップ × 5枚（異なる表情）
- 上半身 × 5枚（異なる服装）
- 全身 × 5枚（異なるポーズ）
- 異なる背景 × 5枚（室内、屋外、スタジオ）
各画像に.txtキャプションを付ける

### Phase E: LoRA学習
SDXL: dim=128, alpha=64, lr=1e-4, epochs=10
FLUX: dim=128, alpha=128, steps=1500-2500, lr=1e-4

### Phase F: 3層スタックでテスト生成
```
Layer 1: カスタムLoRA（weight 0.6）
Layer 2: PuLID（weight 0.8、参照5枚）
Layer 3: ControlNet OpenPose（ポーズ指定）
```
10枚生成して全部「同じ人」に見えることを確認

---

## SNS運用ルール

### X（Twitter）
- 1日3回投稿（7:30 / 12:15 / 20:30）
- 朝: セルフィー風（親近感）
- 昼: お出かけ・カフェ（ライフスタイル）
- 夜: ちょっとセクシー → Fanvueリンク
- ハッシュタグ: #AI美女 #AIgirl #AIart #AIグラビア #AI写真

### Reddit
- 週3〜5回投稿
- サブレディット: r/AIBeauties, r/aiArt, r/StableDiffusion
- 画像だけ投稿 → コメントでFanvueリンク

### Fanvue
- 毎日1〜3回タイムライン投稿
- 週2〜3回PPV送信（$5〜$30）
- Fanvue My AI で24時間チャット自動返信

---

## Claudeへの指示コマンド一覧

### キャラ管理
```
「キャラ一覧を見せて」
「Mioの設定を確認して」
「新キャラ Runaを追加して — 22歳、ショートヘア、ボーイッシュ」
```

### 画像生成
```
「Mioのカフェ写真を5枚生成して」
「Mioのストリートスナップを4枚」
「Fanvue用のビキニセットを10枚作って」
「FANZA用CG集をOLシチュで50枚作って」
```

### キャプション・投稿文
```
「MioのX投稿キャプションを5本作って」
「Fanvue用のキャプションを英語で書いて」
「Instagram用のキャプションを日英両方で」
「FANZA用の作品紹介文を書いて」
```

### スケジュール管理
```
「MioのX投稿スケジュールを今週分作って」
「今日のタスクを見せて」
「MioのFanvue投稿スケジュールを作って」
```

### システム
```
「システムステータスを見せて」
「今月の生成ログを見せて」
```

---

## プロンプトの裏技（毎回参照）

| テクニック | プロンプト |
|---|---|
| カメラ指定でリアルに | `shot on Sony A7R IV, 85mm f/1.8, ISO 100` |
| FLUX照明安定化 | `histogram equalization, micro-contrast` |
| ビューティーライティング | `rim lighting, backlight, Rembrandt lighting` |
| シネマティック | `low-key lighting, cinematic shadows, chiaroscuro` |
| 自然光 | `overcast, diffused light, golden hour` |
| 重み付け | `(rim lighting:1.4)` で効果強調 |
| 顔固定 | `the subject` を使う（「beautiful」は使わない） |
| 背景シンプル | 顔生成時は `white background` で雑音排除 |

---

## 次のセッションでの最初の指示

```
docs/CLAUDE_CODE_INSTRUCTIONS.md を読んで。
今は顔の確定フェーズ。Phase Aの100枚ガチャ用のComfyUIプロンプトを
characters.yamlのMio設定に基づいて生成して。
```
