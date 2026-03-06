# X Automation Bot

An educational, responsible AI-assisted automation bot that generates and posts content to your own X (Twitter) account — and engages naturally with replies.

---

## Features

| Feature | Implementation |
|---|---|
| Authentication | OAuth 1.0a via Tweepy v2 |
| Content generation | Claude (Anthropic API) with exponential backoff |
| Content moderation | Keyword filter, length check, duplicate detection |
| Persistence | SQLite — posts, likes, replies, engagement audit log |
| Rate limiting | Daily post cap + interval guard + hourly engagement caps |
| Engagement monitor | Auto-like replies + smart AI replies to questions |
| Scheduling | APScheduler — post cycle (90 min) + engagement cycle (30 min) |
| Logging | Loguru — colour console + rotating file with 30-day retention |
| Containerisation | Dockerfile (multi-stage, non-root) + docker-compose |

---

## Project Structure

```
x-automation-bot/
├── .env.example          # Credential template — copy to .env and fill in
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
│
├── config.py             # All configuration, with startup validation
├── auth.py               # Twitter client setup
├── database.py           # SQLite — posts, likes, replied_tweets, engagement_log
├── generator.py          # AI tweet generation (Claude) + fallback posts
├── moderator.py          # Content safety pipeline (length, keywords, duplicates)
├── poster.py             # Tweet posting, daily cap, interval guard
├── engagement.py         # Engagement monitor — auto-like + smart reply
├── scheduler.py          # APScheduler setup
├── logger_setup.py       # Loguru configuration
├── main.py               # Entry point — wires all modules together
│
├── data/                 # Auto-created — bot.db (SQLite)
└── logs/                 # Auto-created — bot.log (rotating)
```

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- X Developer account with **Read and Write** permissions: https://developer.x.com
- Anthropic API key: https://console.anthropic.com

### 2. X Developer Portal Setup

1. Create a Project and App at developer.x.com
2. Set App permissions to **Read and Write**
3. Generate OAuth 1.0a credentials: API Key + Secret, Access Token + Secret
4. Copy your Bearer Token
5. Add a **Bot label** to your account (required by X)

### 3. Install

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

### 5. Run

```bash
python main.py
```

---

## Docker

```bash
docker compose up -d
docker compose logs -f
docker compose down
```

---

## Engagement Monitor

The engagement monitor (`engagement.py`) runs every 30 minutes and:

1. **Likes** every new reply to your recent tweets (up to 20/hour)
2. **Replies** to comments that contain a question or substantive discussion (up to 5/hour)
3. **Never replies twice** to the same user on the same tweet
4. **Waits 30–120 seconds** before posting each reply (human-like pacing)
5. **Persists all actions** to SQLite so nothing repeats after a restart

### Engagement knobs (`engagement.py` top of file)

| Constant | Default | Description |
|---|---|---|
| `MAX_LIKES_PER_HOUR` | `20` | Rolling 60-min like ceiling |
| `MAX_REPLIES_PER_HOUR` | `5` | Rolling 60-min reply ceiling |
| `MAX_REPLIES_PER_CYCLE` | `5` | Per-run reply ceiling |
| `REPLY_DELAY_MIN_SEC` | `30` | Minimum pre-reply pause |
| `REPLY_DELAY_MAX_SEC` | `120` | Maximum pre-reply pause |
| `RECENT_TWEETS_TO_CHECK` | `5` | How many of your tweets to scan |
| `REPLY_MAX_CHARS` | `220` | Hard reply character ceiling |

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

---

## How It Works

```
main.py
  │
  ├─ Config.validate()          ← all credentials present?
  ├─ init_db()                  ← creates tables if not exist
  ├─ get_client()               ← OAuth + credential verify
  │
  ├─ run_post_cycle()  [every 90 min]
  │    ├─ pick_topic()
  │    ├─ generate_post()       ← Claude API → fallback on failure
  │    ├─ moderator.check()     ← length + keywords + duplicate
  │    └─ post_tweet()          ← daily cap + interval guard + X API
  │
  └─ run_engagement_cycle()  [every 30 min]
       ├─ get_users_tweets()    ← your RECENT_TWEETS_TO_CHECK recent posts
       └─ for each tweet:
            └─ search_recent_tweets(conversation_id=...)
                 ├─ LIKE  if not already liked + under hourly cap
                 └─ REPLY if question/discussion + not replied to author + under caps
                      ├─ _generate_reply()   ← Claude API
                      ├─ time.sleep(30–120s) ← human delay
                      ├─ create_tweet(in_reply_to_tweet_id=...)
                      └─ record_reply()      ← persists to DB
```

---

## X Automation Policy Compliance

- Posts only to authenticated owner's account
- No bulk mentions or follows
- No engagement-farming language (keyword filter)
- No duplicate content (hash deduplication)
- Human-like posting intervals (90 min minimum)
- Hourly caps on likes and replies
- One reply per user per tweet maximum

Full policy: https://help.twitter.com/en/using-x/automation

---

## Roadmap

- [ ] FastAPI dashboard — post history, engagement stats, manual approval queue
- [ ] Async rewrite (`asyncio` + `httpx`)
- [ ] GitHub Actions CI — lint, type-check, Docker build
- [ ] Prometheus metrics + Grafana dashboard
- [ ] Slack / email alerts on errors or daily summary
