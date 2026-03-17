# X (Twitter) API Automation Guide for AI Content Accounts

**Last Updated:** March 2026
**Status:** Actionable reference for building an automated AI content posting pipeline

---

## Table of Contents

1. [API Tier Comparison (Free / Basic / Pro / Enterprise)](#1-api-tier-comparison)
2. [Posting Images via X API](#2-posting-images-via-x-api)
3. [Scheduling Tools](#3-scheduling-tools)
4. [Python Libraries for Automation](#4-python-libraries-for-automation)
5. [Automation Best Practices & Spam Avoidance](#5-automation-best-practices--spam-avoidance)
6. [Analytics API & Engagement Data](#6-analytics-api--engagement-data)
7. [Recommended Architecture for an AI Content Account](#7-recommended-architecture)
8. [Sources](#8-sources)

---

## 1. API Tier Comparison

| Feature | Free ($0/mo) | Basic ($100/mo) | Pro ($5,000/mo) | Enterprise (custom) |
|---|---|---|---|---|
| **Tweet posting** | ~1,500 tweets/mo (app-level) | ~3,000 tweets/mo | ~300,000 tweets/mo | Unlimited (negotiated) |
| **Tweet reads** | Very limited | ~10,000/mo | ~1,000,000/mo | Full firehose |
| **Media upload (images)** | Possible with v2 + `media.write` scope (see notes) | Yes | Yes | Yes |
| **Full-archive search** | No | No | Yes | Yes |
| **User lookup** | Limited | Yes | Yes | Yes |
| **Analytics (public metrics)** | No | Yes | Yes | Yes |
| **Analytics (non-public metrics)** | No | No | Yes (own tweets) | Yes |
| **Streaming** | No | No | Limited | Full |
| **Apps allowed** | 1 | 2 | 3 | Custom |
| **OAuth 2.0 / Login with X** | No | Yes | Yes | Yes |

### Key Decisions for an AI Content Account

- **Minimum viable tier: Basic ($100/mo).** The Free tier is extremely restricted. While posting text-only tweets is technically possible on Free, media upload reliability is questionable, and you get no read/analytics access.
- **If you need analytics to optimize posting strategy: Basic** gives you public metrics (likes, retweets, replies). For impressions and detailed engagement data on your own tweets, you need **Pro** or use the web-based analytics.x.com dashboard (free).
- **The Pro tier at $5,000/mo is overkill** unless you are running a large-scale operation or need full-archive search.

### Rate Limits (Per 15-Minute Window, Basic Tier)

| Endpoint | Rate Limit |
|---|---|
| POST /2/tweets (create tweet) | 100 requests per user per 24h; 1,667/mo app-level |
| POST /2/media/upload | ~100 uploads per 15 min (user context) |
| GET /2/tweets/:id | 300/15 min (app); 900/15 min (user) |
| GET /2/users/:id | 300/15 min (app); 900/15 min (user) |

---

## 2. Posting Images via X API

### The V1.1 to V2 Migration (CRITICAL)

- **As of June 9, 2025**, X deprecated the v1.1 media upload endpoints (`upload.twitter.com/1.1/media/upload.json`).
- The **new endpoint** is: `POST https://api.x.com/2/media/upload`
- Authentication: **OAuth 2.0 with PKCE** (user context). The critical scope you must request is **`media.write`**.
- Previously, many tutorials used a "hybrid approach" (v1.1 for media, v2 for tweets). This no longer works. You must use v2 for everything.

### Image Upload Flow (V2 -- Current)

#### Simple Upload (images < 5 MB)

```
POST https://api.x.com/2/media/upload
Content-Type: multipart/form-data

Parameters:
  media_data: base64-encoded image data (OR)
  media: binary file upload
  media_category: "tweet_image"
```

Response returns `media_id_string` (use the string version, not the integer, to avoid precision issues).

#### Chunked Upload (images > 5 MB, GIFs, videos)

Three-step process:
1. **INIT**: `POST /2/media/upload` with `command=INIT`, `total_bytes`, `media_type`, `media_category`
2. **APPEND**: `POST /2/media/upload` with `command=APPEND`, `media_id`, `segment_index`, chunk data
3. **FINALIZE**: `POST /2/media/upload` with `command=FINALIZE`, `media_id`

#### Attaching Media to a Tweet

```json
POST https://api.x.com/2/tweets
{
  "text": "Your tweet text here",
  "media": {
    "media_ids": ["1234567890123456789"]
  }
}
```

You can attach up to **4 images** per tweet, or **1 GIF**, or **1 video**.

### Image Specifications

| Spec | Limit |
|---|---|
| **Formats** | JPEG, PNG, GIF, WEBP |
| **Max file size (image)** | 5 MB (simple upload) |
| **Max file size (GIF)** | 15 MB |
| **Max file size (video)** | 512 MB (chunked upload) |
| **Max dimensions** | 4096 x 4096 pixels |
| **Recommended dimensions** | 1200 x 675 (16:9) or 1080 x 1080 (1:1) |
| **Alt text** | Up to 1000 characters via `POST /2/tweets` media alt_text field |
| **Tweet text limit** | 280 characters (standard) / 25,000 (X Premium subscribers) |

### Adding Alt Text (Accessibility & SEO)

After uploading media, before or when creating the tweet:
```json
{
  "text": "Check out this AI-generated artwork",
  "media": {
    "media_ids": ["1234567890123456789"],
    "tagged_user_ids": []
  }
}
```

Alt text can be set during the media metadata step or via the create tweet payload, depending on your library.

---

## 3. Scheduling Tools Comparison

### X-Specific / Creator-Focused Tools

| Tool | Price | AI Features | Image Support | Best For |
|---|---|---|---|---|
| **TweetHunter** | $49-$99/mo | AI tweet generator (GPT-4), viral tweet library (3M+ tweets), auto-DMs, auto-plugs | Yes | Creators focused on growth, lead gen |
| **Typefully** | Free / $12.50-$29/mo | AI writing assistant, thread composer, analytics | Yes | Clean writing experience, threads |
| **Hypefury** | $29-$97/mo | Evergreen tweet recycling, auto-retweets, sales automation | Yes | Creators selling products/courses |
| **Postwise** | ~$37/mo | AI ghostwriter trained on viral tweets | Yes | AI-first content creation |

### Multi-Platform Tools

| Tool | Price | AI Features | Image Support | Best For |
|---|---|---|---|---|
| **Buffer** | Free (limited) / $6+/mo per channel | AI content suggestions | Yes | Budget-friendly, multi-platform |
| **Hootsuite** | $99+/mo | OwlyWriter AI, trend-based content ideas, optimal timing | Yes | Agencies, teams, multi-account |
| **Sprout Social** | $249+/mo | AI-assisted publishing, best-time recommendations | Yes | Enterprise social management |
| **SocialPilot** | $25+/mo | AI assistant, bulk scheduling | Yes | SMBs, agencies on a budget |

### Recommendations for an AI Content Account

1. **Budget option:** Typefully ($12.50/mo) or Buffer ($6/mo). Both handle scheduling + images well. Typefully is better for X-specific features.
2. **Growth-focused:** TweetHunter ($49-$99/mo) if X is your primary channel and you want the viral tweet library + AI generation.
3. **Full automation stack:** Hypefury ($29/mo) for evergreen recycling + your own Python script for custom AI content.
4. **DIY (cheapest):** Skip third-party tools entirely. Use the X API directly with a Python cron job. Cost = just the API tier ($100/mo for Basic).

### AI Content Friendliness Notes

- All these tools allow posting AI-generated content. None explicitly block it.
- TweetHunter and Postwise are built around AI content generation.
- X's own policies do not ban AI-generated content, but they do flag spam-like patterns (see Section 5).
- **Key warning:** Tools that auto-generate AND auto-post without human review risk triggering spam detection. Always have a review step.

---

## 4. Python Libraries for X Automation

### Library Comparison

| Library | v2 Support | Media Upload | Maintenance | Stars | Recommendation |
|---|---|---|---|---|---|
| **tweepy** | Full (v1.1 + v2) | Yes (updated for v2) | Actively maintained | ~10k+ | **Best choice** |
| **python-twitter-v2 (pytwitter)** | v2 only | Yes | Moderately maintained | ~1k | Good lightweight alternative |
| **python-twitter** | v1.1 only | Yes (v1.1) | Largely abandoned | Legacy | Avoid -- v1.1 deprecated |
| **twarc** | v2 | Limited | Academic/archival focus | Niche | Not for posting |
| **XDK (X Developer Kit)** | v2 native | Yes | Official X SDK, beta | New | Watch -- may become standard |

### Tweepy: The Go-To Choice

Install:
```bash
pip install tweepy
```

#### Full Example: Post Tweet with Image (Post-June 2025, v2 Only)

```python
import tweepy

# === Authentication (OAuth 2.0 with PKCE for user context) ===
# For automated posting, OAuth 1.0a User Context is simpler:
client = tweepy.Client(
    consumer_key="YOUR_API_KEY",
    consumer_secret="YOUR_API_SECRET",
    access_token="YOUR_ACCESS_TOKEN",
    access_token_secret="YOUR_ACCESS_TOKEN_SECRET",
)

# === Media Upload ===
# As of tweepy 4.15+, use the v2 media upload.
# If your tweepy version still uses v1.1 under the hood for media,
# you may need the API object as well:

auth = tweepy.OAuth1UserHandler(
    "YOUR_API_KEY",
    "YOUR_API_SECRET",
    "YOUR_ACCESS_TOKEN",
    "YOUR_ACCESS_TOKEN_SECRET",
)
api = tweepy.API(auth)

# Upload image
media = api.media_upload(filename="path/to/image.png")
media_id = media.media_id_string

# === Create Tweet with Image ===
response = client.create_tweet(
    text="AI-generated insight of the day #AIArt",
    media_ids=[media_id],
)
print(f"Tweet posted! ID: {response.data['id']}")
```

**Important Note on v2 Media Upload with Tweepy:**
As of early 2026, check the latest tweepy release notes. The library may have fully transitioned media upload to v2 endpoints. If `api.media_upload()` fails, you may need to use the raw v2 endpoint:

```python
import requests
from requests_oauthlib import OAuth1

auth = OAuth1(
    "YOUR_API_KEY",
    "YOUR_API_SECRET",
    "YOUR_ACCESS_TOKEN",
    "YOUR_ACCESS_TOKEN_SECRET",
)

# Upload media via v2
with open("image.png", "rb") as f:
    files = {"media": f}
    response = requests.post(
        "https://api.x.com/2/media/upload",
        auth=auth,
        files=files,
        data={"media_category": "tweet_image"},
    )
media_id = response.json()["media_id_string"]

# Post tweet via v2
tweet_response = requests.post(
    "https://api.x.com/2/tweets",
    auth=auth,
    json={
        "text": "Automated AI content post",
        "media": {"media_ids": [media_id]},
    },
)
print(tweet_response.json())
```

#### Scheduling with Python (Cron-Based)

```python
# save as post_scheduled_tweet.py
import tweepy
import json
import os
from datetime import datetime

def post_next_tweet():
    """Read from a queue file and post the next scheduled tweet."""
    queue_file = "tweet_queue.json"

    with open(queue_file, "r") as f:
        queue = json.load(f)

    if not queue:
        print("Queue empty!")
        return

    tweet = queue.pop(0)

    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )

    kwargs = {"text": tweet["text"]}

    if tweet.get("image_path"):
        auth = tweepy.OAuth1UserHandler(
            os.environ["X_API_KEY"],
            os.environ["X_API_SECRET"],
            os.environ["X_ACCESS_TOKEN"],
            os.environ["X_ACCESS_SECRET"],
        )
        api = tweepy.API(auth)
        media = api.media_upload(filename=tweet["image_path"])
        kwargs["media_ids"] = [media.media_id_string]

    response = client.create_tweet(**kwargs)
    print(f"[{datetime.now()}] Posted: {response.data['id']}")

    # Save updated queue
    with open(queue_file, "w") as f:
        json.dump(queue, f, indent=2)

if __name__ == "__main__":
    post_next_tweet()
```

Crontab entry (post every 4 hours at :00):
```bash
0 */4 * * * cd /path/to/project && /usr/bin/python3 post_scheduled_tweet.py >> /var/log/tweet_poster.log 2>&1
```

#### Tweet Queue Format (tweet_queue.json)

```json
[
  {
    "text": "The future of AI art is here. Here's what I learned today about diffusion models. #AI #GenerativeArt",
    "image_path": "/path/to/images/diffusion_art_001.png",
    "scheduled_for": "2026-03-18T09:00:00-05:00"
  },
  {
    "text": "5 prompting techniques that changed my AI workflow (thread incoming).",
    "image_path": null,
    "scheduled_for": "2026-03-18T13:00:00-05:00"
  }
]
```

---

## 5. Automation Best Practices & Spam Avoidance

### Posting Frequency Guidelines

| Account Type | Safe Range | Optimal | Danger Zone |
|---|---|---|---|
| **New account (< 3 months)** | 1-2 tweets/day | 1-2/day | > 5/day |
| **Established creator** | 3-5 tweets/day | 3-5/day | > 15/day |
| **Brand/business** | 1-3 tweets/day | 2-3/day | > 10/day |
| **Automated/AI account** | 1-3 tweets/day | 2-3/day | > 5/day |

**Hard platform limits:** Free accounts: 600 posts/day. Premium: 6,000/day. But hitting even 10% of these limits with automated content will flag you.

### Spacing Rules

- **Minimum 2 hours between automated posts.** 3-4 hours is safer.
- **Never post at exactly the same time every day.** Add 5-15 minutes of random jitter to your cron schedule.
- **Mix formats:** Alternate between text-only, image posts, threads, and quote tweets.

### What Triggers Spam Detection

1. **Identical or near-identical content** across posts or accounts
2. **Exact timing patterns** (posting at :00 every hour like clockwork)
3. **Mass following/unfollowing** in short bursts
4. **Excessive liking/retweeting** (> 200 in 10 minutes)
5. **Same links or hashtags** repeated across many posts
6. **Zero engagement with other accounts** (post-only, never reply)
7. **Sudden volume spikes** (0 posts/day to 20 posts/day overnight)

### What Does NOT Trigger Detection (Allowed Automation)

- Scheduling tweets via API or third-party tools
- Posting from RSS feeds
- Using analytics tools to read engagement data
- Auto-posting from your own blog/website (with unique text per post)
- Using AI to help write content (as long as it's varied and quality)

### Content Quality Rules for AI Accounts

1. **Edit AI output before posting.** Pure unedited GPT output reads as generic and gets less engagement.
2. **Develop a consistent voice.** The algorithm rewards accounts that followers recognize.
3. **Include original images/graphics.** AI-generated art or custom infographics significantly boost engagement vs. text-only.
4. **Reply to comments on your posts.** Accounts that only broadcast and never engage get suppressed.
5. **No duplicate content across accounts.** Each account needs unique content even if you own multiple.
6. **Vary hashtag usage.** Don't use the same 5 hashtags on every post.

### Optimal Posting Times by Region

#### US Audience (EST)

| Day | Best Times (EST) | Peak Hour |
|---|---|---|
| Monday | 9 AM - 12 PM | 10 AM |
| Tuesday | 9 AM - 1 PM | 9 AM |
| **Wednesday** | **8 AM - 2 PM** | **9 AM (single best slot)** |
| Thursday | 9 AM - 1 PM | 10 AM |
| Friday | 9 AM - 12 PM | 11 AM |
| Saturday | 10 AM - 12 PM | 11 AM |
| Sunday | Avoid or post sparingly | -- |

#### EU Audience (GMT/CET)

| Slot | Time (GMT) | Notes |
|---|---|---|
| **Morning peak** | 7:00 - 9:00 AM | Before-work check, highest engagement |
| **Lunch** | 12:00 - 1:00 PM | Secondary peak |
| **Evening** | 5:00 - 7:00 PM | Post-work browsing |

#### Asia-Pacific (JST/SGT)

| Slot | Time | Notes |
|---|---|---|
| **Evening peak** | 7:00 - 10:00 PM JST | Users most active at night |
| **Morning** | 8:00 - 10:00 AM JST | Secondary peak |

#### Global Multi-Timezone Strategy

- **Universal sweet spot:** 12:00 PM - 2:00 PM EST (catches US lunch, EU afternoon, Asia evening)
- **Dual-post strategy:** Post the same topic (different text!) 8-12 hours apart for US + Asia coverage
- After 2-3 months of data, use analytics.x.com or API metrics to find YOUR audience's specific active windows

---

## 6. Analytics API & Engagement Data

### What's Available by Tier

| Metric | Free | Basic | Pro | Enterprise |
|---|---|---|---|---|
| Public metrics (likes, retweets, replies, quotes) | No | Yes | Yes | Yes |
| Impression count | No | No | Yes (own tweets) | Yes |
| Profile clicks | No | No | Yes (own tweets) | Yes |
| URL clicks | No | No | Yes (own tweets) | Yes |
| Follower count over time | No | Via user lookup | Via user lookup | Full |
| Engagement API (detailed breakdowns) | No | No | No | Yes |

### Pulling Public Metrics (Basic Tier)

```python
import tweepy

client = tweepy.Client(bearer_token="YOUR_BEARER_TOKEN")

# Get metrics for a specific tweet
tweet = client.get_tweet(
    id="1234567890",
    tweet_fields=["public_metrics", "created_at"],
)

metrics = tweet.data.public_metrics
print(f"Likes: {metrics['like_count']}")
print(f"Retweets: {metrics['retweet_count']}")
print(f"Replies: {metrics['reply_count']}")
print(f"Quotes: {metrics['quote_count']}")
# Note: 'impression_count' requires Pro tier + user context auth
```

### Pulling Your Own Tweet History for Analysis

```python
# Get your recent tweets with metrics
user_tweets = client.get_users_tweets(
    id="YOUR_USER_ID",
    tweet_fields=["public_metrics", "created_at"],
    max_results=100,
)

for tweet in user_tweets.data:
    m = tweet.public_metrics
    engagement = m["like_count"] + m["retweet_count"] + m["reply_count"]
    print(f"{tweet.created_at} | Engagement: {engagement} | {tweet.text[:50]}...")
```

### Non-Public Metrics (Pro Tier, Own Tweets Only)

```python
# Requires OAuth 1.0a user context (not just bearer token)
tweet = client.get_tweet(
    id="1234567890",
    tweet_fields=["non_public_metrics", "organic_metrics"],
    user_auth=True,
)

if tweet.data.non_public_metrics:
    print(f"Impressions: {tweet.data.non_public_metrics['impression_count']}")
    print(f"Profile clicks: {tweet.data.non_public_metrics['user_profile_clicks']}")
    print(f"URL clicks: {tweet.data.non_public_metrics['url_link_clicks']}")
```

### Free Alternative: Web Dashboard

- Go to **analytics.x.com** (free for all accounts)
- Provides impressions, engagement rate, profile visits, follower growth
- Can export CSV data for manual analysis
- No API access, but useful for building an initial baseline

### Building a Simple Analytics Tracker

```python
import tweepy
import csv
from datetime import datetime

def track_daily_metrics():
    client = tweepy.Client(
        bearer_token="YOUR_BEARER_TOKEN",
        consumer_key="YOUR_API_KEY",
        consumer_secret="YOUR_API_SECRET",
        access_token="YOUR_ACCESS_TOKEN",
        access_token_secret="YOUR_ACCESS_SECRET",
    )

    tweets = client.get_users_tweets(
        id="YOUR_USER_ID",
        tweet_fields=["public_metrics", "created_at"],
        max_results=50,
    )

    with open("tweet_metrics.csv", "a", newline="") as f:
        writer = csv.writer(f)
        for tweet in tweets.data:
            m = tweet.public_metrics
            writer.writerow([
                datetime.now().isoformat(),
                tweet.id,
                tweet.created_at,
                m["like_count"],
                m["retweet_count"],
                m["reply_count"],
                m["quote_count"],
                tweet.text[:100],
            ])

if __name__ == "__main__":
    track_daily_metrics()
```

Run daily via cron to build a metrics history you can analyze for optimal content types, posting times, and engagement patterns.

---

## 7. Recommended Architecture for an AI Content Account

### Minimum Viable Setup (Budget: ~$100/mo)

```
[Content Generation]     [Scheduling]         [Posting]         [Analytics]

AI (GPT/Claude/local) -> tweet_queue.json -> Python cron job -> CSV tracker
       |                                     (tweepy)          (weekly review)
       v                                         |
  Human review                                   v
  & editing step                            X API Basic
                                            ($100/mo)
```

### Components

1. **Content Generation Pipeline**
   - Use any LLM (GPT-4, Claude, local models) to generate draft tweets
   - Always include a human review/editing step before queuing
   - Generate images with DALL-E, Midjourney, Stable Diffusion, or Flux
   - Store approved content in a JSON queue file or simple database

2. **Scheduling Layer**
   - Python script with cron (free, full control)
   - OR Typefully ($12.50/mo) if you prefer a GUI
   - Add random jitter (5-15 min) to posting times
   - Space posts 3-4 hours apart

3. **Posting Engine**
   - Tweepy + X API Basic ($100/mo)
   - Handle both text + image posts
   - Log all posts with timestamps and IDs

4. **Analytics Feedback Loop**
   - Pull public metrics daily via API
   - Track: engagement rate, best-performing content types, optimal times
   - Feed insights back into content generation prompts
   - Monthly review to adjust strategy

### Scaling Up

- **More automation:** Add Hypefury ($29/mo) for evergreen recycling of top-performing tweets
- **More analytics:** Upgrade to Pro ($5,000/mo) only when revenue justifies it; until then use analytics.x.com
- **Multi-account:** Each account needs its own API app, unique content, and separate posting patterns

---

## 8. Sources

- [X Developer Platform -- Official Documentation](https://developer.x.com)
- [X Developer Community -- v1.1 Media Upload Deprecation Announcement](https://devcommunity.x.com/t/deprecating-the-v1-1-media-upload-endpoints/238196)
- [X Developer Community -- v2 Media Upload Free Tier Discussion](https://devcommunity.x.com/t/questions-about-https-api-twitter-com-2-media-upload-availability-and-functionality-on-free-tier/240226)
- [Tweepy Official Documentation](https://www.tweepy.org/)
- [X Developer Platform -- Tweeting Media with v2 Tutorial](https://developer.x.com/en/docs/tutorials/tweeting-media-v2)
- [OpenTweet -- Twitter/X Automation Rules in 2026](https://opentweet.io/blog/twitter-automation-rules-2026)
- [SocialRails -- Twitter/X Automation Complete Guide](https://socialrails.com/blog/twitter-x-automation-complete-guide)
- [Buffer -- Best Time to Post on Twitter/X (2026, 1M+ posts analyzed)](https://buffer.com/resources/best-time-to-post-on-twitter-x/)
- [SocialPilot -- Best Time to Post on Twitter (50,000+ accounts)](https://www.socialpilot.co/blog/best-time-to-post-on-twitter)
- [Sprout Social -- Best Times to Post on Twitter (2025)](https://sproutsocial.com/insights/best-times-to-post-on-twitter/)
- [Tweet Archivist -- How Often Should You Post on Twitter in 2026](https://www.tweetarchivist.com/how-often-to-post-on-twitter-2025)
- [Tweet Archivist -- How the Twitter Algorithm Works in 2026](https://www.tweetarchivist.com/how-twitter-algorithm-works-2025)
- [TweetHunter](https://tweethunter.io/)
- [Typefully](https://typefully.com)
- [Hypefury](https://hypefury.com)
- [Buffer](https://buffer.com)
- [Hootsuite](https://hootsuite.com)
- [Gramfunnels -- Twitter API Limits Guide 2025](https://www.gramfunnels.com/blog/twitter-api-limits)
- [PostQuickAI -- How to Automate Posts on X in 2026](https://www.postquick.ai/blog/how-to-automate-posts-on-x-twitter-in-2026)
- [X API Migration Overview](https://docs.x.com/x-api/migrate/overview)

---

**Disclaimer:** X frequently changes its API policies, pricing, and rate limits. Always verify current details at [developer.x.com](https://developer.x.com) before committing to a tier or building production automation. API terms of service prohibit certain types of automation (mass following, spam, coordinated inauthentic behavior) -- review the [X Automation Rules](https://help.x.com/en/rules-and-policies/x-automation) before deploying.
