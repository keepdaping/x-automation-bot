# X Automation Bot v2

Automated X/Twitter growth bot powered by Claude AI for content generation and Playwright for browser automation.

## How It Works

- **Anthropic Claude API** → generates tweets and replies (the only API key needed)
- **Playwright browser automation** → posts, likes, replies, follows on X.com
- **No X/Twitter API keys needed** — everything runs through the browser

## Features

- **AI Content Generation** — Claude-powered tweets and replies
- **Content Pillars** — Rotating daily themes (Money → Building → Journey)
- **Viral Hook Formats** — Hot takes, questions, stories, tips, contrarian views
- **Smart Engagement** — Like, reply, follow with rate limiting
- **Unfollow Strategy** — Auto-unfollows users who don't follow back after 7 days
- **Human Behavior Simulation** — Sessions, breaks, natural typing, scrolling
- **Detection Avoidance** — Stealth mode, rate limits, cluster detection, cooldowns

## Setup

### 1. Clone and install

```bash
git clone https://github.com/keepdaping/x-automation-bot.git
cd x-automation-bot
pip install -r requirements.txt
playwright install chromium
```

### 2. Create session (one-time login)

Log into X.com manually in the bot's browser profile, then export cookies to `session.json`.

### 3. Configure

```bash
cp .env.example .env
# Edit .env — only ANTHROPIC_API_KEY is required
```

### 4. Run

```bash
python run_bot.py
```

### GitHub Actions Deployment

The bot can run on GitHub Actions using Playwright in headless mode.

**Required secret:**
| Secret | Description |
|--------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key from console.anthropic.com |
| `SESSION_JSON_B64` | Base64-encoded session.json: `base64 -w0 session.json` |

The workflow runs every 6 hours and caches the session between runs.

## Architecture

```
run_bot.py              → Main entry point (browser automation)
config.py               → All configuration from .env
database.py             → SQLite (posts, follows, engagement)

content/
  engine.py             → Content generation pipeline
  prompts.py            → System prompts with pillars + hooks
  content_cache.py      → Reply caching with semantic matching
  content_moderator.py  → Quality scoring and validation

core/
  generator.py          → Claude API calls
  engagement.py         → Main engagement loop
  rate_limiter.py       → Multi-level rate limiting
  session_manager.py    → Human-like session behavior
  error_handler.py      → Error recovery + detection cooldown

actions/
  tweet.py              → Post tweets (with error handling)
  like.py               → Like tweets
  reply.py              → Reply to tweets
  follow.py             → Follow users (with tracking)
  unfollow.py           → Unfollow non-followers

browser/
  browser_manager.py    → Playwright lifecycle
  stealth.py            → Anti-detection scripts

search/
  search_tweets.py      → Tweet discovery and scoring

utils/
  human_behavior.py     → Burst typing, scrolling, delays
  engagement_score.py   → Tweet scoring with age boost
  language_handler.py   → Language detection
  selectors.py          → X.com DOM selectors
```

## Content Strategy

**3-pillar rotation** (cycles daily):

| Pillar | Focus |
|--------|-------|
| 💰 Money | Making money online, financial freedom |
| 🔨 Building | Products, side projects, shipping code |
| 🚀 Journey | Personal growth, developer lessons |

**6 viral hook formats**: hot take, question, thread hook, contrarian, story, tip

## Rate Limits

| Action | Daily | Hourly | Min Spacing |
|--------|-------|--------|-------------|
| Likes | 20 | 3 | 30s |
| Replies | 5 | 1 | 120s |
| Follows | 10 | 2 | 60s |
| Unfollows | 5 | 1 | 60s |
| Posts | 1 | — | 300s |

Plus cluster detection (5+ same action in 2min or 8+ total in 10min = blocked).
