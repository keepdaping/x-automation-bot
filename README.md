Here is the **full, updated README.md** file for your X Automation Bot project.  
Copy-paste this entire content directly into your `README.md` file.

```markdown
# X Automation Bot v2

Automated lead generation & growth system for X (Twitter).  
Uses Claude AI for smart content generation and Playwright for undetectable browser automation.

**Not a simple posting bot.**  
This is a **targeted engagement machine** that:
- Finds high-intent users (pain signals: "need clients", "no engagement", "struggling to grow")
- Classifies intent (HIGH / MEDIUM / LOW)
- Replies with curiosity-driven prompts on HIGH-intent tweets
- Tracks every reply → outcomes (replies back, follows, DMs)
- Learns what works → improves future replies

Goal: Drive **profile clicks → DMs → real clients**.

---

## How It Works (High-Level Flow)

```
python run_bot.py
  |
  +-- Config.validate()                 → checks API key, probabilities, keywords
  +-- init_db()                         → creates SQLite tables (posts, follows, conversions, interactions)
  +-- init_rate_limiter()               → enforces daily/hourly limits + spacing
  +-- init_session_manager()            → human-like active hours + session/break timing
  |
  +-- BrowserManager.start()            → launches stealth Chromium
  |   +-- loads session.json cookies
  |   +-- injects anti-detection scripts
  |   +-- goes to x.com/home
  |
  +-- check_authenticated()             → verifies login via DOM selectors
  |
  +-- MAIN LOOP:
      |
      +-- should_be_active()?           → checks UTC hour vs ACTIVE_START/END (5-20 UTC)
      |   → No → sleep until next window
      |
      +-- start_session()               → sets random session duration (20-45 min)
      |
      +-- _check_and_post_daily()       → independent daily tweet posting
      |   → if in window (7-10 UTC) + not posted today → generate & post
      |
      +-- should_take_action()?         → enforces natural pacing (min 30-180s gaps)
      |   → No → wait 5-15s → continue
      |
      +-- run_engagement(page, keyword) → one full cycle:
          +-- pick keyword (60% topic, 40% pain/intent)
          +-- search_tweets() → returns up to 5 tweet elements
          +-- for each tweet:
              +-- extract text & metrics
              +-- score_intent() → HIGH(3)/MEDIUM(2)/LOW(1)
              +-- LIKE (60% base, always attempted if limit allows)
              +-- REPLY (intent-based):
              |   HIGH → curiosity reply 100%
              |   MEDIUM → standard reply 30%
              |   LOW → standard reply 25%
              +-- FOLLOW (intent-scaled: HIGH=60%, MEDIUM=30%, LOW=15%)
              +-- QUOTE (10% chance, max 2/day)
              +-- log_conversion() for intent ≥ 2
              +-- log_reply() to feedback system (intent + style + text)
      |
      +-- session_manager.record_action()
      +-- is_session_complete()? → end_session() + take break (30-120 min)
      +-- natural pause (30-180s)
```

---

## Feedback Loop (Self-Improving Replies)

Every reply & follow is tracked in `data/bot.db → interactions` table.

**What is tracked:**
- tweet_id, reply_id, user_handle
- tweet_text, reply_text
- intent (HIGH/MEDIUM/LOW)
- reply_style ("curiosity", "standard", etc.)
- got_reply_back, got_follow, got_dm (updated periodically)
- score (weighted: 3×reply + 5×follow + 10×DM)

**How outcomes are updated:**
- Background scheduler (`core/scheduler.py`) runs every ~90–110 minutes
- Uses `BrowserManager` to check:
  - Is following? (`check_is_following`)
  - Did they reply to our tweet? (`check_user_replied`)
  - DM received? (placeholder – hard to detect safely)

**How to see results:**
```bash
python dashboard.py
```
→ Open `dashboard.html` in browser  
→ Scroll to **"Reply & Follow Performance by Intent & Style"** table  
→ See which reply styles actually get DMs/follows/replies

Use this data to tweak `content/prompts.py` (e.g. double down on winning styles).

---

## Architecture Overview

```
run_bot.py                  → Entry point, main loop, daily tweet, session control
config.py                   → All .env loading & validation
database.py                 → SQLite tables & helpers (posts, follows, conversions, interactions)
dashboard.py                → HTML report with charts + reply performance table
logger_setup.py             → Loguru configuration

content/                    → AI content generation
├── engine.py               → Calls Claude, caches replies, handles fallbacks
├── prompts.py              → All system prompts (daily tweet, reply, curiosity, quote)
├── content_cache.py        → Exact + semantic reply deduplication
└── content_moderator.py    → Quality scoring, banned words/patterns

core/                       → Bot brain
├── engagement.py           → Main cycle: search → score → route → execute
├── rate_limiter.py         → Daily/hourly limits + cluster/spacing protection
├── session_manager.py      → Human-like active hours, session duration, breaks
├── error_handler.py        → Error classification + cooldown/recovery
└── scheduler.py            → Background APScheduler for outcome checking

actions/                    → Browser actions via Playwright
├── tweet.py                → Post original tweet
├── like.py                 → Like tweet
├── reply.py                → Reply with human typing + feedback logging
├── follow.py               → Follow user + feedback logging
├── unfollow.py             → Unfollow stale follows
└── quote_tweet.py          → Quote tweet with commentary

browser/                    → Playwright management
├── browser_manager.py      → Launch, cookies, auth check, outcome checks
└── stealth.py              → Anti-detection injections

search/
└── search_tweets.py        → Keyword search, scroll, tweet extraction & filtering

utils/                      → Helpers
├── human_behavior.py       → Natural typing, scrolling, delays
├── intent_scorer.py        → Phrase-based intent scoring
├── engagement_score.py     → Tweet quality scoring
└── ... (selectors, tweet text, etc.)
```

---

## Setup Instructions

### Local Development

```bash
# 1. Clone & enter directory
git clone https://github.com/keepdaping/x-automation-bot.git
cd x-automation-bot

# 2. Create & activate venv
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 4. Setup .env
cp .env.example .env
# Edit .env → add your ANTHROPIC_API_KEY

# 5. Create browser session (manual login)
python create_session.py
# → Opens browser → log in to @KeepdapingB → press Enter when done

# 6. Run the bot
python run_bot.py

# 7. View performance
python dashboard.py   # opens dashboard.html in browser
```

### GitHub Actions (Cloud Run)

1. Add secrets in repo → Settings → Secrets and variables → Actions:
   - `ANTHROPIC_API_KEY`
   - `SESSION_JSON_B64` (base64 of your `session.json`)

2. Workflow runs automatically: 6am, 10am, 2pm, 6pm UTC (9am, 1pm, 5pm, 9pm EAT)

---

## Monitoring & Improvement

- **Dashboard** (`python dashboard.py`) → live stats + reply performance table
- **Database** (`data/bot.db`) → use DB Browser for SQLite to inspect `interactions`
- **Logs** → check console or `data/error_history.log`

To improve conversions:
1. Run bot for 2–3 days
2. Open dashboard → look at "Reply & Follow Performance" table
3. Identify winning `intent` + `reply_style` combos
4. Tweak `content/prompts.py` to use more of the winning style

---

## Known Limitations & Roadmap

- Intent scoring is phrase-based (no negation handling yet)
- DM detection is placeholder (hard to do safely)
- No auto-style selection yet (manual dashboard review)
- GitHub Actions timeout = 50 min (can be extended)

Roadmap ideas:
- Auto-prefer winning reply styles
- Better DM detection via notifications
- A/B test reply variants
- Export leads to Google Sheets

Questions? DM @KeepdapingB or open an issue.

Happy growing!
```

This is the **complete, polished README** — accurate, professional, and conversion-focused.  
Replace your current `README.md` with this full content.

Let me know if you want:
- Badges (stars, license, Python version)
- Screenshots embedded
- Or the next improvement (auto-style selection, better DM detection, etc.)

You're all set — bot + docs are now ready for real growth! 🚀