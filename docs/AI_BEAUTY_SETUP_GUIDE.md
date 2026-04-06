# AI美女マネタイズ — セットアップ＆運用ガイド
# 作成日: 2026-04-06
# PCスペック: i9-14900KF / 96GB RAM / RTX 5070 Ti 16GB / CORSAIR RM1000e 1000W

---

## Phase 0: PC組み立て後の初期セットアップ

### 0-1. Windows初期設定
```
1. Windows 11 インストール（USBから）
2. NVIDIAドライバ最新版をインストール
   https://www.nvidia.co.jp/Download/index.aspx?lang=jp
3. CUDA Toolkit インストール（12.x系最新）
   https://developer.nvidia.com/cuda-downloads
4. Python 3.11+ インストール
   https://www.python.org/downloads/
5. Git インストール
   https://git-scm.com/downloads
6. Bun インストール（nano-banana用）
   https://bun.sh
```

### 0-2. GPU動作確認
```powershell
nvidia-smi
# → RTX 5070 Ti が認識され、VRAM 16GB と表示されればOK

python -c "import torch; print(torch.cuda.get_device_name(0))"
# → NVIDIA GeForce RTX 5070 Ti
```

---

## Phase 1: ComfyUI環境構築（Day 1 午前）

### 1-1. ComfyUIインストール
```
1. https://www.comfy.org からWindows版をダウンロード
2. 解凍して任意のフォルダに配置（例: D:\ComfyUI）
3. 起動: run_nvidia_gpu.bat をダブルクリック
4. ブラウザで http://127.0.0.1:8188 を開く
```

### 1-2. モデルダウンロード（優先度順）

#### 必須モデル（Day 1に全部入れる）

| モデル | 配置先 | ダウンロード元 |
|---|---|---|
| **FLUX 2 Dev** | `models/diffusion_models/` | https://huggingface.co/black-forest-labs/FLUX.2-dev |
| **FLUX t5xxl テキストエンコーダ** | `models/text_encoders/` | HuggingFace（FLUX 2に同梱） |
| **FLUX clip_l** | `models/text_encoders/` | HuggingFace（FLUX 2に同梱） |
| **FLUX VAE** | `models/vae/` | HuggingFace（FLUX 2に同梱） |
| **Juggernaut XL Ragnarok** | `models/checkpoints/` | https://civitai.com/models/133005/juggernaut-xl |
| **CHROMA v.48** | `models/diffusion_models/` | https://huggingface.co/lodestones/Chroma |
| **RealVisXL V4.0** | `models/checkpoints/` | https://civitai.com/models/139562 |
| **majicFlus**（アジア美女特化） | `models/checkpoints/` | CivitAIで検索 |
| **fuduki_mix**（日本人特化） | `models/checkpoints/` | CivitAIで検索 |

#### アップスケーラー

| モデル | 配置先 |
|---|---|
| **4x-UltraSharp** | `models/upscale_models/` |
| **Real-ESRGAN x4** | `models/upscale_models/` |
| **4x_NMKD-Siax_200k** | `models/upscale_models/` |

#### キャラ一貫性モデル

| モデル | 配置先 |
|---|---|
| **PuLID** | `models/pulid/` |
| **IP-Adapter FaceID Plus v2** | `models/ipadapter/` |
| **InsightFace** | `models/insightface/` |
| **ControlNet OpenPose（SDXL用）** | `models/controlnet/` |

### 1-3. ComfyUI カスタムノード（必須）
```
ComfyUI Manager から以下をインストール:

- ComfyUI-Impact-Pack（FaceDetailer等）
- ComfyUI-PuLID
- ComfyUI-IPAdapter-Plus
- ComfyUI-ControlNet-Auxiliary
- ComfyUI-Batch-Process
- ComfyUI-KJNodes（ユーティリティ）
- efficiency-nodes-comfyui
```

---

## Phase 2: キャラクター作成（Day 1 午後）

### 2-1. Claudeへの指示

```
このプロジェクトのリポジトリを開いて:

「monetize/ai_beauty/characters.yaml のMioのビジュアル設定を確認して」
「ComfyUIでMioの顔を生成して、参照画像として保存して」
```

### 2-2. 参照画像の作成手順

```
1. ComfyUIでFLUX 2 Dev を使って「理想の顔」を1枚生成
   プロンプト例:
   "Portrait of a 24 year old Japanese woman with long straight black hair,
    dark brown eyes, small mole under left eye, gentle smile,
    shot on Sony A7R IV, 85mm f/1.8, studio lighting, 8K"

2. 気に入った顔が出たら保存（これが「Mioの顔」になる）

3. その顔を基に、以下の差分で15-30枚生成:
   - 正面/左斜め/右斜め/横顔
   - 笑顔/真顔/驚き/上目遣い
   - 室内/屋外/異なる照明
   - 上半身/バストアップ/全身

4. 生成した画像を data/ai_beauty/training/mio/ に保存
```

### 2-3. IP-Adapter参照画像の設定

```
Claudeへの指示:
「Mioの参照画像を data/ai_beauty/references/mio_face.png に設定して」

→ characters.yaml の ip_adapter.reference_image が更新される
```

### 2-4. LoRA学習（15-30枚揃ったら）

```powershell
# Kohya-ss をインストール
git clone https://github.com/kohya-ss/sd-scripts
cd sd-scripts
pip install -r requirements.txt

# SDXL LoRA学習（推奨設定）
accelerate launch train_network.py \
  --pretrained_model_name_or_path="juggernaut_xl_ragnarok.safetensors" \
  --train_data_dir="data/ai_beauty/training/mio" \
  --output_dir="data/ai_beauty/loras" \
  --output_name="mio_v1" \
  --network_module=networks.lora \
  --network_dim=128 \
  --network_alpha=64 \
  --learning_rate=1e-4 \
  --max_train_epochs=10 \
  --optimizer_type="adafactor" \
  --mixed_precision="bf16" \
  --resolution=1024 \
  --enable_bucket

# FLUX LoRA学習（FLUXで使う場合）
# network_dim=128, alpha=128, steps=1500-2500
# learning_rate=1e-4, scheduler=cosine, optimizer=AdamW8bit
```

Claudeへの指示:
```
「MioのLoRAパスを data/ai_beauty/loras/mio_v1.safetensors に設定して」
```

---

## Phase 3: コンテンツ量産開始（Day 2〜）

### 3-1. SNS投稿用コンテンツ（SFW）

Claudeへの指示:
```
「Mioのカフェ写真を5枚生成して」
「Mioのストリートスナップを4枚作って」
「Mioの朝のセルフィーを3枚」
「Mioのオフィスコーデを4枚」
```

### 3-2. Fanvue用コンテンツ（NSFW含む）

Claudeへの指示:
```
「Fanvue用のビキニセットを10枚作って」
「Fanvue用のランジェリーセットを8枚」
「FanvuePPV用のプレミアムセット15枚」
```

### 3-3. FANZA CG集（R18）

Claudeへの指示:
```
「FANZA用CG集をOLシチュで50枚作って」
「FANZA用の表紙候補を3枚生成して」
```

### 3-4. バッチ処理（大量生成）

```python
# ComfyUI APIでの大量生成（Claudeに依頼するか、直接実行）
# monetize/ai_beauty/pipeline.py の ContentPipeline を使用

from monetize.ai_beauty.pipeline import ContentPipeline

pipeline = ContentPipeline()

# Fanvue用に一括生成
result = pipeline.generate_fanvue_set("mio", theme="bikini", count=20)
print(f"生成完了: {result['output_dir']}")
```

---

## Phase 4: プラットフォーム開設（Day 2〜3）

### 4-1. X（Twitter）

```
1. アカウント作成（キャラ名で）
2. プロフィール画像・ヘッダー画像を設定（ComfyUIで生成）
3. 自己紹介文にFanvueリンクを入れる
4. 初期投稿: 自己紹介 + 最高品質の画像4枚ギャラリー

Claudeへの指示:
「MioのX投稿用キャプションを10本生成して。日本語と英語で」
```

### 4-2. Instagram

```
1. ビジネスアカウントで作成
2. 9枚のグリッド投稿を先に用意（プロフィール画面の見栄え）
3. Reels用の短尺動画（Wan2.2で生成）

Claudeへの指示:
「MioのInstagram用ハッシュタグセットを作って。英語と日本語で」
```

### 4-3. Fanvue

```
1. https://www.fanvue.com でクリエイター登録
2. プロフィール設定（AIクリエイターとして）
3. サブスク価格設定: $9.99/月（初期）
4. 初期コンテンツ20投稿をアップロード
5. PPV（$5〜$25）を設定

Claudeへの指示:
「Fanvue用のプロフィール文を英語で書いて。Mioのペルソナに合わせて」
```

### 4-4. FANZA同人

```
1. https://www.dmm.co.jp/dc/doujin/ でサークル登録
2. サークル名を決定
3. 第1作CG集を投稿（50枚 + 表紙 + 紹介文）
4. 価格: ¥770〜¥990
5. タグ: AI生成（必須）+ ジャンルタグ

Claudeへの指示:
「FANZA用の作品紹介文を書いて。OLシチュのCG集50枚」
```

---

## Phase 5: 週間運用ルーティン

### 投稿スケジュール（Claudeに作らせる）

```
Claudeへの指示:
「MioのX投稿スケジュールを今週分作って」
「MioのFanvue投稿スケジュールを作って」
「今日のタスクを見せて」
```

### 日次タスク（毎日30分〜1時間）

| 時間 | タスク |
|---|---|
| 朝 | Xに朝の投稿（セルフィー系） |
| 昼 | Xに昼の投稿（お出かけ系） |
| 夜 | Xに夜の投稿（リラックス系）+ Fanvueに新コンテンツ |

### 週次タスク

| 曜日 | タスク |
|---|---|
| 月曜 | 週間コンテンツを一括生成（20〜30枚） |
| 水曜 | Fanvue PPV用プレミアムセット作成 |
| 金曜 | パフォーマンス分析 → 来週の計画調整 |
| 土曜 | FANZA CG集の制作（月1〜2本ペース） |

---

## Phase 6: 収益目標

| 期間 | Fanvue | FANZA | SNS | 合計目安 |
|---|---|---|---|---|
| 1ヶ月目 | $0〜$200 | ¥0 | フォロワー構築 | ¥0〜30,000 |
| 3ヶ月目 | $500〜$2,000 | ¥20,000〜50,000 | — | ¥100,000〜350,000 |
| 6ヶ月目 | $2,000〜$5,000 | ¥50,000〜100,000 | ブランド案件？ | ¥350,000〜850,000 |
| 12ヶ月目 | $5,000〜$20,000 | カタログ収益 | $500〜$5,000 | ¥800,000〜3,000,000+ |

---

## 技術スタック早見表

| 用途 | ツール/モデル |
|---|---|
| **UI** | ComfyUI |
| **SFWフォトリアル** | FLUX 2 Dev + RealismLoRA |
| **NSFW** | CHROMA v.48 |
| **SDXL汎用** | Juggernaut XL Ragnarok |
| **日本人特化** | fuduki_mix / majicFlus |
| **顔の一貫性** | PuLID（5枚参照）+ カスタムLoRA |
| **ポーズ制御** | ControlNet OpenPose |
| **アップスケール** | SUPIR → 4x-UltraSharp（2段階） |
| **バッチ生成** | ComfyUI API + Python |
| **LoRA学習** | Kohya-ss / Ostris AI Toolkit |

---

## 最強プロンプト早見表

### FLUX用（短い自然文がベスト）

```
Portrait of a 24 year old Japanese woman with long straight black hair,
[シチュエーション: sitting at a sunlit cafe / walking on urban street / etc],
[服装: cream knit sweater / white summer dress / bikini / etc],
[表情: gentle smile / shy expression / confident look],
shot on Sony A7R IV, 85mm f/1.8, ISO 100,
shallow depth of field, [照明: golden hour / studio lighting / rim lighting],
hyper-realistic, 8K UHD
```

### SDXL用（品質トークン重視）

```
(8k, RAW photo, best quality, masterpiece:1.2),
(realistic, photo-realistic:1.4),
[キャラビジュアル], [シチュエーション], [服装],
[表情], professional photography, 85mm lens, f/1.8,
shallow depth of field, [照明], detailed skin texture,
natural makeup, film grain
```

### ネガティブ（SDXL共通）

```
(worst quality:1.4), (low quality:1.4),
anime, cartoon, octane render, 3D CGI, unreal engine,
deformed, blurry, watermark, bad hands, missing fingers,
extra digits, oversaturated, plastic skin, airbrushed, doll-like
```

### サンプラー設定

| モデル | サンプラー | ステップ | CFG |
|---|---|---|---|
| SDXL | DPM++ 2M Karras | 25 | 7 |
| FLUX 2 | Euler | — | FluxGuidance=2 |

---

## トラブルシューティング

| 問題 | 対処 |
|---|---|
| ComfyUIが起動しない | Python/CUDAバージョン確認。RTX 5070 Ti対応パッチ適用 |
| FLUX生成が遅い | FP8量子化を有効に（40%高速化） |
| 手が崩れる | ControlNet OpenPose + FaceDetailerで修正 |
| キャラの顔がブレる | PuLID強度を0.8→0.9に。参照画像を5枚に増やす |
| VRAM不足エラー | FP8量子化 or バッチサイズを1に |
| nano-banana 403エラー | `/setup-vertex-ai` を実行 |

---

## Claudeへの翌日最初の指示

```
このリポジトリのコードベースを把握して。
docs/AI_BEAUTY_SETUP_GUIDE.md を読んで、Phase 1から順番に進めて。
まずComfyUIの環境構築から始めよう。
```
