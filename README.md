# X Automation Bot

A production-grade Twitter/X engagement automation system for lead generation. Finds high-intent users expressing pain around automation, AI tooling, and client acquisition — then engages them intelligently to drive inbound DMs and profile clicks.

Built with **Playwright** (browser automation), **Claude API** (content generation), and **SQLite** (state tracking). Runs continuously on a VPS with human-like session behavior.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Execution Flow](#3-execution-flow)
4. [Key Components](#4-key-components)
5. [AI Integration](#5-ai-integration)
6. [Current Features](#6-current-features)
7. [Configuration Guide](#7-configuration-guide)
8. [Deployment Guide](#8-deployment-guide)
9. [Safety & Anti-Ban Design](#9-safety--anti-ban-design)
10. [Known Limitations](#10-known-limitations)
11. [Future Improvements](#11-future-improvements)

---

## 1. Project Overview

### What it does

The bot operates three concurrent functions:

1. **Posts one original tweet per day** — AI-generated, on a rotating content pillar schedule, designed to attract inbound DMs
2. **Engages high-intent users** — searches for people publicly expressing pain around growth, automation, or client acquisition, then replies/follows/quotes them
3. **Tracks interaction outcomes** — every reply is logged; a background job marks interactions as processed so the database stays clean

### Business goal

Drive inbound DMs and profile clicks from founders, freelancers, and developers who need automation help — without cold outreach or hard selling. Every piece of content is designed to make the target think *"this person gets my problem"*.

### Tech stack

| Layer | Technology |
|---|---|
| Browser control | Playwright (sync API, Chromium) |
| Content generation | Anthropic Claude API (Haiku by default) |
| State storage | SQLite (two databases) |
| Background tasks | APScheduler BackgroundScheduler |
| Language | Python 3.10+ |

---

## 2. System Architecture

```
x-automation-bot/
│
├── run_bot.py                  # Entry point — BotController main loop
├── config.py                   # All settings, loaded from .env at startup
├── database.py                 # SQLite operations (posts, replies, follows, conversions)
├── feedback.py                 # Interaction outcome tracking (interactions table)
│
├── browser/
│   ├── browser_manager.py      # Playwright lifecycle: launch, auth, restart
│   └── stealth.py              # Anti-detection: launch args, JS injections
│
├── core/
│   ├── engagement.py           # Main engagement coordinator per cycle
│   ├── generator.py            # Raw Claude API calls with error handling
│   ├── rate_limiter.py         # Daily/hourly/cluster limits (rate_limiter.db)
│   ├── session_manager.py      # Active hours, session duration, breaks
│   ├── error_handler.py        # Error classification, backoff, detection cooldown
│   └── scheduler.py            # BackgroundScheduler for DB housekeeping
│
├── content/
│   ├── engine.py               # Single entry point for all content generation
│   ├── prompts.py              # System prompts, voice rules, tweet patterns
│   ├── content_moderator.py    # Validates and scores generated content
│   ├── content_cache.py        # Reply cache (exact + semantic dedup)
│   └── conversation_graph.py   # Multi-turn memory (disabled, Phase 2)
│
├── actions/
│   ├── reply.py                # Types and submits a reply via Playwright
│   ├── follow.py               # Clicks Follow, saves to DB
│   ├── like.py                 # Clicks Like
│   ├── tweet.py                # Posts an original tweet
│   ├── quote_tweet.py          # Quotes a tweet with AI commentary
│   └── unfollow.py             # Unfollows non-reciprocators after N days
│
├── search/
│   └── search_tweets.py        # Navigates to search, scrolls, filters, returns tweets
│
└── utils/
    ├── intent_scorer.py        # Keyword-based pain signal detection (scores 1/2/3)
    ├── llm_intent_scorer.py    # Claude-based intent scoring (opt-in via INTENT_MODE)
    ├── human_behavior.py       # Burst typing, random delays, natural scrolling
    ├── tweet_metrics.py        # Extracts like/reply/retweet counts from DOM
    ├── engagement_score.py     # Scores tweet quality for search filtering
    ├── tweet_text.py           # Extracts visible text from tweet element
    ├── language_handler.py     # Filters non-English tweets
    ├── selectors.py            # All CSS/aria selectors in one place
    └── simple_queue.py         # Basic thread-safe job queue (stub)
```

### How the layers connect

```
Config (.env)
    │
    ▼
BotController (run_bot.py)
    ├── SessionManager      ← controls WHEN to run
    ├── RateLimiter         ← controls HOW OFTEN to run
    ├── BrowserManager      ← ONE Playwright instance for everything
    ├── BackgroundScheduler ← DB housekeeping, runs independently
    │
    ├── Daily Tweet Path
    │     └── ContentEngine.generate_daily_tweet()
    │               └── Claude API + 6 quality gates
    │
    └── Engagement Cycle (core/engagement.py)
              ├── search_tweets()       → keyword → scored tweet list
              ├── score_intent()        → routing decision (1/2/3)
              ├── ContentEngine         → Claude API → reply text
              ├── reply/follow/like()   → Playwright actions
              └── FeedbackTracker       → writes to bot.db/interactions
```

---

## 3. Execution Flow

### Startup sequence

```
python run_bot.py
  │
  ├── 1. init_db()                    Create SQLite tables if missing
  ├── 2. Config.validate()            Crash if ANTHROPIC_API_KEY missing
  ├── 3. init_rate_limiter()          Open rate_limiter.db
  ├── 4. init_session_manager()       Load session state from disk
  ├── 5. BrowserManager.start()       Launch Chromium, load session.json cookies
  ├── 6. check_authenticated()        Navigate to x.com/home, verify logged in
  ├── 7. start_scheduler()            Start BackgroundScheduler (daemon thread)
  ├── 8. start_worker()               Start simple_queue daemon thread
  └── 9. Enter main loop
```

### Main loop (continuous)

```
while running:
  │
  ├── session_manager.should_be_active()?
  │     No  → sleep up to 5h, continue
  │     Yes → proceed
  │
  ├── session_manager.start_session()
  │     Sets: duration (20–45 min), action target (8–12), first action delay
  │
  ├── _check_and_post_daily()         ← independent of engagement
  │     • has_posted_today()? → skip
  │     • Random time within DAILY_TWEET_START/END window
  │     • generate_daily_tweet() → post if signal passes all gates
  │
  └── run_engagement(page, keyword)   ← one full engagement cycle
```

### One engagement cycle

```
run_engagement()
  │
  ├── Check rate limits            Bail if all daily limits exhausted
  ├── 25% chance: browse timeline  Scroll home feed (human behavior)
  ├── 30% chance: unfollow cycle   Unfollow stale non-reciprocators
  ├── Select keyword               40% intent keyword, 60% general keyword
  ├── search_tweets(keyword)       Return up to 8 scored tweet elements
  │
  └── For each tweet:
        ├── get_tweet_text()
        ├── score_intent()          → 1 (LOW) / 2 (MEDIUM) / 3 (HIGH)
        │
        ├── Routing:
        │   HIGH  (3) → reply 100% + curiosity mode + 60% follow chance
        │   MEDIUM(2) → reply 30%  + 30% follow chance
        │   LOW   (1) → reply at REPLY_PROBABILITY + base follow chance
        │
        ├── _attempt_reply()        ContentEngine → Claude → Playwright
        ├── _attempt_follow()       Playwright click + DB save
        └── _attempt_quote()        10% flat chance → AI commentary → post
```

### Daily tweet generation

```
generate_daily_tweet()
  │
  ├── Config.get_content_pillar(day_of_year)  Deterministic daily theme
  ├── Config.get_viral_hook()                 Random hook style
  │
  └── Retry loop (up to 4 attempts, 90s budget):
        ├── Gate 1: basic validation      (length, banned patterns)
        ├── Gate 2: vague content check   (is_generic equivalent)
        ├── Gate 3: generic check         (low-effort pattern detection)
        ├── Gate 4: named role required   (VA, junior, CFO, etc.)
        ├── Gate 5: strong ending         (question, tension, or number)
        └── Gate 6: real signal           (signal_density >= 0.75)

        All 6 pass → post immediately
        Partial pass → save as best candidate
        All fail → skip slot (silence > noise)

        Retry strategies escalate per attempt:
          Attempt 0: normal generation
          Attempt 1: force displacement_report structure + named role
          Attempt 2: minimum viable tweet < 120 chars
          Attempt 3: fill-in-the-blank template
```

---

## 4. Key Components

### Rate Limiter (`core/rate_limiter.py`)

Four independent enforcement layers — all configurable via `.env`:

| Layer | Default | Description |
|---|---|---|
| Daily limit | e.g. 15 replies/day | Hard cap per action type |
| Hourly limit | `daily ÷ 12` | Auto-calculated |
| 2-min cluster | 5 same actions | Prevents action bursts |
| 10-min global | 8 total actions | Prevents any burst pattern |

Plus per-action minimum spacing: replies require 120s gap, posts 300s, follows 60s.

Stored in a dedicated `data/rate_limiter.db`. Thread-safe with a lock. Auto-purges history older than 90 days on daily rollover.

### Session Manager (`core/session_manager.py`)

Models a realistic working day. State is persisted to `data/session_state.txt` and restored on restart.

| Behavior | Default |
|---|---|
| Active hours | 08:00–23:00 (configurable) |
| Session length | 20–45 min |
| Actions per session | 8–12 target |
| Break length | 30–120 min |
| Browse-only sessions | 5% chance |
| Session extension | 40% chance when target reached |

### Content Engine (`content/engine.py`)

Single entry point for all content. Two distinct pipelines:

**Reply pipeline** — speed-optimised:
cache check → validate input → Claude → validate output → dedup → cache → return

**Daily tweet pipeline** — quality-optimised:
6 sequential gates → escalating retry prompts → 90s hard timeout → best-effort fallback or skip

### Content Moderator (`content/content_moderator.py`)

Rule-based scoring and validation. No AI used here.

- `validate()` — length, banned patterns, punctuation abuse
- `is_generic()` — multi-word low-effort phrases (any length) + single tokens (≤ 40 chars only, preventing false positives on substantive tweets)
- `has_named_role()` — requires VA, junior, CFO, founder, etc.
- `has_strong_ending()` — last line must contain question, role, implication, or number
- `signal_density()` — 0.0–1.0 score across four signal categories: tool name, number, outcome verb, consequence phrase
- `score_quality()` — composite 0.0–1.0 score used for cache prioritisation

### Feedback Tracker (`feedback.py`)

Logs every reply action to `bot.db/interactions`. Columns include:

- `tweet_id`, `reply_id`, `user_handle`
- `tweet_text`, `reply_text`, `intent`, `reply_style`
- `got_reply_back`, `got_follow`, `got_dm` (outcome columns, populated by future tooling)
- `outcome_score` — weighted: reply×3, follow×5, DM×10

### Background Scheduler (`core/scheduler.py`)

Runs as a daemon thread (`BackgroundScheduler`). Does **not** block the main engagement loop and does **not** launch a second browser.

**Job:** Every 90–110 minutes, marks interactions older than 2 hours as `checked_at` to prevent table bloat. Uses DB-only operations — no Playwright navigation.

---

## 5. AI Integration

### Where Claude is used

| Use case | Function | Model | Token budget |
|---|---|---|---|
| Engagement reply | `generate_reply()` | Haiku (configurable) | 150 |
| Daily original tweet | `generate_daily_tweet()` | Haiku (configurable) | 150 |
| High-intent curiosity reply | `generate_curiosity_reply()` | Haiku (configurable) | 150 |
| Quote tweet commentary | `generate_quote_text()` | Haiku (configurable) | 150 |
| Intent scoring (opt-in) | `LLMIntentScorer.score()` | Haiku | 300 |

### AI vs rules decision matrix

| Decision | Mechanism |
|---|---|
| Should we reply to this tweet? | **Rules** (intent score + probability) |
| What to reply with | **AI** (Claude) |
| Is the reply high quality? | **Rules** (ContentModerator, 6 gates) |
| Is the reply a duplicate? | **Rules** (SHA-256 hash + Jaccard similarity) |
| What to post as daily tweet | **AI** (Claude, pillar + hook guided) |
| Does the daily tweet pass? | **Rules** (signal_density, named_role, etc.) |
| Which keyword to search | **Rules** (weighted random from config) |
| Should we follow this user? | **Rules** (intent score + probability) |
| When to take breaks | **Rules** (session_manager) |
| Rate limit enforcement | **Rules** (rate_limiter) |

Claude handles only content creation. All routing, filtering, safety, and timing decisions are deterministic rule-based logic — debuggable, free, and fast.

### Intent scoring modes

Controlled by `INTENT_MODE` in `.env`:

| Mode | Behaviour | Cost |
|---|---|---|
| `keyword` (default) | Fast keyword matching against pain-phrase lists | Free |
| `hybrid` | Keyword first, LLM as tiebreaker | Low |
| `llm` | Full Claude scoring with negation awareness | Per-call |

---

## 6. Current Features

- **Daily tweet posting** — one original tweet per day on rotating content pillars (money / building / journey), posted within a configurable UTC time window
- **Intent-based engagement** — HIGH intent users always get a reply; MEDIUM users get 30% reply chance; LOW intent gets likes/follows only
- **Curiosity replies** — high-intent users receive a conversion-optimised curiosity prompt designed to trigger a DM
- **Follow strategy** — follows proportional to intent; unfollows non-reciprocators after `UNFOLLOW_AFTER_DAYS` days
- **Quote tweets** — 10% flat chance per tweet with AI-generated commentary
- **Content quality gates** — 6-layer validation before any daily tweet posts; silence is preferred over low-quality noise
- **Reply caching** — exact and semantic (Jaccard) dedup prevents repetitive replies
- **Language filtering** — non-English tweets skipped before engaging
- **Rate limiting** — four layers of enforcement across daily, hourly, cluster, and spacing dimensions
- **Human session simulation** — active hours, random session lengths, browse-only sessions, natural breaks
- **Burst typing** — realistic variable-speed character input to avoid bot detection
- **Engagement scoring** — tweets filtered by like/reply/retweet count + recency boost before processing
- **Interaction logging** — every reply and follow logged to DB with intent, style, and outcome columns
- **Background housekeeping** — scheduler keeps the interactions table clean without blocking the main loop
- **Detection cooldown** — consecutive error tracking with 24h cooldown on suspected detection
- **Session state persistence** — restart-safe; session and break state restored from disk

---

## 7. Configuration Guide

All settings are loaded from a `.env` file in the project root. No config requires a code change.

### Required

```env
ANTHROPIC_API_KEY=sk-ant-...
```

### Search & engagement

```env
# Keywords used to find tweets (comma-separated)
SEARCH_KEYWORDS=AI,python,automation,tech,startup

# High-intent pain-signal keywords (40% of searches use these)
INTENT_KEYWORDS=no engagement,need clients,struggling to grow,nobody sees my posts,zero sales

# Probability of engaging (0.0–1.0)
LIKE_PROBABILITY=0.6
REPLY_PROBABILITY=0.25
FOLLOW_PROBABILITY=0.15

# Intent scoring engine
# Options: keyword (default, free), hybrid, llm (costs API calls)
INTENT_MODE=keyword
```

### Daily tweet

```env
DAILY_TWEET_ENABLED=true

# Post window (UTC hours) — bot picks a random minute within this range
DAILY_TWEET_START_HOUR_UTC=10
DAILY_TWEET_END_HOUR_UTC=13

# Rotating themes (name:description, comma-separated)
CONTENT_PILLARS=money:Making money online and financial freedom,building:Building products and side projects,journey:Personal growth and lessons learned

# Hook styles rotated randomly
VIRAL_HOOKS=hot_take,question,thread_hook,contrarian,story,tip
```

### Rate limits

```env
MAX_LIKES_PER_DAY=20
MAX_REPLIES_PER_DAY=15
MAX_FOLLOWS_PER_DAY=10
MAX_UNFOLLOWS_PER_DAY=5
MAX_POSTS_PER_DAY=1
MAX_QUOTES_PER_DAY=2
```

### Session behavior

```env
# Active operating hours (system local time)
ACTIVE_START_HOUR=8
ACTIVE_END_HOUR=23

# Session length range (minutes)
SESSION_DURATION_MIN=20
SESSION_DURATION_MAX=45

# Break length range (minutes)
BREAK_DURATION_MIN=30
BREAK_DURATION_MAX=120

# Time between actions (seconds)
MIN_ACTION_INTERVAL_SEC=30
MAX_ACTION_INTERVAL_SEC=180

# Probability a completed session extends instead of breaking
SESSION_CONTINUE_PROBABILITY=0.40

# Probability a session is browse-only (no actions taken)
SESSION_BROWSE_ONLY_PROBABILITY=0.05
```

### AI model

```env
# Claude model to use for generation
AI_MODEL=claude-haiku-4-5-20251001

# Token budget per generation call
AI_MAX_TOKENS=150
```

### Browser

```env
HEADLESS_MODE=true
STEALTH_MODE=true
BROWSER_TIMEOUT_MS=30000

# Path to session cookie file (from create_session.py)
SESSION_FILE=session.json
```

### Unfollow strategy

```env
# Days before unfollowing a non-reciprocator
UNFOLLOW_AFTER_DAYS=7

# Probability of running unfollow check per engagement cycle
UNFOLLOW_CHECK_PROBABILITY=0.3
```

### Content safety

```env
# Words that cause generated content to be rejected (comma-separated)
BANNED_WORDS=viagra,cialis,pharmacy,mlm,pyramid,dropship
```

### Database & logging

```env
DATABASE_PATH=data/bot.db
LOG_LEVEL=INFO
DEBUG=false
```

### Feature flags

```env
# Enable multi-turn conversation memory (Phase 2, disabled by default)
CONVERSATION_ENABLED=false

# Enable self-improving feedback analysis (not yet implemented)
FEEDBACK_ANALYSIS_ENABLED=false
```

---

## 8. Deployment Guide

### Prerequisites

- VPS with at least 1 GB RAM (2 GB recommended for Chromium)
- Ubuntu 22.04 or Debian 12
- Python 3.10+

### Initial setup

```bash
# Clone and enter the project
git clone <repo-url>
cd x-automation-bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
playwright install-deps chromium
```

### Create authenticated session

Run this once locally (or with a display) to log in and save cookies:

```bash
python create_session.py
```

This produces `session.json`. Copy it to the VPS — the bot loads it on every start.

### Environment file

```bash
cp .env.example .env
nano .env   # Add ANTHROPIC_API_KEY and adjust settings
```

### Running with tmux (quick start)

```bash
# Start a persistent tmux session
tmux new-session -d -s xbot

# Activate venv and start bot
tmux send-keys -t xbot "source venv/bin/activate && python run_bot.py" Enter

# Reattach later
tmux attach -t xbot
```

### Running as a systemd service (recommended)

Create `/etc/systemd/system/xbot.service`:

```ini
[Unit]
Description=X Automation Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/x-automation-bot
ExecStart=/home/ubuntu/x-automation-bot/venv/bin/python run_bot.py
EnvironmentFile=/home/ubuntu/x-automation-bot/.env
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable xbot
sudo systemctl start xbot

# View live logs
sudo journalctl -u xbot -f
```

### Running via GitHub Actions

The repo includes `.github/workflows/run-bot.yml` for scheduled cloud runs. Set these repository secrets:

| Secret | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `SESSION_COOKIES` | Base64-encoded contents of `session.json` |

### Data directory

All persistent data lives in `data/` (created automatically):

```
data/
├── bot.db                  # Posts, replies, follows, interactions, conversions
├── rate_limiter.db         # Action history for rate enforcement
├── session_state.txt       # Session/break state (survives restarts)
├── detection_cooldown.txt  # Written on suspected detection event
└── error_history.log       # Timestamped error traces
```

---

## 9. Safety & Anti-Ban Design

### Browser stealth

- Playwright launched without automation flags (`--enable-automation` removed)
- `navigator.webdriver` overridden to `undefined` via JS injection on every page load
- Persistent Chrome profile reused across runs — same browser fingerprint as a real user
- Cookie-based authentication — no programmatic login flow that triggers security checks

### Human behavior simulation

| Mechanism | Detail |
|---|---|
| Burst typing | Characters typed in variable-speed clusters of 3–7, with pauses after punctuation |
| Natural scrolling | Each scroll split into 3–6 random-pixel steps with mid-scroll hesitations |
| Action spacing | Minimum enforced gaps: 30s likes, 120s replies, 300s posts |
| Random delays | All waits are `random.uniform(min, max)` — never fixed intervals |
| Session structure | 20–45 min active, 30–120 min breaks, sleeps outside configured hours |
| Browse-only sessions | 5% of sessions navigate without taking any actions |
| Timeline browsing | 25% of cycles browse the home timeline before searching |

### Four-layer rate limiting

```
Daily cap        → hard limit per action type (configurable)
Hourly cap       → 1/12 of daily limit (auto-calculated)
2-min cluster    → max 5 of the same action in 2 minutes
10-min global    → max 8 any actions in 10 minutes
```

All four layers must pass before any action is attempted.

### Error handling and detection cooldown

- Errors classified on each occurrence (recoverable / browser / detection / fatal)
- Recoverable errors: exponential backoff, capped at 5 minutes
- Detection-signature errors (`403`, `blocked`, `detected`): 24-hour full stop, state persisted to disk, resumes automatically
- Browser errors: restart attempted before giving up

### Single browser instance

The bot maintains exactly one Playwright browser context for its entire lifecycle. The background scheduler uses only SQLite — it never creates a browser, never navigates, and never competes with the main thread for the Playwright context.

---

## 10. Known Limitations

### Browser-based outcome tracking is not yet implemented

The `got_reply_back` and `got_follow` columns exist in the interactions table and are reserved for future use. Playwright's sync API is not safe to call from a background thread, and sharing the main browser with the scheduler creates race conditions. The scheduler currently marks interactions as `checked_at` without collecting outcome data. Implementing this requires either post-engagement checks in the main thread or migration to async Playwright.

### DM detection is a placeholder

`check_for_dm()` always returns `False`. Twitter's DM inbox carries high scraping risk. DM-driven conversions are not counted in outcome scores.

### LLM intent mode exists but is not wired into routing

Setting `INTENT_MODE=llm` activates `LLMIntentScorer`, but `_process_single_tweet` in the engagement loop currently always uses keyword scoring. The scorer is correct and tested; connecting it to the routing decision is the remaining step.

### Timezone handling is mixed

`SessionManager` uses system local time for active hours. `database.py` uses UTC for daily post checks. On a VPS set to UTC, these are consistent. On a VPS with a non-UTC timezone, active hours and daily post timing will differ from configured values. Set the VPS system timezone to UTC and configure all hours accordingly.

### Queue worker is a stub

`utils/simple_queue.py` starts a worker thread that dequeues jobs but does not execute them. The queue infrastructure is in place; job execution is not yet implemented.

### No test coverage

No automated tests exist. The content moderator, rate limiter, session manager, and intent scorer are deterministic and well-suited to unit testing, but untested. Changes to these components should be validated manually before deploying.

### Reply quality gates are lighter than daily tweet gates

The 6-gate pipeline applies only to `generate_daily_tweet`. Engagement replies use basic validation and a generic check only — no named role or signal density requirement.

---

## 11. Future Improvements

### High priority

| Improvement | Description |
|---|---|
| In-thread outcome checking | After replying, check if the target user replied back using the existing browser session, before moving to the next tweet |
| LLM intent routing | Wire `LLMIntentScorer` into `_process_single_tweet` behind the existing `INTENT_MODE` flag |
| Reply quality parity | Apply the same 6-gate pipeline to engagement replies, not just daily tweets |
| Outcome-driven style selection | Read `FeedbackTracker.get_stats()` to favour `reply_style` values with higher `outcome_score` |

### Medium priority

| Improvement | Description |
|---|---|
| Queue worker implementation | Implement the `worker_loop` body in `simple_queue.py` to execute enqueued engagement jobs |
| Unified timezone configuration | Add a `BOT_TIMEZONE` env var; use `pytz` or `zoneinfo` consistently across all time-sensitive modules |
| Log rotation | Add file rotation to the logger to prevent unbounded `error_history.log` growth |

### Lower priority

| Improvement | Description |
|---|---|
| Test suite | Unit tests for `ContentModerator`, `RateLimiter`, `SessionManager`, and `intent_scorer` |
| Proxy support | IP rotation to reduce detection risk on long-running single-IP VPS deployments |
| Dashboard | `dashboard.py` exists as a stub — build a reporting view over `conversion_stats` and `feedback.get_stats()` |
| Conversation memory | `content/conversation_graph.py` exists behind `CONVERSATION_ENABLED=false` — wire it in for multi-turn follow-up with high-intent users who reply |
