"""System E — Character-Voice Content Generator.

Generates captions, stories, and engagement posts in the character's voice
using Claude API. All content maintains persona consistency.
"""

import json
import logging
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from core.claude_client import ClaudeClient

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
CONFIG_PATH = Path(__file__).parent / "character_config.yaml"
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
GENERATED_DIR = Path(__file__).parent.parent / "data" / "system_e" / "generated"


def load_character_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


class ContentGenerator:
    """Generate character-consistent text content."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.config = load_character_config()
        self.character = self.config["character"]
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    def _build_system_prompt(self) -> str:
        """Build a system prompt that establishes the character's voice."""
        char = self.character
        voice = char["content_voice"]
        personality = char["personality"]

        return f"""You are ghostwriting social media content as {char['name']}, a {char['age']}-year-old {char['backstory']['career']}.

CHARACTER PROFILE:
- Name: {char['name']}
- Tagline: {char['tagline']}
- Personality: {', '.join(personality['traits'])}
- Quirks: {', '.join(personality['quirks'])}
- Values: {', '.join(personality['values'])}
- Tone: {voice['tone']}
- Catchphrase: {voice['catchphrase']}
- Backstory: {char['backstory']['origin']}. {char['backstory']['motivation']}.

CONTENT RULES:
- Write in first person as {char['name']}
- Primary language: English (occasional Japanese phrases OK for flavor)
- Never mention being AI in the content itself (disclosed in bio per FTC rules)
- Stay within approved topics: {', '.join(voice['topics'])}
- NEVER discuss: {', '.join(voice['banned_topics'])}
- Keep it authentic — share struggles too, not just highlights
- Use data/science references when relevant (fits the nerdy personality)
- Tone: warm, encouraging, slightly geeky — NEVER preachy or salesy"""

    def generate_caption(
        self,
        scene: str,
        image_description: str = "",
        content_type: str = "standard",
    ) -> dict:
        """Generate a caption for an image post.

        Args:
            scene: The scene category (e.g., 'morning_routine', 'workout').
            image_description: Description of what's in the image.
            content_type: One of 'standard', 'story', 'engagement', 'promo'.

        Returns:
            Dict with 'text', 'hashtags', 'type', 'scene'.
        """
        type_instructions = {
            "standard": (
                "Write a short, engaging X/Twitter post (max 250 chars). "
                "Share a genuine thought, tip, or moment. Natural and conversational."
            ),
            "story": (
                "Write a mini-story or personal anecdote (max 280 chars). "
                "Something relatable that makes people feel connected. "
                "Can be a small win, a funny moment, or a lesson learned."
            ),
            "engagement": (
                "Write a post that encourages replies (max 250 chars). "
                "Ask a question, run a poll setup, or invite opinions. "
                "Make it easy and fun to respond to."
            ),
            "promo": (
                "Write a soft promotional post (max 280 chars). "
                "Mention a product/service naturally as something you genuinely use. "
                "Never hard-sell. Focus on personal experience and results."
            ),
        }

        instruction = type_instructions.get(content_type, type_instructions["standard"])

        prompt = f"""{instruction}

Scene: {scene}
Image shows: {image_description or 'Character in ' + scene + ' setting'}

Return a JSON object with:
- "text": the post text (no hashtags in text)
- "hashtags": array of 1 most relevant hashtag (without # symbol)

JSON only, no explanation."""

        try:
            result = self.claude.generate_json(
                prompt=prompt,
                system=self._build_system_prompt(),
                max_tokens=512,
                temperature=0.8,
            )
            result["type"] = content_type
            result["scene"] = scene
            result["generated_at"] = datetime.now(JST).isoformat()
            return result
        except Exception as e:
            logger.error("Caption generation failed: %s", e)
            return {
                "text": "",
                "hashtags": [],
                "type": content_type,
                "scene": scene,
                "error": str(e),
            }

    # Fallback polls when Claude API is unavailable
    FALLBACK_POLLS = [
        {
            "text": "What's your go-to way to de-stress after a long day?",
            "options": ["Workout", "Meditation", "Walk in nature", "Hot bath"],
        },
        {
            "text": "Morning workout or evening workout — which team are you?",
            "options": ["Morning", "Evening", "Whenever I can", "Rest day"],
        },
        {
            "text": "How many hours of sleep did you get last night?",
            "options": ["Less than 6", "6-7 hours", "7-8 hours", "8+ hours"],
        },
        {
            "text": "What's your biggest wellness struggle right now?",
            "options": ["Consistency", "Motivation", "Time management", "Nutrition"],
        },
        {
            "text": "Do you track your fitness data?",
            "options": ["Obsessively", "Sometimes", "Just started", "Nope"],
        },
    ]

    def generate_poll(self, topic: str = "") -> dict:
        """Generate a poll post. Polls get highest engagement on X."""
        prompt = f"""Create a fun, engaging poll for X/Twitter about wellness or fitness.
{f'Topic hint: {topic}' if topic else 'Pick a relevant wellness/fitness topic.'}

Rules:
- Question should be conversational and easy to engage with
- 2-4 poll options, each max 25 characters
- Question max 200 characters
- Make it feel authentic, not corporate

Return a JSON object with:
- "text": the poll question
- "options": array of 2-4 poll option strings

JSON only, no explanation."""

        try:
            result = self.claude.generate_json(
                prompt=prompt,
                system=self._build_system_prompt(),
                max_tokens=512,
                temperature=0.9,
            )
            # Validate and constrain options
            options = result.get("options", [])[:4]
            if len(options) < 2:
                raise ValueError("Too few poll options returned")
            result["options"] = [opt[:25] for opt in options]
            result["duration_minutes"] = 1440  # 24 hours
            result["type"] = "poll"
            result["generated_at"] = datetime.now(JST).isoformat()
            return result
        except Exception as e:
            logger.error("Poll generation failed, using fallback: %s", e)
            fallback = random.choice(self.FALLBACK_POLLS).copy()
            fallback["duration_minutes"] = 1440
            fallback["type"] = "poll"
            fallback["generated_at"] = datetime.now(JST).isoformat()
            return fallback

    def generate_thread(self, topic: str, num_tweets: int = 4) -> dict:
        """Generate a thread of tweets on a topic.

        Args:
            topic: The topic to write about.
            num_tweets: Number of tweets in the thread (3-7).

        Returns:
            Dict with 'tweets' (list of strings), 'topic', 'hashtags'.
        """
        num_tweets = max(3, min(7, num_tweets))

        prompt = f"""Write a {num_tweets}-tweet thread about: {topic}

Rules:
- Tweet 1: Hook that makes people want to read the thread
- Tweets 2-{num_tweets-1}: Valuable content, tips, or insights
- Tweet {num_tweets}: Summary + call to engage (question or invitation)
- Each tweet max 270 chars (leave room for numbering)
- Use data/science when relevant

Return a JSON object with:
- "tweets": array of tweet texts (without numbering — I'll add that)
- "hashtags": array of 1 most relevant hashtag for the first tweet (without # symbol)
- "hook_quality": rate 1-10 how attention-grabbing the first tweet is

JSON only, no explanation."""

        try:
            result = self.claude.generate_json(
                prompt=prompt,
                system=self._build_system_prompt(),
                max_tokens=2048,
                temperature=0.8,
            )
            result["type"] = "thread"
            result["topic"] = topic
            result["generated_at"] = datetime.now(JST).isoformat()
            return result
        except Exception as e:
            logger.error("Thread generation failed: %s", e)
            return {"tweets": [], "type": "thread", "topic": topic, "error": str(e)}

    def generate_daily_content_plan(self, date: str | None = None) -> list[dict]:
        """Generate a full day's content plan.

        Creates a mix of content types optimized for multi-timezone posting.

        Args:
            date: Target date (YYYY-MM-DD). Defaults to tomorrow.

        Returns:
            List of content items with posting times and types.
        """
        if not date:
            tomorrow = datetime.now(JST) + timedelta(days=1)
            date = tomorrow.strftime("%Y-%m-%d")

        # Determine day-of-month for alternating poll/engagement at noon
        day_of_month = int(date.split("-")[2])
        noon_type = "poll" if day_of_month % 2 == 1 else "engagement"

        # Content mix optimized for reach:
        # - Threads get 40-60% more impressions than standalone posts
        # - Polls get highest impressions on X
        content_plan = [
            {"time_jst": "07:00", "type": "standard", "scene": "morning_routine",
             "note": "Asia peak - morning ritual content"},
            {"time_jst": "12:00", "type": noon_type, "scene": "lifestyle",
             "note": f"Asia lunch - {'poll (odd day)' if noon_type == 'poll' else 'engagement (even day)'}"},
            {"time_jst": "19:00", "type": "thread", "scene": self._pick_scene(),
             "note": "EU morning + Asia evening - thread for 40-60% more reach"},
            {"time_jst": "23:00", "type": "story", "scene": self._pick_scene(),
             "note": "US West morning - story content"},
        ]

        # Generate content for each slot
        results = []
        for slot in content_plan:
            logger.info("Generating content for %s %s (%s)", date, slot["time_jst"], slot["type"])

            if slot["type"] == "poll":
                content = self.generate_poll()
            elif slot["type"] == "thread":
                content = self.generate_thread(topic=slot["scene"])
            else:
                content = self.generate_caption(
                    scene=slot["scene"],
                    content_type=slot["type"],
                )

            content["scheduled_date"] = date
            content["scheduled_time_jst"] = slot["time_jst"]
            content["note"] = slot["note"]
            results.append(content)

        # Save plan
        plan_file = GENERATED_DIR / f"content_plan_{date}.json"
        plan_file.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Content plan saved: %s (%d items)", plan_file, len(results))

        return results

    def _pick_scene(self) -> str:
        """Pick a random scene weighted by frequency config."""
        scenes = self.config["image_generation"].get("scene_categories", {})
        freq_weights = {
            "daily": 7,
            "3x_weekly": 3,
            "2x_weekly": 2,
            "weekly": 1,
        }
        weighted = []
        for name, cfg in scenes.items():
            freq = cfg.get("frequency", "weekly")
            weight = freq_weights.get(freq, 1)
            weighted.extend([name] * weight)
        return random.choice(weighted) if weighted else "lifestyle"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    gen = ContentGenerator()
    plan = gen.generate_daily_content_plan()
    for item in plan:
        print(f"[{item.get('scheduled_time_jst')}] {item.get('type')}: {item.get('text', '')[:80]}")
