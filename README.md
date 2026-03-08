# X Automation Bot

An AI-powered Twitter/X automation bot that generates relatable content, posts threads, quote tweets viral posts, and engages with replies — all running 24/7 for free on GitHub Actions.

---

## Features

| Feature | Implementation |
|---|---|
| Authentication | OAuth 1.0a via Tweepy v2 |
| Content generation | Claude (Anthropic API) with exponential backoff |
| Thread posting | 4-tweet threads every 3rd run for higher reach |
| Quote tweeting | Finds viral niche tweets and adds your opinion |
| Content moderation | Keyword filter, length check, duplicate detection |
| Persistence | SQLite — posts, likes, replies, engagement audit log |
| Rate limiting | Daily post cap + interval guard + hourly engagement caps |
| Engagement monitor | Auto-like replies + smart AI replies to comments |
| Scheduling | GitHub Actions cron — runs every 2 hours, free forever |
| Logging | Loguru — colour console + rotating file with 30-day retention |
| Containerisation | Dockerfile (multi-stage, non-root) + docker-compose |

---

## Project Structure

```
x-automation-bot/
├── .env.example            # Credential template — copy to .env and fill in
├── .gitignore
├── .github/
│   └── workflows/
│       └── bot.yml         # GitHub Actions — runs every 2 hours for free
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
│
├── config.py               # All configuration, daily themes, startup validation
├── auth.py                 # Twitter client setup
├── database.py             # SQLite — posts, likes, replied_tweets, engagement_log
├── generator.py            # AI single tweet generation (Claude) + fallback posts
├── thread_generator.py     # AI 4-tweet thread generation
├── thread_poster.py        # Posts threads as reply chains on X
├── quoter.py               # Finds viral tweets and quote tweets them
├── moderator.py            # Content safety pipeline (length, keywords, duplicates)
├── poster.py               # Single tweet posting, daily cap, interval guard
├── engagement.py           # Engagement monitor — auto-like + smart reply
├── scheduler.py            # APScheduler setup (for local/Docker use)
├── logger_setup.py         # Loguru configuration
├── main.py                 # Entry point — wires all modules together
│
├── data/                   # Auto-created — bot.db (SQLite) + run_counter.txt
└── logs/                   # Auto-created — bot.log (rotating)
```

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- X Developer account with **Read and Write** permissions: https://developer.x.com
- Anthropic API key: https://console.anthropic.com
- GitHub account (free): https://github.com

### 2. X Developer Portal Setup

1. Create a Project and App at developer.x.com
2. Set App permissions to **Read and Write**
3. Generate OAuth 1.0a credentials: API Key + Secret, Access Token + Secret
4. Copy your Bearer Token
5. Add a **Bot label** to your account (required by X)

### 3. Install Locally

```bash
git clone <your-repo>
cd x-automation-bot

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure

```bash
cp .env.example .env
```

Fill in `.env`:

```env
X_API_KEY=...
X_API_SECRET=...
X_ACCESS_TOKEN=...
X_ACCESS_TOKEN_SECRET=...
X_BEARER_TOKEN=...
ANTHROPIC_API_KEY=...
```

### 5. Run Locally

```bash
python main.py
```

---

## Deploying Free on GitHub Actions (Recommended)

No server, no hosting cost, runs 24/7 automatically.

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOURUSERNAME/x-automation-bot.git
git push -u origin main
```

### 2. Add Secrets to GitHub

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

Add each of these:

| Secret Name | Value |
|---|---|
| `X_API_KEY` | Your Twitter API Key |
| `X_API_SECRET` | Your Twitter API Secret |
| `X_ACCESS_TOKEN` | Your Access Token |
| `X_ACCESS_TOKEN_SECRET` | Your Access Token Secret |
| `X_BEARER_TOKEN` | Your Bearer Token |
| `ANTHROPIC_API_KEY` | Your Anthropic API Key |

### 3. GitHub Actions Workflow

The `.github/workflows/bot.yml` file runs your bot automatically:

```yaml
name: X Bot
on:
  schedule:
    - cron: '0 */2 * * *'  # every 2 hours
  workflow_dispatch:        # manual trigger

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python main.py
        env:
          X_API_KEY: ${{ secrets.X_API_KEY }}
          X_API_SECRET: ${{ secrets.X_API_SECRET }}
          X_ACCESS_TOKEN: ${{ secrets.X_ACCESS_TOKEN }}
          X_ACCESS_TOKEN_SECRET: ${{ secrets.X_ACCESS_TOKEN_SECRET }}
          X_BEARER_TOKEN: ${{ secrets.X_BEARER_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

**Important:** The bot is designed to run once and exit cleanly. GitHub Actions handles all scheduling — do NOT use the internal APScheduler with GitHub Actions.

---

## How It Works

```
main.py (runs once per GitHub Actions trigger)
  │
  ├─ Config.validate()              ← all credentials present?
  ├─ init_db()                      ← creates tables if not exist
  ├─ get_client()                   ← OAuth + credential verify
  │
  ├─ run_post_cycle()
  │    ├─ [run % 3 == 0] → THREAD
  │    │    ├─ pick_topic()
  │    │    ├─ generate_thread()    ← Claude API → 4 tweets JSON
  │    │    └─ post_thread()        ← posts as reply chain on X
  │    │
  │    └─ [other runs] → SINGLE TWEET
  │         ├─ pick_topic()
  │         ├─ generate_post()      ← Claude API → fallback on failure
  │         ├─ moderator.check()    ← length + keywords + duplicate
  │         └─ post_tweet()         ← daily cap + interval guard + X API
  │
  ├─ run_engagement_cycle()
  │    ├─ get_users_tweets()        ← scan recent 5 tweets
  │    └─ for each tweet:
  │         └─ search replies
  │              ├─ LIKE  if not already liked + under hourly cap
  │              └─ REPLY if 10+ words or question + not replied yet
  │                   ├─ _generate_reply()   ← Claude API
  │                   ├─ time.sleep(10–30s)  ← human delay
  │                   └─ create_tweet(in_reply_to_tweet_id=...)
  │
  └─ run_quote_tweet_cycle()
       ├─ search_recent_tweets()    ← find viral niche tweets (15+ likes)
       ├─ _generate_quote_text()    ← Claude adds your opinion
       └─ create_tweet(quote_tweet_id=...)  ← tries next if restricted
```

---

## Content Strategy

The bot rotates topics daily to keep content fresh and varied:

| Day | Theme | Topics |
|---|---|---|
| Monday | Making Money Online 💰 | Freelancing truths, earning online |
| Tuesday | AI & Automation 🤖 | Free AI tools, automation tips |
| Wednesday | Learning & Coding 💻 | Self-taught lessons, building projects |
| Thursday | Freelancing Tips 🧑‍💻 | Pricing, finding clients, working alone |
| Friday | Mindset & Motivation 🧠 | Starting messy, staying consistent |
| Saturday | Building in Public 🚀 | Sharing progress, real lessons |
| Sunday | Life & Growth 🌱 | Hard lessons, growth mindset |

**Posting schedule:**
- Run 1 → Single tweet
- Run 2 → Single tweet
- Run 3 → 🧵 4-tweet thread
- Run 4 → Single tweet (repeat)

---

## Engagement Monitor

The engagement monitor scans your recent tweets every run and:

1. **Likes** every new reply (up to 20/hour)
2. **Replies** to comments that are 10+ words or contain a question (up to 5/hour)
3. **Never replies twice** to the same user on the same tweet
4. **Waits 10–30 seconds** before posting each reply (human-like pacing)
5. **Persists all actions** to SQLite so nothing repeats after a restart

### Engagement knobs (`engagement.py` top of file)

| Constant | Default | Description |
|---|---|---|
| `MAX_LIKES_PER_HOUR` | `20` | Rolling 60-min like ceiling |
| `MAX_REPLIES_PER_HOUR` | `5` | Rolling 60-min reply ceiling |
| `MAX_REPLIES_PER_CYCLE` | `5` | Per-run reply ceiling |
| `REPLY_DELAY_MIN_SEC` | `10` | Minimum pre-reply pause |
| `REPLY_DELAY_MAX_SEC` | `30` | Maximum pre-reply pause |
| `RECENT_TWEETS_TO_CHECK` | `5` | How many of your tweets to scan |
| `REPLY_MAX_CHARS` | `220` | Hard reply character ceiling |

---

## Quote Tweet System

The quoter finds viral tweets in your niche and adds your opinion:

- Searches keywords like "freelancing tips", "building in public", "AI tools 2025"
- Qualifies tweets with 15+ likes not already processed
- Generates a short, opinionated response using Claude AI
- Automatically skips restricted tweets and tries the next one
- Marks processed tweets in DB to avoid repeating

### Quote tweet keywords (`quoter.py`)

Edit `SEARCH_KEYWORDS` to match your niche. Current defaults:
```python
SEARCH_KEYWORDS = [
    "freelancing tips",
    "making money online",
    "learn to code",
    "AI tools 2025",
    "building in public",
    "side hustle",
    "self taught developer",
    "solopreneur",
]
```

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `MAX_POSTS_PER_DAY` | `10` | Hard daily posting cap |
| `MIN_INTERVAL_MINUTES` | `90` | Minimum gap between posts |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `DB_PATH` | `data/bot.db` | SQLite database path |
| `AI_MODEL` | `claude-haiku-4-5-20251001` | Anthropic model |
| `AI_MAX_TOKENS` | `200` | Max tokens for tweet generation |
| `AI_MAX_RETRIES` | `3` | AI retry attempts (exponential backoff) |
| `ENABLE_DAILY_GREETING` | `False` | Prepend Good morning/afternoon/evening |

---

## Docker (Alternative to GitHub Actions)

```bash
docker compose up -d
docker compose logs -f
docker compose down
```

Note: When using Docker, restore the scheduler in `main.py` — the run-once design is for GitHub Actions only.

---

## X Automation Policy Compliance

- Posts only to authenticated owner's account
- No bulk mentions or follows
- No engagement-farming language (keyword filter)
- No duplicate content (hash deduplication)
- Human-like posting intervals (90 min minimum)
- Hourly caps on likes and replies
- One reply per user per tweet maximum
- Quote tweets respect X's quoting restrictions

Full policy: https://help.twitter.com/en/using-x/automation

---

## Roadmap

- [ ] Tweet performance tracker — log views, likes, retweets per tweet
- [ ] Auto follow-back system
- [ ] FastAPI dashboard — post history, engagement stats
- [ ] Slack / email alerts on errors or daily summary
- [ ] Async rewrite (`asyncio` + `httpx`)
- [ ] Prometheus metrics + Grafana dashboard
