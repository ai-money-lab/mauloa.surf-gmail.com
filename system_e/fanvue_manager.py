"""System E — Fanvue Content Manager.

Manages content creation and organization for Fanvue subscription platform.
Separates content into tiers (free, basic, premium, VIP).
Includes auto-scheduling, upsell triggers, drip campaigns, content recycling,
revenue tracking, and content calendar generation.
"""

import calendar
import json
import logging
import random
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import yaml

from core.claude_client import ClaudeClient

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
CONFIG_PATH = Path(__file__).parent / "character_config.yaml"
FANVUE_DIR = Path(__file__).parent.parent / "data" / "system_e" / "fanvue"


def load_character_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


class FanvueManager:
    """Manage content pipeline for Fanvue subscription tiers."""

    def __init__(self):
        self.claude = ClaudeClient()
        self.config = load_character_config()
        self.tiers = self.config["monetization"]["fanvue_tiers"]
        FANVUE_DIR.mkdir(parents=True, exist_ok=True)

    def categorize_content(self, image_path: str, scene: str) -> str:
        """Determine which Fanvue tier an image belongs to.

        Args:
            image_path: Path to the generated image.
            scene: Scene category used for generation.

        Returns:
            Tier name: 'free', 'basic', 'premium', or 'vip'.
        """
        # Tier logic based on scene exclusivity
        premium_scenes = {"studio", "workout"}
        basic_scenes = {"morning_routine", "outdoor", "lifestyle"}

        if scene in premium_scenes:
            return "premium"
        elif scene in basic_scenes:
            return "basic"
        return "free"

    def prepare_fanvue_post(
        self,
        image_path: str,
        scene: str,
        caption: str = "",
    ) -> dict:
        """Prepare a content item for Fanvue posting.

        Args:
            image_path: Path to the image file.
            scene: Scene category.
            caption: Optional caption (will generate one if empty).

        Returns:
            Dict with all info needed to post to Fanvue.
        """
        tier = self.categorize_content(image_path, scene)

        if not caption:
            caption = self._generate_fanvue_caption(scene, tier)

        # Ensure AI disclosure is present in every Fanvue post
        ai_marker = "AI-generated"
        if ai_marker.lower() not in caption.lower():
            caption = f"{caption}\n🤖 {ai_marker} content"

        post = {
            "image_path": image_path,
            "caption": caption,
            "tier": tier,
            "scene": scene,
            "created_at": datetime.now(JST).isoformat(),
            "status": "ready",
        }

        # Save to queue
        self._add_to_queue(post)
        return post

    def _generate_fanvue_caption(self, scene: str, tier: str) -> str:
        """Generate a Fanvue-appropriate caption.

        Fanvue captions are more personal/exclusive than X posts.
        """
        char = self.config["character"]

        tier_vibes = {
            "free": "casual preview that teases exclusive content",
            "basic": "personal and behind-the-scenes, like talking to a close friend",
            "premium": "exclusive and intimate, sharing something special",
            "vip": "very personal, like a private message to your closest supporter",
        }

        vibe = tier_vibes.get(tier, tier_vibes["basic"])

        prompt = f"""Write a short Fanvue caption (2-3 sentences, max 200 chars) for a {scene} photo.

Vibe: {vibe}
Tier: {tier} ({"free — visible to everyone" if tier == "free" else f"${self.tiers[tier]['price']}/month subscribers only"})

Make it feel exclusive and personal.
End with: "🤖 AI-generated content"
Return just the caption text, nothing else."""

        try:
            system = (
                f"You are {char['name']}, {char['tagline']}. "
                f"Personality: {', '.join(char['personality']['traits'])}. "
                f"Write as yourself in first person."
            )
            return self.claude.generate(
                prompt=prompt,
                system=system,
                max_tokens=256,
                temperature=0.8,
            ).strip().strip('"')
        except Exception as e:
            logger.error("Fanvue caption generation failed: %s", e)
            return f"New {scene} content just dropped! ✨ 🤖 AI-generated content"

    def _add_to_queue(self, post: dict) -> None:
        """Add a post to the Fanvue posting queue."""
        queue_file = FANVUE_DIR / "posting_queue.json"
        existing = []
        if queue_file.exists():
            try:
                existing = json.loads(queue_file.read_text(encoding="utf-8"))
            except Exception:
                existing = []

        existing.append(post)
        queue_file.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Added to Fanvue queue: tier=%s, scene=%s", post["tier"], post["scene"])

    def get_queue(self, tier: str | None = None) -> list[dict]:
        """Get pending Fanvue posts, optionally filtered by tier."""
        queue_file = FANVUE_DIR / "posting_queue.json"
        if not queue_file.exists():
            return []

        try:
            queue = json.loads(queue_file.read_text(encoding="utf-8"))
        except Exception:
            return []

        if tier:
            return [p for p in queue if p.get("tier") == tier and p.get("status") == "ready"]
        return [p for p in queue if p.get("status") == "ready"]

    def mark_posted(self, index: int) -> None:
        """Mark a queue item as posted."""
        queue_file = FANVUE_DIR / "posting_queue.json"
        if not queue_file.exists():
            return

        queue = json.loads(queue_file.read_text(encoding="utf-8"))
        if 0 <= index < len(queue):
            queue[index]["status"] = "posted"
            queue[index]["posted_at"] = datetime.now(JST).isoformat()
            queue_file.write_text(
                json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    def get_tier_stats(self) -> dict:
        """Get content statistics per tier."""
        queue_file = FANVUE_DIR / "posting_queue.json"
        if not queue_file.exists():
            return {}

        try:
            queue = json.loads(queue_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

        stats = {}
        for item in queue:
            tier = item.get("tier", "unknown")
            status = item.get("status", "unknown")
            if tier not in stats:
                stats[tier] = {"ready": 0, "posted": 0}
            stats[tier][status] = stats[tier].get(status, 0) + 1

        return stats


    # ─── Auto-Scheduling ───

    # Optimal Fanvue posting hours (JST).  Fanvue subscribers are most active
    # in the evening / late-night JST window, which overlaps with US mornings.
    FANVUE_OPTIMAL_HOURS: dict[str, list[int]] = {
        "weekday": [12, 19, 21, 23],
        "weekend": [10, 14, 20, 22],
    }

    WEEKLY_TIER_TARGETS: dict[str, int] = {
        "free": 3,
        "basic": 5,
        "premium": 3,
        "vip": 1,
    }

    def schedule_weekly_content(
        self,
        start_date: datetime | None = None,
        available_content: list[dict] | None = None,
    ) -> dict:
        """Plan a full week of Fanvue posts balanced across tiers.

        Ensures tier balance (free 3/week, basic 5/week, premium 3/week,
        vip 1/week) and assigns optimal posting times that differ from the
        X schedule.

        Args:
            start_date: Monday of the target week.  Defaults to the coming
                Monday in JST.
            available_content: Optional list of content dicts (must contain
                at least ``tier``).  When provided the scheduler matches
                items from this pool first; remaining slots are left as
                placeholders.  When *None* the method pulls from the
                existing posting queue.

        Returns:
            Schedule dict persisted to
            ``data/system_e/fanvue/weekly_schedule.json``.
        """
        now = datetime.now(JST)

        if start_date is None:
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            start_date = now.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=days_until_monday)

        # Build a content pool — either from the caller or from the queue
        if available_content is not None:
            content_pool = list(available_content)
        else:
            content_pool = []
            for tier in self.WEEKLY_TIER_TARGETS:
                content_pool.extend(self.get_queue(tier=tier))

        # Create tier-aware slot list and shuffle for variety
        tier_slots: list[str] = []
        for tier, count in self.WEEKLY_TIER_TARGETS.items():
            tier_slots.extend([tier] * count)
        random.shuffle(tier_slots)

        posts: list[dict] = []
        for idx, tier in enumerate(tier_slots):
            day_offset = idx % 7
            post_date = start_date + timedelta(days=day_offset)
            is_weekend = post_date.weekday() >= 5
            hours = self.FANVUE_OPTIMAL_HOURS[
                "weekend" if is_weekend else "weekday"
            ]
            hour = hours[idx % len(hours)]
            minute = random.randint(0, 45)
            scheduled_time = post_date.replace(hour=hour, minute=minute)

            # Match content from pool by tier
            matched: dict | None = None
            for i, item in enumerate(content_pool):
                if item.get("tier") == tier:
                    matched = content_pool.pop(i)
                    break

            posts.append({
                "id": str(uuid.uuid4())[:8],
                "tier": tier,
                "scheduled_at": scheduled_time.isoformat(),
                "day_of_week": calendar.day_name[scheduled_time.weekday()],
                "image_path": matched.get("image_path") if matched else None,
                "caption": matched.get("caption") if matched else None,
                "scene": matched.get("scene") if matched else None,
                "status": "scheduled",
            })

        posts.sort(key=lambda p: p["scheduled_at"])

        schedule = {
            "week_start": start_date.strftime("%Y-%m-%d"),
            "created_at": now.isoformat(),
            "total_posts": len(posts),
            "tier_breakdown": {
                t: sum(1 for p in posts if p["tier"] == t)
                for t in self.WEEKLY_TIER_TARGETS
            },
            "posts": posts,
        }

        schedule_file = FANVUE_DIR / "weekly_schedule.json"
        schedule_file.write_text(
            json.dumps(schedule, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(
            "Weekly schedule created: %d posts from %s",
            len(posts),
            start_date.strftime("%Y-%m-%d"),
        )
        return schedule

    # ─── Upsell Triggers ───

    UPSELL_TEMPLATES: dict[str, list[str]] = {
        "free_to_basic": [
            "Loved this? There's a whole set from today's shoot — just for subscribers. 💫",
            "This is the preview… the full story is on the other side. 🤍",
            "I share so much more behind the curtain. Come hang out?",
        ],
        "basic_to_premium": [
            "Premium members got the full workout plan that goes with this — just saying. 😉",
            "If you want the deep-dive version, premium is where I go all out.",
            "I did a Q&A about this topic for premium members this week — it got real.",
        ],
        "premium_to_vip": [
            "VIP members got a personal voice note about this today. ✨",
            "Want to request what I cover next? That's a VIP perk.",
        ],
    }

    def generate_upsell_trigger(
        self,
        current_tier: str,
        content_context: str = "",
    ) -> dict[str, Any]:
        """Generate a natural upsell message that fits Riena's personality.

        After free content, auto-generates a teaser hinting at basic tier.
        After basic content, occasionally hints at premium value.  Messages
        are warm and conversational, never pushy.

        Args:
            current_tier: The tier the viewer is currently on.
            content_context: Optional description of the content just viewed,
                used to make AI-generated upsells more relevant.

        Returns:
            Dict with ``trigger_id``, ``message``, ``current_tier``,
            ``target_tier``, and ``created_at``.  Returns a dict with
            ``message: None`` when the viewer is already VIP.
        """
        tier_ladder = {"free": "basic", "basic": "premium", "premium": "vip"}
        target_tier = tier_ladder.get(current_tier)
        if target_tier is None:
            return {
                "trigger_id": None,
                "message": None,
                "current_tier": current_tier,
                "target_tier": None,
                "reason": "already_top_tier",
            }

        upsell_key = f"{current_tier}_to_{target_tier}"
        templates = self.UPSELL_TEMPLATES.get(upsell_key, [])

        target_info = self.tiers.get(target_tier, {})
        price = target_info.get("price", 0)
        char = self.config["character"]

        # Attempt AI-generated message when context is provided
        message: str | None = None
        if content_context:
            try:
                prompt = (
                    f"Write a single short upsell message (1-2 sentences, max 160 chars) "
                    f"from Riena hinting that the {target_tier} tier (${price}/mo) has "
                    f"even more value related to: {content_context}. "
                    f"Be natural, warm, never pushy. No hashtags. Return only the message."
                )
                system = (
                    f"You are {char['name']}, {char['tagline']}. "
                    f"Personality: {', '.join(char['personality']['traits'][:3])}. "
                    f"Write casually in first person."
                )
                message = self.claude.generate(
                    prompt=prompt,
                    system=system,
                    max_tokens=128,
                    temperature=0.8,
                ).strip().strip('"')
            except Exception as e:
                logger.warning("AI upsell generation failed, using template: %s", e)

        if not message and templates:
            message = random.choice(templates)
        elif not message:
            message = f"Want more like this? Check out the {target_tier} tier. 🤍"

        trigger_id = str(uuid.uuid4())[:8]
        result: dict[str, Any] = {
            "trigger_id": trigger_id,
            "message": message,
            "current_tier": current_tier,
            "target_tier": target_tier,
            "target_price": price,
            "created_at": datetime.now(JST).isoformat(),
        }

        # Persist for conversion tracking
        self._record_upsell_event(result)
        return result

    def _record_upsell_event(self, trigger: dict) -> None:
        """Append an upsell trigger event for later conversion analysis."""
        tracking_file = FANVUE_DIR / "upsell_tracking.json"
        events: list[dict] = []
        if tracking_file.exists():
            try:
                events = json.loads(tracking_file.read_text(encoding="utf-8"))
            except Exception:
                events = []

        events.append({**trigger, "converted": False})
        tracking_file.write_text(
            json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def record_upsell_conversion(self, trigger_id: str) -> bool:
        """Mark an upsell trigger as converted (subscriber upgraded).

        Args:
            trigger_id: The ``trigger_id`` returned by
                :meth:`generate_upsell_trigger`.

        Returns:
            True if the trigger was found and updated.
        """
        tracking_file = FANVUE_DIR / "upsell_tracking.json"
        if not tracking_file.exists():
            return False

        events = json.loads(tracking_file.read_text(encoding="utf-8"))
        found = False
        for event in events:
            if event.get("trigger_id") == trigger_id:
                event["converted"] = True
                event["converted_at"] = datetime.now(JST).isoformat()
                found = True
                break

        if found:
            tracking_file.write_text(
                json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            logger.info("Upsell conversion recorded: %s", trigger_id)
        return found

    def get_upsell_conversion_rates(self) -> dict[str, Any]:
        """Calculate upsell conversion rates grouped by tier transition.

        Returns:
            Dict mapping transition keys (e.g. ``free->basic``) to
            ``{"total": int, "converted": int, "rate": float}``.
        """
        tracking_file = FANVUE_DIR / "upsell_tracking.json"
        if not tracking_file.exists():
            return {}

        try:
            events = json.loads(tracking_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

        stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "converted": 0}
        )
        for ev in events:
            key = f"{ev.get('current_tier', '?')}->{ev.get('target_tier', '?')}"
            stats[key]["total"] += 1
            if ev.get("converted"):
                stats[key]["converted"] += 1

        return {
            k: {
                **v,
                "rate": round(v["converted"] / v["total"], 4) if v["total"] else 0.0,
            }
            for k, v in stats.items()
        }

    # ─── Drip Campaign ───

    DRIP_SEQUENCES: dict[str, list[dict[str, Any]]] = {
        "welcome": [
            {
                "day": 1,
                "message": (
                    "Hey! So glad you're here. 🤍 I'm Riena — I share real wellness "
                    "tips, workouts, and the messy behind-the-scenes of building "
                    "healthy habits. Welcome to the inner circle."
                ),
                "purpose": "warm_welcome",
            },
            {
                "day": 3,
                "message": (
                    "Quick question — what's one wellness goal you're working on "
                    "right now? I love knowing what matters to the people here. "
                    "No wrong answers. 🧡"
                ),
                "purpose": "engagement",
            },
            {
                "day": 7,
                "message": (
                    "It's been a week since you joined! Here's something I only "
                    "share with subscribers — my actual weekly meal prep list. "
                    "Messy but real. Let me know if you try any of it. "
                    "🤖 AI-generated content"
                ),
                "purpose": "value_delivery",
            },
        ],
        "re_engagement": [
            {
                "day": 0,
                "message": (
                    "Hey, it's been a minute! No pressure at all — just wanted to "
                    "say I posted some new stuff I think you'd really like. "
                    "Hope you're doing well. 🤍"
                ),
                "purpose": "soft_reminder",
            },
        ],
        "tier_upgrade": [
            {
                "day": 0,
                "message": (
                    "I've noticed you really engage with the workout content — love "
                    "that! Just FYI, premium members get my full weekly workout plans "
                    "and form videos. No pressure, just thought you'd want to know. ✨"
                ),
                "purpose": "upgrade_nudge",
            },
        ],
    }

    def _load_drip_state(self) -> dict[str, Any]:
        """Load the drip campaign state from disk."""
        state_file = FANVUE_DIR / "drip_state.json"
        if state_file.exists():
            try:
                return json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"subscribers": {}}

    def _save_drip_state(self, state: dict[str, Any]) -> None:
        """Persist drip campaign state."""
        state_file = FANVUE_DIR / "drip_state.json"
        state_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def run_drip_campaign(
        self,
        subscriber_list: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute pending drip-campaign actions for all subscribers.

        Handles three sequences:

        * **Welcome** — Day 1, 3, 7 messages for new subscribers.
        * **Re-engagement** — Gentle nudge for subscribers inactive 7+ days.
        * **Tier upgrade** — After 14+ days of engagement, nudge free/basic
          subscribers toward the next tier.

        Args:
            subscriber_list: Current subscriber data.  Each dict should
                contain ``id``, ``tier``, ``subscribed_at`` (ISO datetime),
                and ``last_interaction`` (ISO datetime or *None*).
                When *None* the method operates only on subscribers already
                present in the persisted drip state.

        Returns:
            List of message action dicts ready to be sent, each with
            ``subscriber_id``, ``message``, ``sequence``, and ``purpose``.
        """
        state = self._load_drip_state()
        now = datetime.now(JST)
        actions: list[dict[str, Any]] = []

        # Merge explicit subscriber list into state
        if subscriber_list:
            for sub in subscriber_list:
                sub_id = str(sub["id"])
                if sub_id not in state["subscribers"]:
                    state["subscribers"][sub_id] = {
                        "joined": sub.get("subscribed_at"),
                        "tier": sub.get("tier", "free"),
                        "drip_sent": [],
                        "last_active": sub.get("last_interaction"),
                        "re_engagement_sent": False,
                        "tier_upgrade_sent": False,
                    }
                else:
                    # Update mutable fields
                    state["subscribers"][sub_id]["tier"] = sub.get("tier", "free")
                    state["subscribers"][sub_id]["last_active"] = sub.get(
                        "last_interaction"
                    )

        for sub_id, sub_data in state["subscribers"].items():
            join_date = sub_data.get("joined")
            if not join_date:
                continue
            try:
                joined = datetime.fromisoformat(join_date)
                days_since_sub = (now - joined).days
            except (ValueError, TypeError):
                continue

            tier = sub_data.get("tier", "free")
            sent = sub_data.get("drip_sent", [])

            # --- Welcome sequence ---
            for step in self.DRIP_SEQUENCES["welcome"]:
                if days_since_sub >= step["day"] and step["day"] not in sent:
                    actions.append({
                        "subscriber_id": sub_id,
                        "sequence": "welcome",
                        "type": "welcome",
                        "day": step["day"],
                        "message": step["message"],
                        "purpose": step["purpose"],
                        "scheduled_at": now.isoformat(),
                    })
                    sent.append(step["day"])

            # --- Re-engagement (7+ days inactive) ---
            last_active_raw = sub_data.get("last_active")
            if last_active_raw:
                try:
                    last_active = datetime.fromisoformat(last_active_raw)
                    inactive_days = (now - last_active).days

                    if (
                        inactive_days >= 7
                        and not sub_data.get("re_engagement_sent")
                    ):
                        step = self.DRIP_SEQUENCES["re_engagement"][0]
                        actions.append({
                            "subscriber_id": sub_id,
                            "sequence": "re_engagement",
                            "type": "reengagement",
                            "message": step["message"],
                            "purpose": step["purpose"],
                            "scheduled_at": now.isoformat(),
                        })
                        sub_data["re_engagement_sent"] = True

                    # Reset flag once they come back (active within last 3 days)
                    if inactive_days < 3:
                        sub_data["re_engagement_sent"] = False
                except (ValueError, TypeError):
                    pass

            # --- Tier upgrade nudge (14+ days, free or basic only) ---
            if (
                days_since_sub >= 14
                and tier in ("free", "basic")
                and not sub_data.get("tier_upgrade_sent")
            ):
                step = self.DRIP_SEQUENCES["tier_upgrade"][0]
                actions.append({
                    "subscriber_id": sub_id,
                    "sequence": "tier_upgrade",
                    "type": "tier_upgrade",
                    "message": step["message"],
                    "purpose": step["purpose"],
                    "scheduled_at": now.isoformat(),
                })
                sub_data["tier_upgrade_sent"] = True

            sub_data["drip_sent"] = sent

        self._save_drip_state(state)
        logger.info("Drip campaign: %d actions for %d subscribers",
                     len(actions), len(state["subscribers"]))
        return actions

    # ─── Content Recycling ───

    RECYCLING_FRAMINGS: list[str] = [
        "extended cut",
        "behind the scenes",
        "the full story",
        "unfiltered version",
        "subscriber-only deep dive",
    ]

    def recycle_top_content(
        self,
        x_posts: list[dict],
        limit: int = 5,
        engagement_key: str | None = None,
    ) -> list[dict]:
        """Identify top-performing X content and reframe it for Fanvue.

        Ranks source posts by engagement, then generates exclusive Fanvue
        captions with an *extended cut* / *behind the scenes* framing that
        adds subscriber-only value.

        Args:
            x_posts: List of post dicts from X / System A.  Expected keys
                include ``text``, ``likes``, ``retweets``, ``image_path``
                (optional), ``scene`` (optional), and any custom engagement
                metric.
            limit: Number of top posts to recycle.
            engagement_key: When set, use this key for sorting instead of
                the default ``likes + retweets * 2`` formula.

        Returns:
            List of recycled content dicts ready for Fanvue scheduling.
        """
        if engagement_key:
            sorted_posts = sorted(
                x_posts,
                key=lambda p: p.get(engagement_key, 0),
                reverse=True,
            )
        else:
            sorted_posts = sorted(
                x_posts,
                key=lambda p: p.get("likes", 0) + p.get("retweets", 0) * 2,
                reverse=True,
            )

        recycled: list[dict] = []
        for post in sorted_posts[:limit]:
            text = post.get("text", "")
            scene = post.get("scene", "lifestyle")
            framing = random.choice(self.RECYCLING_FRAMINGS)
            engagement_score = (
                post.get(engagement_key, 0)
                if engagement_key
                else post.get("likes", 0) + post.get("retweets", 0) * 2
            )

            # Attempt AI-powered caption rewrite
            caption: str | None = None
            try:
                char = self.config["character"]
                prompt = (
                    f"Rewrite this social media post as an exclusive Fanvue "
                    f"subscriber caption. Frame it as the '{framing}'. "
                    f"Make it feel more personal and intimate than the public "
                    f"version. Keep it 2-3 sentences, max 250 chars.\n\n"
                    f"Original: {text}\n\n"
                    f"End with: '🤖 AI-generated content'\n"
                    f"Return just the caption."
                )
                system = (
                    f"You are {char['name']}, {char['tagline']}. "
                    f"Personality: {', '.join(char['personality']['traits'][:3])}. "
                    f"Write as yourself in first person."
                )
                caption = self.claude.generate(
                    prompt=prompt,
                    system=system,
                    max_tokens=256,
                    temperature=0.8,
                ).strip().strip('"')
            except Exception as e:
                logger.warning("AI caption for recycled content failed: %s", e)

            if not caption:
                caption = (
                    f"Extended version of my recent post 💫\n\n{text}\n\n"
                    f"Behind the scenes: here's what I didn't share on X...\n"
                    f"🤖 AI-generated content"
                )

            recycled.append({
                "original_text": text,
                "fanvue_text": caption,
                "framing": framing,
                "scene": scene,
                "tier": "basic",
                "source": "recycled_from_x",
                "source_engagement": engagement_score,
                "image_path": post.get("image_path"),
                "recycled_at": datetime.now(JST).isoformat(),
            })

        logger.info("Recycled %d top posts for Fanvue", len(recycled))
        return recycled

    # ─── Revenue Tracking ───

    def track_subscription_revenue(
        self,
        subscriber_counts: dict[str, int],
    ) -> dict[str, Any]:
        """Calculate, track, and project subscription revenue.

        Computes expected monthly revenue from subscriber counts per tier,
        tracks period-over-period growth rate, and projects future revenue
        at the current growth rate (3, 6, and 12 months out).

        Args:
            subscriber_counts: Mapping of tier name to subscriber count,
                e.g. ``{"free": 500, "basic": 120, "premium": 45, "vip": 8}``.

        Returns:
            Revenue snapshot dict, also appended to
            ``data/system_e/fanvue/revenue_tracking.json``.
        """
        now = datetime.now(JST)
        total_revenue = 0.0
        breakdown: dict[str, dict[str, Any]] = {}

        for tier_name, count in subscriber_counts.items():
            price = self.tiers.get(tier_name, {}).get("price", 0)
            tier_rev = round(count * price, 2)
            total_revenue += tier_rev
            breakdown[tier_name] = {
                "subscribers": count,
                "price": price,
                "monthly_revenue": tier_rev,
            }

        total_revenue = round(total_revenue, 2)
        total_subs = sum(subscriber_counts.values())

        # Load history for growth calculation
        tracking_file = FANVUE_DIR / "revenue_tracking.json"
        history: list[dict[str, Any]] = []
        if tracking_file.exists():
            try:
                history = json.loads(tracking_file.read_text(encoding="utf-8"))
            except Exception:
                history = []

        # Period-over-period growth rate
        growth_rate: float = 0.0
        prev_mrr = history[-1].get("total_mrr", 0) if history else 0
        if prev_mrr > 0:
            growth_rate = round((total_revenue - prev_mrr) / prev_mrr, 4)

        # Revenue projections at current growth
        projections: dict[str, float] = {}
        for months in (3, 6, 12):
            if growth_rate > 0:
                projected = total_revenue * ((1 + growth_rate) ** months)
            else:
                projected = total_revenue
            projections[f"{months}_month"] = round(projected, 2)

        # Average revenue per subscriber (ARPS)
        arps = round(total_revenue / total_subs, 2) if total_subs > 0 else 0.0

        result: dict[str, Any] = {
            "date": now.strftime("%Y-%m-%d"),
            "timestamp": now.isoformat(),
            "total_mrr": total_revenue,
            "annual_run_rate": round(total_revenue * 12, 2),
            "total_subscribers": total_subs,
            "arps": arps,
            "breakdown": breakdown,
            "growth_rate": growth_rate,
            "growth_rate_pct": round(growth_rate * 100, 2),
            "projected_revenue": projections,
        }

        history.append(result)
        tracking_file.write_text(
            json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(
            "Fanvue MRR: $%.2f (%d subs, growth=%.1f%%, ARR=$%.2f)",
            total_revenue,
            total_subs,
            growth_rate * 100,
            total_revenue * 12,
        )
        return result

    # ─── Content Calendar ───

    SPECIAL_EVENTS: list[dict[str, Any]] = [
        {
            "name": "Monthly Q&A Live",
            "tier": "premium",
            "week": 2,
            "day_of_week": "Friday",
            "description": "Live Q&A session — ask me anything about wellness, habits, or life.",
        },
        {
            "name": "VIP Voice Note",
            "tier": "vip",
            "week": 1,
            "day_of_week": "Wednesday",
            "description": "Personal voice note sharing what I'm working on this month.",
        },
        {
            "name": "VIP Custom Request Window",
            "tier": "vip",
            "week": 3,
            "day_of_week": "Monday",
            "description": "Submit your custom content requests for the month.",
        },
        {
            "name": "Behind-the-Scenes Day",
            "tier": "basic",
            "week": 1,
            "day_of_week": "Tuesday",
            "description": "Full behind-the-scenes of a content creation day.",
        },
        {
            "name": "Subscriber Spotlight",
            "tier": "basic",
            "week": 4,
            "day_of_week": "Thursday",
            "description": "Shout-out and feature of a subscriber's wellness journey.",
        },
        {
            "name": "Monthly Wellness Challenge Kickoff",
            "tier": "premium",
            "week": 1,
            "day_of_week": "Monday",
            "description": "New monthly wellness challenge begins — premium members get the full plan.",
        },
    ]

    TIER_CONTENT_TYPES: dict[str, list[str]] = {
        "free": [
            "Preview photo (teaser for subscriber content)",
            "Motivational quote card",
            "Quick wellness tip",
        ],
        "basic": [
            "Exclusive behind-the-scenes photo",
            "Personal life update",
            "Workout snapshot",
            "Meal of the day",
            "Casual Q&A response",
        ],
        "premium": [
            "Full workout plan",
            "In-depth wellness breakdown",
            "Video content (form guide / routine)",
        ],
        "vip": [
            "Personal voice/video message",
            "Custom content fulfillment",
        ],
    }

    def generate_content_calendar(
        self,
        year: int | None = None,
        month: int | str | None = None,
    ) -> dict[str, Any]:
        """Generate a monthly content calendar for every Fanvue tier.

        Creates a day-by-day plan ensuring each tier receives appropriate
        volume and variety, with special events (Q&A, challenges, VIP
        exclusives) woven in.  VIP tier receives truly exclusive value
        items that lower tiers never see.

        Args:
            year: Target year.  Defaults to current year (JST).
            month: Target month as int (1-12) or ``"YYYY-MM"`` string.
                Defaults to next month.

        Returns:
            Calendar dict persisted to
            ``data/system_e/fanvue/content_calendar_{YYYY-MM}.json``.
        """
        now = datetime.now(JST)

        # Parse flexible month input
        if isinstance(month, str) and "-" in month:
            parts = month.split("-")
            year = int(parts[0])
            month_int = int(parts[1])
        else:
            if year is None:
                year = now.year
            if month is None:
                # Default to next month
                next_m = now.replace(day=1) + timedelta(days=32)
                month_int = next_m.month
                year = next_m.year
            else:
                month_int = int(month)

        _, num_days = calendar.monthrange(year, month_int)
        month_label = f"{year}-{month_int:02d}"

        # Tier weekly quotas aligned with WEEKLY_TIER_TARGETS
        tier_templates = {
            "free": {
                "posts_per_week": 3,
                "content_types": self.TIER_CONTENT_TYPES["free"],
            },
            "basic": {
                "posts_per_week": 5,
                "content_types": self.TIER_CONTENT_TYPES["basic"],
            },
            "premium": {
                "posts_per_week": 3,
                "content_types": self.TIER_CONTENT_TYPES["premium"],
            },
            "vip": {
                "posts_per_week": 1,
                "content_types": self.TIER_CONTENT_TYPES["vip"],
            },
        }

        daily_plans: list[dict[str, Any]] = []
        tier_totals: dict[str, int] = defaultdict(int)
        special_events_scheduled: list[dict[str, Any]] = []

        for day in range(1, num_days + 1):
            date = datetime(year, month_int, day, tzinfo=JST)
            day_name = calendar.day_name[date.weekday()]
            week_num = (day - 1) // 7 + 1
            weekday = date.weekday()  # 0=Mon .. 6=Sun

            day_plan: dict[str, Any] = {
                "date": date.strftime("%Y-%m-%d"),
                "day_of_week": day_name,
                "week": week_num,
                "posts": [],
            }

            # Assign primary tier based on weekday for a balanced spread
            if weekday in (0, 2, 4):  # Mon, Wed, Fri -> basic
                tier = "basic"
            elif weekday in (1, 3):  # Tue, Thu -> free / premium alternation
                tier = "free" if week_num % 2 == 1 else "premium"
            elif weekday == 5:  # Sat -> premium
                tier = "premium"
            else:  # Sun -> vip (first 2 weeks), free (later weeks)
                tier = "vip" if week_num <= 2 else "free"

            content_options = tier_templates[tier]["content_types"]
            content_type = content_options[day % len(content_options)]

            is_weekend = weekday >= 5
            hours = self.FANVUE_OPTIMAL_HOURS[
                "weekend" if is_weekend else "weekday"
            ]
            suggested_hour = hours[day % len(hours)]

            day_plan["posts"].append({
                "tier": tier,
                "content_type": content_type,
                "suggested_time": f"{suggested_hour:02d}:00 JST",
                "status": "planned",
            })
            tier_totals[tier] += 1

            # Layer in special events
            for event in self.SPECIAL_EVENTS:
                if event["week"] == week_num and event["day_of_week"] == day_name:
                    event_entry = {
                        "tier": event["tier"],
                        "content_type": event["name"],
                        "description": event["description"],
                        "is_special_event": True,
                        "suggested_time": "20:00 JST",
                        "status": "planned",
                    }
                    day_plan["posts"].append(event_entry)
                    tier_totals[event["tier"]] += 1
                    special_events_scheduled.append({
                        "date": date.strftime("%Y-%m-%d"),
                        **event,
                    })

            daily_plans.append(day_plan)

        total_posts = sum(tier_totals.values())

        cal: dict[str, Any] = {
            "month": month_label,
            "month_name": calendar.month_name[month_int],
            "year": year,
            "total_posts": total_posts,
            "tier_summary": dict(tier_totals),
            "special_events": special_events_scheduled,
            "special_events_count": len(special_events_scheduled),
            "tier_details": {
                tier: {
                    "posts_per_week_target": tmpl["posts_per_week"],
                    "content_types": tmpl["content_types"],
                    "special_events": [
                        e["name"]
                        for e in self.SPECIAL_EVENTS
                        if e["tier"] == tier
                    ],
                }
                for tier, tmpl in tier_templates.items()
            },
            "days": daily_plans,
        }

        calendar_file = FANVUE_DIR / f"content_calendar_{month_label}.json"
        calendar_file.write_text(
            json.dumps(cal, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(
            "Content calendar generated: %s %d — %d posts, %d special events",
            calendar.month_name[month_int],
            year,
            total_posts,
            len(special_events_scheduled),
        )
        return cal


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager = FanvueManager()
    stats = manager.get_tier_stats()
    print("Fanvue queue stats:", json.dumps(stats, indent=2))
