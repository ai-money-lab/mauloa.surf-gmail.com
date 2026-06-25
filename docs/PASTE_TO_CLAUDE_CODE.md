# ═══════════════════════════════════════════════════════════
# Claude Code に以下を丸ごとペーストしてください
# ═══════════════════════════════════════════════════════════
#
# やってほしいこと:
#
# 1. monetize/ai_beauty/characters.yaml の mio を以下の新設計に上書き更新して
# 2. monetize/ai_beauty/prompts.yaml の quality_base を以下に更新して
# 3. docs/CLAUDE_CODE_INSTRUCTIONS.md の顔の設計図とプロンプトを以下に更新して
# 4. 更新後 git commit & push して
#
# ═══════════════════════════════════════════════════════════

## 1. characters.yaml の mio を以下に更新

```yaml
mio:
  name: "Mio"
  name_jp: "ミオ"
  age: 23
  personality: "Sweet and a little playful. Loves matcha and quiet mornings. Seems innocent but has a teasing side. Speaks English with occasional Japanese words mixed in."
  visual:
    ethnicity: "japanese"
    face: "soft oval face with delicate V-line jaw"
    eyes: "large almond-shaped dark brown eyes with slight upward tilt"
    eyebrows: "naturally thick eyebrows with soft arch"
    nose: "small refined nose with gentle bridge"
    lips: "slightly full glossy lips with natural pink tint"
    skin: "luminous fair skin with natural healthy glow"
    hair: "dark brown hair with loose soft waves falling past shoulders"
    body_type: "slim with natural curves, 160cm"
    distinguishing: "subtle beauty mark on right cheekbone"
  default_expression: "gentle half-smile with knowing eyes, soft confident gaze"
  default_style: "casual chic, warm earth tones, cashmere and denim"
  target_audience: "English-speaking men 25-45, interested in Japanese culture"
  niche: "Japanese petite girlfriend experience — cute × alluring fusion"
  differentiator: "English captions with occasional Japanese words. No other AI model does this."
  lora:
    model_path: ""
    weight: 0.7
  ip_adapter:
    reference_image: ""
    weight: 0.8
  platforms:
    fanvue:
      enabled: true
      subscription_price_usd: 9.99
      content_rating: "nsfw"
    x_twitter:
      enabled: true
      handle: ""
      content_rating: "sfw"
    instagram:
      enabled: false
      handle: ""
      content_rating: "sfw"
    fanza:
      enabled: false
      circle_name: ""
      content_rating: "r18"
  hashtags:
    sfw: ["#AIgirl", "#AIbeauty", "#virtualmodel", "#japanesegirl", "#tokyolife"]
    nsfw: ["#exclusive", "#fanvue", "#aigirlfriend"]
```

## 2. prompts.yaml の quality_base を以下に更新

```yaml
quality_base:
  positive_flux: >-
    hyper-realistic, 8K UHD,
    micro-contrast, histogram equalization,
    detailed skin texture with natural pores,
    shallow depth of field
  positive_sdxl: >-
    (8k, RAW photo, best quality, masterpiece:1.2),
    (realistic, photo-realistic:1.4),
    sharp focus, depth of field, film grain,
    professional photography, natural lighting,
    detailed skin texture with natural pores
  negative: >-
    (worst quality:1.4), (low quality:1.4),
    anime, cartoon, 3D CGI, octane render, unreal engine,
    deformed, blurry, bad eyes, asymmetric eyes, cross-eyed,
    bad teeth, bad hands, missing fingers, extra digits,
    plastic skin, airbrushed, doll-like, overly smooth skin,
    watermark, text, logo, signature
```

## 3. 顔ガチャ用プロンプト（100枚回す用）

### FLUX用（ComfyUIにそのまま入れる）

```
Close-up portrait of a 23 year old Japanese woman,
soft oval face with delicate V-line jaw,
large almond-shaped dark brown eyes with slight upward tilt,
naturally thick eyebrows with soft arch,
small refined nose with gentle bridge,
slightly full glossy lips with natural pink tint,
luminous fair skin with natural healthy glow,
dark brown hair with loose soft waves falling past shoulders,
subtle beauty mark on right cheekbone,
expression: gentle half-smile with knowing eyes,
soft confident gaze directly at camera,
shot on Hasselblad X2D, 85mm f/1.4,
studio lighting with soft rim light from behind,
shallow depth of field, neutral grey background,
hyper-realistic, 8K UHD, micro-contrast, histogram equalization
```

### SDXL用（Juggernaut XL / fuduki_mix）

ポジティブ:
```
(8k, RAW photo, best quality, masterpiece:1.2),
(realistic, photo-realistic:1.4),
close-up portrait, 23 year old Japanese woman,
soft oval face, delicate V-line jaw,
large almond-shaped dark brown eyes, slight upward tilt,
naturally thick eyebrows with soft arch,
small refined nose, slightly full glossy pink lips,
luminous fair skin with healthy glow,
dark brown hair with loose soft waves,
subtle beauty mark on right cheekbone,
gentle half-smile with knowing confident eyes,
studio lighting, soft rim light, neutral background,
85mm lens, f/1.4, detailed skin texture, sharp focus
```

ネガティブ:
```
(worst quality:1.4), (low quality:1.4),
anime, cartoon, 3D CGI, octane render, unreal engine,
deformed, blurry, bad eyes, asymmetric eyes, cross-eyed,
bad teeth, bad hands, missing fingers, extra digits,
plastic skin, airbrushed, doll-like, overly smooth skin,
watermark, text, logo, signature
```

### サンプラー設定
- SDXL: DPM++ 2M Karras / 25 steps / CFG 7
- FLUX: Euler / FluxGuidance=2

## 4. SNS投稿用プロンプト（顔確定後に使う）

### カフェ（X朝投稿用）
```
Photo of a 23 year old Japanese woman with dark brown wavy hair,
sitting at a modern Tokyo cafe, wearing cream cashmere sweater,
holding a matcha latte, warm natural smile,
afternoon window light casting soft shadows,
shot on Sony A7R IV, 50mm f/1.8, ISO 200,
shallow depth of field, warm color grading,
candid feel, lifestyle photography, 8K
```

### 街歩き（X昼投稿用）
```
Full body photo of a 23 year old Japanese woman,
dark brown wavy hair, wearing a fitted white t-shirt tucked into
high-waisted jeans and white sneakers,
walking through Shibuya crossing at golden hour,
looking back over shoulder with playful smile,
urban Tokyo background with bokeh lights,
shot on Canon EOS R5, 35mm f/1.4,
street photography style, cinematic color grading
```

### 朝セルフィー（X朝投稿用）
```
Selfie of a 23 year old Japanese woman in bed,
dark brown messy wavy hair, wearing oversized white shirt,
soft morning sunlight from window, sleepy gentle smile,
smartphone POV, warm intimate atmosphere,
natural no-makeup look, pillow visible,
shot on iPhone, natural grain, authentic feel
```

### ビーチ（Fanvueティーザー用）
```
Photo of a 23 year old Japanese woman in a white string bikini,
dark brown wavy hair blowing in ocean breeze,
standing at shoreline during golden hour sunset,
toned slim body with natural curves,
looking at camera with confident subtle smile,
warm golden light on skin, ocean waves behind,
shot on Sony A7R IV, 85mm f/2, ISO 100,
editorial beach photography, cinematic warm tones
```

### ランジェリー（Fanvue限定用）
```
Intimate portrait of a 23 year old Japanese woman
in black lace lingerie, dark brown wavy hair over one shoulder,
sitting on edge of bed, soft warm lamplight from side,
looking at camera with alluring half-smile,
natural body with soft curves, detailed skin texture,
warm intimate bedroom atmosphere,
shot on Sony A7III, 85mm f/1.8,
shallow depth of field, cinematic warm grading
```

### バスルーム（Fanvue PPV用）
```
Photo of a 23 year old Japanese woman wrapped in white towel,
dark brown wet wavy hair, standing in modern bathroom,
soft steam atmosphere, warm overhead lighting,
bare shoulders with water droplets on skin,
playful teasing expression, looking over shoulder,
shot on Hasselblad X2D, 80mm f/2.8,
editorial beauty photography, soft focus
```

## 5. X投稿キャプションテンプレート

朝:
```
Good morning ☀️ just woke up and can't decide what to wear today...
おはよう〜 💕
#AIgirl #goodmorning #virtualmodel
```

昼:
```
Found the cutest cafe in Tokyo 🍰 The matcha latte here is amazing!
What's your favorite drink?
#tokyo #cafe #AIbeauty #japanesegirl
```

夜:
```
Getting ready for a quiet night in... 🌙
Want to see what I'm wearing? Link in bio 💋
#AImodel #exclusive #fanvue
```

## 6. 実行手順

1. まず characters.yaml と prompts.yaml を更新して commit & push
2. FLUX用の顔ガチャプロンプトで100枚生成
3. ベスト1枚を選ぶ（目の対称性・肌質・唇・全体の魅力で判断）
4. 選んだ1枚をPuLID参照画像に設定
5. 5方向（正面・左斜め・右斜め・上から・横顔）の参照画像を生成
6. 20枚のLoRA学習データを作成
7. LoRA学習実行
8. 3層スタック（LoRA + PuLID + ControlNet）でテスト生成10枚
9. 全部同じ人に見えたら、SNS投稿用プロンプトで量産開始
