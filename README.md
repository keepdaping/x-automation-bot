# X Automation Bot v2

An automated lead generation and growth system for X (Twitter). Uses Claude AI for content generation and Playwright for browser automation.

This is not a simple posting bot. It is a targeted engagement system that finds high-intent users, engages them with curiosity-driven replies, and drives profile visits that convert to DMs and clients.

---

## How It Works (High Level)

1. **Search** — Finds tweets by keyword (topic keywords + pain-based intent keywords)
2. **Score** — Rates each tweet's intent level (HIGH / MEDIUM / LOW)
3. **Decide** — Routes engagement based on intent:
   - HIGH intent → curiosity reply + like + follow (60%)
   - MEDIUM intent → standard reply (30%) + like
   - LOW intent → like only
4. **Engage** — Executes actions via Playwright browser automation
5. **Track** — Logs all high-intent engagements for conversion analysis

Only two external dependencies: **Anthropic Claude API** (content generation) and **Playwright** (browser control). No X/Twitter API keys needed.

---

## Full Execution Flow

```
python run_bot.py
  |
  +-- Config.validate()            -> checks API key, probabilities, keywords
  +-- init_db()                    -> creates SQLite tables (posts, follows, conversions)
  +-- init_rate_limiter(Config)    -> loads daily/hourly limits, action spacing
  +-- init_session_manager(Config) -> loads active hours, session/break durations
  |
  +-- BrowserManager.start()       -> launches headless Chromium via Playwright
  |   +-- loads session.json cookies
  |   +-- injects stealth scripts (hide webdriver flag, spoof UA)
  |   +-- navigates to x.com/home
  |
  +-- check_authenticated()        -> verifies X login via DOM checks
  |
  +-- MAIN LOOP (while running):
      |
      +-- should_be_active()?      -> checks UTC hour against ACTIVE_START/END
      |   +-- NO -> sleep until next active window
      |
      +-- start_session()          -> randomize duration (20-45min), set action target
      |
      +-- _check_and_post_daily()  -> independent of engagement loop
      |   +-- if within posting window + not posted today -> generate + post
      |
      +-- should_take_action()?    -> natural pacing (min 30s between actions)
      |   +-- NO -> wait 5-15s, continue loop
      |
      +-- run_engagement(page, keyword)  -> ONE CYCLE:
      |   +-- pick keyword (60% topic, 40% intent)
      |   +-- search_tweets(page, keyword) -> returns 5 tweets
      |   +-- for each tweet:
      |   |   +-- get_tweet_metrics()  -> likes, replies, retweets, age
      |   |   +-- score_intent()       -> HIGH(3) / MEDIUM(2) / LOW(1)
      |   |   +-- LIKE  (60% all levels, if rate limit allows)
      |   |   +-- REPLY (intent-routed, if rate limit allows)
      |   |   |   +-- HIGH   -> generate_curiosity_reply() 100%
      |   |   |   +-- MEDIUM -> generate_reply() 30%
      |   |   |   +-- LOW    -> generate_reply() 25%
      |   |   +-- FOLLOW (intent-scaled: HIGH=60%, MEDIUM=30%, LOW=15%)
      |   |   +-- QUOTE  (10% chance, 2/day limit)
      |   +-- log_conversion() for intent >= 2
      |
      +-- session_manager.record_action()
      +-- is_session_complete()? -> end_session() + take break
      +-- natural pacing pause (30-180s)
```

---

## Architecture

### Directory Structure

```
x-automation-bot/
+-- run_bot.py                 -> Entry point. Main loop, session lifecycle, daily tweets
+-- config.py                  -> All configuration from .env (202 lines)
+-- database.py                -> SQLite operations: posts, follows, conversions (269 lines)
+-- dashboard.py               -> HTML dashboard generator with Chart.js (348 lines)
+-- create_session.py          -> Opens browser for manual X login, saves cookies
+-- logger_setup.py            -> Loguru config
+-- requirements.txt           -> anthropic, playwright, loguru, langdetect, textblob
|
+-- content/                   -> Content generation system
|   +-- engine.py              -> ContentEngine: reply, daily tweet, curiosity reply, quote (162 lines)
|   +-- prompts.py             -> All system prompts: 5 prompts for different contexts (214 lines)
|   +-- content_cache.py       -> Reply caching with exact + semantic matching (184 lines)
|   +-- content_moderator.py   -> Validation, quality scoring, dedup (128 lines)
|
+-- core/                      -> Bot control systems
|   +-- engagement.py          -> Main engagement loop with intent routing (287 lines)
|   +-- generator.py           -> Claude API wrapper with model fallback (119 lines)
|   +-- rate_limiter.py        -> Multi-level rate limiting: daily/hourly/cluster (229 lines)
|   +-- session_manager.py     -> Human-like session/break behavior (240 lines)
|   +-- error_handler.py       -> Error classification + recovery strategies (122 lines)
|
+-- actions/                   -> Playwright browser actions
|   +-- tweet.py               -> Post original tweets with confirmation (64 lines)
|   +-- like.py                -> Like tweets with retry (52 lines)
|   +-- reply.py               -> Reply with human typing (45 lines)
|   +-- follow.py              -> Follow + track in database (57 lines)
|   +-- unfollow.py            -> Unfollow stale follows via profile nav (95 lines)
|   +-- quote_tweet.py         -> Quote tweet with commentary (109 lines)
|
+-- browser/                   -> Browser lifecycle
|   +-- browser_manager.py     -> Playwright launch, cookies, auth check (106 lines)
|   +-- stealth.py             -> Anti-detection: UA spoof, webdriver hide (75 lines)
|
+-- search/
|   +-- search_tweets.py       -> Tweet discovery, scoring, weighted selection (122 lines)
|
+-- utils/                     -> Helpers
|   +-- intent_scorer.py       -> Pain-signal phrase matching (94 lines)
|   +-- engagement_score.py    -> Tweet scoring: engagement x recency (25 lines)
|   +-- human_behavior.py      -> Burst typing, natural scroll, delays (99 lines)
|   +-- language_handler.py    -> Language detection, English filter (58 lines)
|   +-- tweet_metrics.py       -> Extract likes/replies/retweets from DOM (42 lines)
|   +-- tweet_text.py          -> Extract tweet text from DOM (7 lines)
|   +-- selectors.py           -> Centralized X.com DOM selectors (20 lines)
|
+-- data/                      -> Runtime data (gitignored)
|   +-- bot.db                 -> Posts, follows, conversions, reply cache
|   +-- rate_limiter.db        -> Action history, daily summaries
|   +-- session_state.txt      -> Persisted session/break state
|
+-- .github/workflows/
    +-- run-bot.yml            -> GitHub Actions: cron at 6,10,14,18 UTC
```

### Legacy Files (unused, safe to delete)

These exist in the repo but are not imported by any active code:

```
utils/behavior_patterns.py     -> replaced by human_behavior.py
utils/performance_tracker.py   -> replaced by rate_limiter metrics
utils/posting_schedule.py      -> replaced by session_manager
utils/tweet_selector.py        -> replaced by engagement_score.py
core/scheduler.py              -> replaced by session_manager (used apscheduler)
import_cookies.py              -> replaced by create_session.py
browser/login.py               -> empty placeholder
docker-compose.yml             -> empty file
```

---

## Module Deep Dives

### run_bot.py - Entry Point

BotController class manages the entire lifecycle. __init__() validates config, initializes DB + rate limiter + session manager, sets up signal handlers for graceful shutdown. start() launches browser, verifies auth, enters main while loop. _check_and_post_daily() is independent of engagement - checks if within posting window and hasn't posted today, generates daily tweet using content pillar + viral hook. _get_next_search_topic() uses shuffled keyword rotation per session to avoid predictable search patterns.

The main loop checks three gates in order: (1) active hours, (2) session state, (3) action pacing. All three must pass before run_engagement() is called.

### core/engagement.py - Engagement Engine

The central orchestrator. run_engagement() does one complete cycle:

1. Checks detection cooldown (24h pause if bot was detected)
2. Checks remaining daily limits
3. 25% chance: browse home timeline first (human behavior)
4. 30% chance: run unfollow cycle
5. Picks keyword: 40% from INTENT_KEYWORDS, 60% from SEARCH_KEYWORDS
6. Searches X for tweets (returns 5 max)
7. For each tweet: extracts text, scores intent, routes engagement

Intent routing logic:
- HIGH (3): curiosity reply 100%, follow 60%, like 60%
- MEDIUM (2): standard reply 30%, follow 30%, like 60%
- LOW (1): standard reply 25%, follow 15%, like 60%

All actions are gated by rate_limiter.can_perform_action() before execution. High-intent engagements (intent >= 2) are logged to the conversions table.

### content/engine.py - Content Generation

ContentEngine singleton with four generation methods:

generate_reply(tweet_text) - Standard reply pipeline: cache check -> input validation -> Claude API -> output validation -> generic check -> duplicate check -> cache store -> return. Falls back to static fallback replies if any step fails.

generate_daily_tweet(topic) - Original tweet: get pillar (day_of_year % 3) -> pick random hook -> build prompt -> Claude API with "Write one original tweet about: {topic}"

generate_curiosity_reply(tweet_text) - High-intent reply: curiosity prompt -> Claude API -> validate -> return. Falls back to standard generate_reply() on failure.

generate_quote_text(tweet_text) - Quote tweet commentary: quote prompt -> Claude API -> return (200 char max).

### content/prompts.py - Prompt System

Five system prompts, each with a different goal:

| Prompt | Used For | Key Rules |
|--------|----------|-----------|
| get_daily_tweet_system_prompt() | Original tweets | Max 4 lines, line breaks, punchline ending, pillar + hook injected |
| get_reply_system_prompt() | Standard replies | Conversational, ask follow-up questions |
| get_curiosity_reply_prompt() | High-intent replies | Hint at solution, leave gap, variation rules to prevent templating |
| get_quote_tweet_system_prompt() | Quote tweets | 200 char max, strong take, no generic praise |
| _get_default_reply_system_prompt() | Fallback in generator.py | Minimal rules, used if no prompt passed |

Daily tweet prompt injects pillar description and hook instruction into a template that enforces: max 4 lines, each under 10-12 words, first line = hook, last line = punchline, spoken not written.

Curiosity prompt has variation rules: banned openers ("I had the same problem"), banned phrases ("changed one thing"), required variation across observational/contrarian/subtle/micro-story/direct angles, banned guru language ("leverage", "scale", "optimize").

### core/generator.py - Claude API

generate_contextual_reply() is the single function that calls Claude. Accepts system_prompt and optional user_message. Model fallback chain: claude-haiku-4-5-20251001 -> claude-sonnet-4-6. Stops retrying on rate limits (429). Re-raises auth errors (fatal). Tracks metrics: model used, tokens, duration, success.

### utils/intent_scorer.py - Intent Detection

Pure phrase matching against two static lists. HIGH intent (~30 phrases): "no engagement", "need clients", "struggling to grow", etc. MEDIUM intent (~20 phrases): "just started", "building my", "first client", etc. Matching is substring-based. First match wins (high checked before medium). Score of 2 also assigned if tweet has 2+ question marks.

### core/rate_limiter.py - Rate Limiting

Four protection layers:

1. Daily caps: hard limits per action type per day
2. Hourly caps: ceil(daily_limit / 12) per action type
3. Cluster detection: 5+ same action in 2 min OR 8+ total in 10 min = blocked
4. Action spacing: minimum seconds between consecutive same-type actions

| Action | Daily | Hourly | Min Spacing |
|--------|-------|--------|-------------|
| Like | 20 | 2 | 30s |
| Reply | 5 | 1 | 120s |
| Follow | 10 | 1 | 60s |
| Unfollow | 5 | 1 | 60s |
| Post | 1 | 1 | 300s |
| Quote | 2 | 1 | 180s |

Auto-migrates old databases via _migrate_db() - adds missing columns without breaking existing data. If bot detection is suspected (403/401), a 24-hour cooldown activates (persisted to disk).

### core/session_manager.py - Session Behavior

Simulates human usage patterns. Active hours: 5:00-20:00 UTC. Sessions: 20-45 minutes, target ~1 action per 5 minutes. Breaks: 30-120 minutes. Extended breaks: 20% chance of 2-4 hours. Session continuation: 25% chance to extend by 10-20 minutes. Browse-only: 10% of action opportunities silently skipped.

State persisted to data/session_state.txt. Stale sessions (>12h old) auto-reset to idle.

### search/search_tweets.py - Tweet Discovery

Navigates to x.com/search?q={keyword}&f=live, scrolls to load tweets. For each: extracts ID, filters promoted/pinned, checks minimum engagement (sum >= 3). Scores by likes*2 + replies*3 + retweets*2 + age_bonus. Selects via weighted random. Returns max 5 tweet elements. Maintains in-session _seen_tweet_ids set.

### actions/ - Browser Actions

- tweet.py: navigates to compose, types with human_typing(), clicks post, verifies textarea disappears
- like.py: finds [data-testid="like"], scrolls into view, clicks with force fallback
- reply.py: clicks reply button, waits for textarea, types with human_typing(), Ctrl+Enter
- follow.py: clicks [data-testid="follow"], saves to follows DB table for unfollow tracking
- unfollow.py: queries DB for follows older than 7 days, navigates to profile, clicks Following -> confirm
- quote_tweet.py: clicks retweet -> quote option, types commentary, clicks post

### content/content_moderator.py - Content Validation

Validation checks: empty, too short (<3 chars), too long (>280 chars), banned patterns (URLs, hashtags, CTAs, bot reveals), banned words (configurable via .env), excessive punctuation, all caps.

Quality scoring (0-1 scale): length sweet spot, word diversity, sentence count, absence of generic phrases, questions present, personality markers.

Generic detection: rejects "i agree", "good point", "so true", "100%", "interesting", "nice".

### content/content_cache.py - Reply Caching

Two-tier: exact match (MD5 hash) and semantic match (Jaccard similarity, 0.7 threshold). Entries expire after 30 days. Cleanup runs every 100 accesses. is_duplicate_reply() prevents posting same reply to different tweets.

---

## Database Schema

### data/bot.db

```sql
posts           -> id, text_hash, tweet_id, topic, pillar, format, score, created_at
replies         -> id, text_hash, our_tweet_id, replied_to_id, created_at
engagement_log  -> id, action, target_id, timestamp
follows         -> id, user_id, username, followed_at, followed_back, unfollowed_at
conversions     -> id, tweet_text, tweet_url, reply_text, keyword, intent_score,
                   intent_label, reply_type, created_at
reply_cache     -> id, tweet_hash, original_text, generated_reply, quality_score,
                   created_at, last_used, usage_count
```

### data/rate_limiter.db

```sql
action_history  -> id, action_type, timestamp, success, duration_ms, target_id, notes
daily_summary   -> date, likes, replies, follows, unfollows, posts, quotes, errors
```

---

## Configuration Reference

All config loaded from .env (local) or environment variables (GitHub Actions).

| Setting | Default | What it controls |
|---------|---------|-----------------|
| ANTHROPIC_API_KEY | (required) | Claude API authentication |
| SEARCH_KEYWORDS | AI tools,python automation,... | Topic keywords for tweet search |
| INTENT_KEYWORDS | no engagement,need clients,... | Pain-based keywords for lead discovery |
| CONTENT_PILLARS | ai:...,hustle:...,journey:... | Rotating daily tweet themes |
| VIRAL_HOOKS | hot_take,question,... | Tweet format styles |
| LIKE_PROBABILITY | 0.6 | Base chance to like (all intent levels) |
| REPLY_PROBABILITY | 0.25 | Base chance to reply (LOW intent only) |
| FOLLOW_PROBABILITY | 0.15 | Base chance to follow (LOW intent only) |
| MAX_LIKES_PER_DAY | 20 | Hard daily cap |
| MAX_REPLIES_PER_DAY | 5 | Hard daily cap |
| MAX_FOLLOWS_PER_DAY | 10 | Hard daily cap |
| MAX_QUOTES_PER_DAY | 2 | Hard daily cap |
| ACTIVE_START_HOUR | 5 | UTC hour bot starts (8am EAT) |
| ACTIVE_END_HOUR | 20 | UTC hour bot stops (11pm EAT) |
| DAILY_TWEET_START_HOUR_UTC | 7 | Tweet window start (10am EAT) |
| DAILY_TWEET_END_HOUR_UTC | 10 | Tweet window end (1pm EAT) |
| BANNED_WORDS | viagra,cialis,... | Blocked words in generated content |
| AI_MODEL | claude-haiku-4-5-20251001 | Primary Claude model |

---

## GitHub Actions Deployment

Workflow: .github/workflows/run-bot.yml

Schedule: Runs at 06:00, 10:00, 14:00, 18:00 UTC (9am, 1pm, 5pm, 9pm EAT).

Required secrets:

| Secret | Description |
|--------|-------------|
| ANTHROPIC_API_KEY | Claude API key |
| SESSION_JSON_B64 | Base64-encoded session.json cookies |

What happens each run: checkout code -> install dependencies + Playwright -> restore cached data -> decode session cookies from secret -> clear stale session state -> run bot with 50-min timeout -> cache data for next run.

All config values are passed as environment variables in the workflow file.

---

## Known Limitations

1. **Intent scoring uses substring matching.** "I don't need clients" scores as HIGH because "need clients" is found. No negation awareness.

2. **Session manager uses local time.** datetime.now().hour works on GitHub Actions (UTC) but breaks on local machines in non-UTC timezones.

3. **Tweet URLs not logged.** The tweet_url field in conversion tracking is always empty.

4. **Content moderator validates input tweets.** Banned pattern checks (hashtags, mentions) run on the tweet being replied to, not just generated content.

5. **Extended breaks waste GitHub Actions time.** 20% chance of 2-4 hour break in a 50-minute CI run.

6. **Only 5 tweets per search.** Often yields 2-3 likes and 0-1 replies per cycle.

7. **No 280-char enforcement in code.** Constraint is in the prompt but not enforced post-generation.

---

## Setup

### Local Development

```bash
git clone https://github.com/keepdaping/x-automation-bot.git
cd x-automation-bot
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Edit .env - add your ANTHROPIC_API_KEY
python create_session.py    # Opens browser for manual X login
python run_bot.py           # Start the bot
python dashboard.py         # Open stats dashboard
```

### GitHub Actions

1. Go to repo Settings -> Secrets -> Actions
2. Add ANTHROPIC_API_KEY (from console.anthropic.com)
3. Add SESSION_JSON_B64 (run: python -c "import base64; print(base64.b64encode(open('session.json','rb').read()).decode())")
4. Workflow runs automatically at 6, 10, 14, 18 UTC
5. Manual trigger: Actions tab -> Run workflow
