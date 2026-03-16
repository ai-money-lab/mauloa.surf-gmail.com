"""Realistic portrait prompt templates for Gemini Imagen (Nano Banana 2).

AI-generated images tend to look too perfect — flawless skin, ideal lighting,
and symmetrical composition. These prompts deliberately introduce natural
imperfections to produce smartphone-quality photos that feel authentic.

Key anti-AI techniques used:
- Specify "smartphone photo" or "iPhone selfie" to get casual composition
- Add slight imperfections: uneven lighting, natural skin texture, stray hair
- Use "no airbrushing, no smoothing" to preserve skin detail
- Mention specific camera artifacts: slight grain, soft focus edges
- Include environmental context for realism (messy room, real furniture)
"""

# ── 10 realistic portrait prompt templates ─────────────────
# Each prompt is designed to minimize AI-like artifacts.
# Use {aspect} placeholder for aspect ratio instruction.
# Use {extra} placeholder for optional additional details.

PORTRAIT_PROMPTS: list[dict[str, str]] = [
    {
        "id": "bedroom_morning",
        "name": "朝のベッドルーム",
        "prompt": (
            "Vertical portrait image ({aspect}). "
            "Photorealistic smartphone photo of a super cute Japanese woman "
            "in her 20s sitting on a white bed inside her bedroom at home. "
            "She has light ash brown shoulder-length hair with airy bangs, "
            "clear radiant skin with visible pores and natural skin texture, "
            "and gentle glossy lips. "
            "She wears a soft beige sports bra and rests her hands on the bed "
            "while leaning forward slightly in a cute pose. "
            "Bright natural indoor daylight from a window. "
            "Simple background without posters, photos, or books. "
            "Shot on iPhone 15, slight lens distortion at edges, "
            "no airbrushing, no skin smoothing, natural shadows under chin. "
            "A few stray hairs catching the light. {extra}"
        ),
    },
    {
        "id": "mirror_selfie",
        "name": "鏡越しセルフィー",
        "prompt": (
            "Vertical portrait image ({aspect}). "
            "Photorealistic mirror selfie taken with iPhone by a cute Japanese "
            "woman in her early 20s in a small apartment bathroom. "
            "She holds the phone at chest level, slightly tilted. "
            "Wearing an oversized white t-shirt, messy bun hairstyle with "
            "loose strands framing her face. "
            "Warm tungsten bathroom lighting, slight mirror smudges visible. "
            "Natural skin texture, tiny beauty mark near lip, "
            "no makeup or very minimal makeup. "
            "Phone flash reflection visible in mirror. "
            "Slightly cluttered bathroom counter in background. "
            "Casual, unposed feel. Shot on smartphone. {extra}"
        ),
    },
    {
        "id": "cafe_window",
        "name": "カフェの窓際",
        "prompt": (
            "Vertical portrait image ({aspect}). "
            "Candid smartphone photo of a pretty Japanese woman in her 20s "
            "sitting by a window at a small cozy cafe. "
            "She has dark brown medium-length hair, slightly messy from wind. "
            "Wearing a cream knit cardigan over a simple white camisole. "
            "Soft natural window light illuminating one side of her face, "
            "the other side in gentle shadow. "
            "She is looking slightly away from camera with a soft smile. "
            "A coffee cup and phone on the wooden table. "
            "Background slightly out of focus with warm cafe ambiance. "
            "Natural skin with subtle under-eye shadows, real skin texture. "
            "Shot on smartphone, slight color cast from window light. {extra}"
        ),
    },
    {
        "id": "night_room",
        "name": "夜の部屋・間接照明",
        "prompt": (
            "Vertical portrait image ({aspect}). "
            "Photorealistic smartphone photo of a cute Japanese woman in her "
            "20s lying on her stomach on a bed at night. "
            "Room lit only by a warm-toned bedside lamp and phone screen glow. "
            "She has shoulder-length black hair spread on the pillow, "
            "wearing a thin-strap camisole. "
            "Looking at camera with a sleepy, relaxed expression. "
            "Warm orange-tinted lighting, visible noise and grain from low "
            "light smartphone photography. "
            "Slightly underexposed, natural shadows. "
            "Wrinkled bedsheets, a book and phone charger nearby. "
            "Real skin texture visible, slight redness on cheeks. "
            "No retouching, no airbrushing. {extra}"
        ),
    },
    {
        "id": "outdoor_golden_hour",
        "name": "夕方の外・ゴールデンアワー",
        "prompt": (
            "Vertical portrait image ({aspect}). "
            "Photorealistic smartphone photo of a beautiful Japanese woman "
            "in her 20s standing on a quiet residential street during golden "
            "hour sunset. "
            "She has caramel brown layered hair blowing slightly in the breeze. "
            "Wearing a simple white blouse and denim skirt. "
            "Warm golden sunlight hitting her face from the side, "
            "creating natural lens flare and warm color cast. "
            "She is mid-laugh, eyes slightly squinted from the sun. "
            "Slightly blown-out highlights on hair edges. "
            "Background shows blurred houses and power lines. "
            "Natural perspiration on skin, visible arm hair in sunlight. "
            "Shot on iPhone, auto-exposure slightly off. {extra}"
        ),
    },
    {
        "id": "post_shower",
        "name": "お風呂上がり",
        "prompt": (
            "Vertical portrait image ({aspect}). "
            "Photorealistic smartphone photo of a cute Japanese woman in her "
            "20s just after a shower, sitting on the edge of a bathtub. "
            "She has wet dark hair clinging to her neck and shoulders, "
            "wearing a bath towel wrapped around her body. "
            "Slightly flushed skin from hot water, water droplets on "
            "collarbones and shoulders. "
            "Steamy bathroom atmosphere, foggy mirror in background. "
            "Warm overhead lighting, slightly humid lens effect. "
            "She is looking at camera with a natural relaxed smile. "
            "Real skin texture, visible tiny moles, no airbrushing. "
            "Casual bathroom items visible in background. "
            "Shot on smartphone with slight moisture on lens. {extra}"
        ),
    },
    {
        "id": "workout_gym",
        "name": "ジム・運動後",
        "prompt": (
            "Vertical portrait image ({aspect}). "
            "Photorealistic smartphone selfie of a fit Japanese woman in her "
            "20s at a small home gym or workout space. "
            "She has her hair in a high ponytail, stray baby hairs around "
            "her forehead, slightly sweaty. "
            "Wearing a black sports bra and grey leggings. "
            "Flushed cheeks, slight perspiration on forehead and chest. "
            "Harsh overhead fluorescent lighting creating unflattering but "
            "realistic shadows. "
            "She is taking the selfie with one hand, other hand on hip. "
            "Yoga mat and water bottle visible on floor. "
            "Natural skin texture, visible veins on arms, real muscle tone. "
            "Slightly grainy image from indoor lighting. {extra}"
        ),
    },
    {
        "id": "lazy_couch",
        "name": "ソファでだらだら",
        "prompt": (
            "Vertical portrait image ({aspect}). "
            "Photorealistic smartphone photo taken from above of a cute "
            "Japanese woman in her 20s lying on a grey fabric sofa. "
            "She has natural black hair fanned out, wearing an oversized "
            "pastel hoodie and shorts. "
            "She is looking up at the camera with a playful pouty expression. "
            "Natural afternoon light from a nearby window, "
            "TV remote and snack wrapper visible on the sofa. "
            "Slightly double chin from the angle (natural for looking up). "
            "No makeup, natural eyebrows, slight dark circles under eyes. "
            "Real skin texture with natural unevenness. "
            "Cozy messy living room background. "
            "Shot on smartphone from arm's length above. {extra}"
        ),
    },
    {
        "id": "summer_balcony",
        "name": "夏のベランダ",
        "prompt": (
            "Vertical portrait image ({aspect}). "
            "Photorealistic smartphone photo of a pretty Japanese woman in "
            "her 20s sitting on a small apartment balcony on a summer evening. "
            "She has medium-length brown hair with subtle highlights, "
            "wearing a thin white tank top. "
            "Warm evening light mixed with cool blue twilight sky. "
            "She is holding a can of chuhai and looking at camera with a "
            "relaxed tipsy smile. "
            "Slight tan lines visible on shoulders. "
            "Laundry hanging in the background, potted plant on railing. "
            "Natural skin with slight sunburn on nose and cheeks. "
            "Visible arm hair and natural body details. "
            "Smartphone photo quality with slight warm color grading. {extra}"
        ),
    },
    {
        "id": "desk_study",
        "name": "デスクで作業中",
        "prompt": (
            "Vertical portrait image ({aspect}). "
            "Photorealistic smartphone photo of a cute Japanese woman in her "
            "20s sitting at a messy desk studying or working on a laptop. "
            "She has glasses pushed up on her head, brown hair in a loose "
            "low ponytail with pieces falling out. "
            "Wearing a thin long-sleeve thermal top. "
            "Blue-white laptop screen light mixed with warm desk lamp. "
            "She just looked up at camera with a tired but cute half-smile. "
            "Slight bags under eyes, natural skin redness around nose. "
            "Coffee mug, scattered papers, phone with cracked screen protector "
            "on desk. "
            "Real skin texture, no retouching, natural indoor mixed lighting. "
            "Shot on smartphone, slightly warm white balance. {extra}"
        ),
    },
]


def get_prompt(prompt_id: str, aspect: str = "3:4", extra: str = "") -> str:
    """Get a formatted prompt by ID.

    Args:
        prompt_id: One of the prompt template IDs (e.g. 'bedroom_morning').
        aspect: Aspect ratio string (e.g. '3:4', '9:16', '16:9').
        extra: Additional instructions to append.

    Returns:
        The formatted prompt string.

    Raises:
        KeyError: If prompt_id is not found.
    """
    for p in PORTRAIT_PROMPTS:
        if p["id"] == prompt_id:
            return p["prompt"].format(aspect=aspect, extra=extra)
    raise KeyError(f"Prompt ID '{prompt_id}' not found. Available: {[p['id'] for p in PORTRAIT_PROMPTS]}")


def list_prompts() -> list[dict[str, str]]:
    """Return a summary list of all available prompts."""
    return [{"id": p["id"], "name": p["name"]} for p in PORTRAIT_PROMPTS]
