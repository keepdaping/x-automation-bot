# X Automation Bot — Keepdaping

A production-grade Twitter/X engagement system for high-intent lead generation. Finds founders, freelancers, and developers publicly expressing pain around automation, client acquisition, or AI tooling — then engages them using an **autonomous ReAct agent** that reasons about every action before taking it.

Built with **Playwright** (browser automation), **Claude API** (content generation + intent scoring), **SQLite** (state + learning), and a **self-learning layer** (UCB1 bandits + Bayesian policy engine) that continuously improves decisions based on real outcome data.

> **Architecture:** v3 — ReAct AgentController (Reason + Act loop).
> The bot no longer follows a static pipeline. It now *thinks*, then *acts*, then *observes*, in a continuous cycle driven by `core/agent_controller.py`.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [ReAct Agent — How It Thinks](#3-react-agent--how-it-thinks)
4. [Self-Learning System](#4-self-learning-system)
5. [Execution Flow](#5-execution-flow)
6. [Key Components](#6-key-components)
7. [AI Integration](#7-ai-integration)
8. [Current Features](#8-current-features)
9. [Configuration Guide](#9-configuration-guide)
10. [Deployment Guide](#10-deployment-guide)
11. [Safety & Anti-Ban Design](#11-safety--anti-ban-design)
12. [Known Limitations](#12-known-limitations)
13. [Future Improvements](#13-future-improvements)
14. [System Evolution](#14-system-evolution)

---

## 1. Project Overview

### What it does

The bot runs four concurrent functions:

1. **Posts one original tweet per day** — AI-generated on a rotating content pillar schedule, designed to attract inbound DMs
2. **Engages high-intent users** — searches for people expressing pain around growth, automation, or client acquisition; replies, follows, and quotes using an autonomous ReAct agent
3. **Tracks and measures outcomes** — every reply is logged; browser-based checks detect if the target replied back, followed, or DM'd; outcomes feed back into the decision system
4. **Learns from outcomes daily** — a UCB1 bandit system and Bayesian policy engine continuously update action probabilities and search phrase selection based on what actually drives conversions

### Business goal

Drive inbound DMs and profile clicks from founders, freelancers, and developers who need automation help — without cold outreach or hard selling. Every piece of content is designed to make the target think *"this person understands my problem."* The system self-improves: strategies that generate replies and follows get reinforced; strategies that don't are automatically deprioritised.

### Tech stack

| Layer | Technology |
|---|---|
| Browser control | Playwright (sync API, Chromium) |
| Content generation | Anthropic Claude API (Haiku by default) |
| Agent reasoning | Claude API via AgentController |
| State storage | SQLite (`bot.db` + `rate_limiter.db`) |
| Background tasks | APScheduler BackgroundScheduler |
| Language | Python 3.10+ |

---

## 2. System Architecture

```
x-automation-bot/
│
├── run_bot.py                    # Entry point — BotController main loop
├── config.py                     # All settings, loaded from .env at startup
├── database.py                   # SQLite operations (posts, replies, follows)
├── feedback.py                   # Interaction outcome tracking (interactions table)
│
├── browser/
│   ├── browser_manager.py        # Playwright lifecycle: launch, auth, restart
│   └── stealth.py                # Anti-detection: launch args, JS injections
│
├── core/
│   ├── agent_controller.py       # ★★ PRIMARY: ReAct autonomous agent
│   │                             #    Implements THOUGHT → ACTION → OBSERVE loop
│   │                             #    Owns: search, intent analysis, memory, self-correction
│   ├── engagement.py             # Thin wrapper — delegates to AgentController
│   ├── pipeline.py               # Per-tweet routing (used by agent internally)
│   ├── reply_handler.py          # Reply generation + bandit style selection
│   ├── follow_handler.py         # Follow action + feedback logging
│   ├── quote_handler.py          # Quote-tweet action
│   ├── generator.py              # Raw Claude API calls with error handling
│   ├── rate_limiter.py           # Daily/hourly/cluster limits (rate_limiter.db)
│   ├── session_manager.py        # Active hours, session duration, breaks
│   ├── error_handler.py          # Error classification, backoff, detection cooldown
│   ├── scheduler.py              # BackgroundScheduler: housekeeping + learning
│   │
│   ├── outcome_updater.py        # ★ Browser-checks past replies; marks stale rows
│   ├── reward_aggregator.py      # ★ Read-only stats (style/intent/phrase) + Bayesian smooth
│   ├── bandit.py                 # ★ UCB1 bandit — reply style + phrase selection
│   ├── policy.py                 # ★ Evidence-adjusted action probabilities (TTL-cached)
│   └── learning.py               # ★ Daily loop: outcomes → bandit rewards
│
├── content/
│   ├── engine.py                 # Single entry point for all content generation
│   ├── prompts.py                # System prompts, voice rules, tweet patterns
│   ├── content_moderator.py      # Validates and scores generated content
│   └── content_cache.py          # Reply cache (exact + semantic dedup)
│
├── actions/
│   ├── reply.py                  # Types and submits a reply via Playwright
│   ├── follow.py                 # Clicks Follow, saves to DB
│   ├── like.py                   # Clicks Like
│   ├── tweet.py                  # Posts an original tweet
│   ├── quote_tweet.py            # Quotes a tweet with AI commentary
│   └── unfollow.py               # Unfollows non-reciprocators after N days
│
├── search/
│   └── search_tweets.py          # Navigates to search, scrolls, filters, returns tweets
│
└── utils/
    ├── intent_scorer.py          # ★ Multi-pass pain signal detection (70+ phrases)
    ├── llm_intent_scorer.py      # Claude-based intent scoring (opt-in via INTENT_MODE)
    ├── human_behavior.py         # Burst typing, random delays, natural scrolling
    ├── tweet_metrics.py          # Extracts like/reply/retweet counts from DOM
    ├── engagement_score.py       # Scores tweet quality for search filtering
    ├── tweet_text.py             # Extracts visible text from tweet element
    ├── language_handler.py       # Filters non-English tweets
    └── selectors.py              # All CSS/aria selectors in one place
```

### How the layers connect

```
Config (.env)
    │
    ▼
BotController (run_bot.py)
    ├── SessionManager              ← controls WHEN to run
    ├── RateLimiter                 ← controls HOW OFTEN to run
    ├── BrowserManager              ← ONE Playwright instance for everything
    ├── BackgroundScheduler         ← housekeeping + daily learning cycle
    │
    ├── Daily Tweet Path
    │     └── ContentEngine.generate_daily_tweet()
    │               └── Claude API + 6 quality gates
    │
    └── Engagement Cycle (core/engagement.py)
              └── AgentController.run_cycle()    ← ★ ALL REASONING LIVES HERE
                    │
                    ├── strategy_lookup_tool()   THOUGHT: what do the stats say?
                    │     └── RewardAggregator   → style rewards, phrase rewards, rate pressure
                    │
                    ├── _choose_search_phrase()  THOUGHT: 75% intent / 25% UCB1 bandit
                    │
                    ├── search_tool(phrase)      ACTION: navigate + return tweets
                    │     └── 3-tier fallback    exact → simplified → backup phrase
                    │
                    └── Per-tweet loop:
                          ├── analyze_intent_tool()    ACTION: score_intent + LLM override
                          ├── _check_memory()          THOUGHT: prior interaction with user?
                          ├── PolicyEngine             STRATEGY: evidence-adjusted probabilities
                          ├── _decide_action()         THOUGHT: choose reply/follow/like/scroll
                          └── engagement_action_tool() ACTION: execute chosen action
                                └── _do_reply()         → self-correction loop (up to 3x)
                                      ├── generate candidate
                                      ├── ContentModerator.validate()
                                      ├── signal_density / named_role gates
                                      └── if failed → THOUGHT: diagnose + regenerate

    Self-Learning Layer (background, daily):
              ├── OutcomeUpdater     → marks stale interactions as checked
              ├── LearningLoop       → reads outcomes → updates bandits
              └── RewardAggregator   → read-only stats for policy engine
```

---

## 3. ReAct Agent — How It Thinks

`core/agent_controller.py` is the primary execution hub. Every decision is reasoned before it is executed, and every result is observed before the next step. The console logs make this reasoning visible in real time.

### The THOUGHT → ACTION → OBSERVE pattern

```
[THOUGHT ] Pre-flight: checking detection cooldown.
[ACTION  ] strategy_lookup_tool()
[OBSERVE ] Rate remaining={reply:12, follow:9, like:18} | pressure=18% | best_style=grok
[THOUGHT ] Consulting bandit rewards and intent keyword pool for search phrase.
[THOUGHT ] Search phrase: 'struggling to get clients' (75% intent-targeted path)
[ACTION  ] search_tool(query='struggling to get clients')
[OBSERVE ] Found 8 tweets for 'struggling to get clients'
[THOUGHT ] Found 8 tweets. Will analyze intent and choose engagement action for each.

[THOUGHT ] — Tweet 1/8 —
[ACTION  ] analyze_intent_tool(text='Every tool I try breaks after a week...')
[OBSERVE ] Intent=HIGH (score=3)
[THOUGHT ] Memory: no prior interaction with @founder_jane.
[THOUGHT ] Intent=HIGH | policy: reply=0.72, follow=0.18 | remaining: replies=12, follows=9
[THOUGHT ] Decision: execute 'reply' on this tweet.
[ACTION  ] engagement_action_tool(action=reply)
[OBSERVE ] Moderation PASSED (style=grok, quality=0.76, signal=3/4, has_role=True)
[OBSERVE ] Reply posted [style=grok] | reply_id=1923847561234

[THOUGHT ] — Tweet 3/8 —
[ACTION  ] analyze_intent_tool(text='n8n is finally working!')
[OBSERVE ] Intent=LOW (score=1)
[THOUGHT ] Memory: already replied to @n8n_user today (style=standard). Switching to 'follow'.
[THOUGHT ] Decision: execute 'follow' on this tweet.
```

### Self-correction loop

When generated reply text fails ContentModerator gates, the agent does not silently drop it. It diagnoses the specific failure and requests a corrected generation:

```
[OBSERVE ] Moderation FAILED — gates: signal_density | signal_density=1/4 | has_named_role=False | quality=0.38
[THOUGHT ] Self-correction attempt 2/3. Last failure: 'signal_density'. Trying style='curiosity'.
           Correction hint sent to LLM: "Include a specific tool name, a number,
           and a concrete outcome or consequence."
[OBSERVE ] Moderation PASSED (style=curiosity, quality=0.61, signal=2/4, has_role=True)
[OBSERVE ] Reply posted [style=curiosity] | reply_id=1923847561299
```

### Four agentic properties

| Property | Mechanism |
|---|---|
| **Autonomy** | `strategy_lookup_tool()` reads Bandit + RewardAggregator stats before every cycle; the agent selects search phrases and reply styles based on live reward data, not hardcoded rules |
| **Self-Correction** | `_do_reply()` loops up to `MAX_REGENERATIONS=3` times; on each failure it diagnoses which gate failed (`signal_density`, `named_role`, `generic`) and adjusts the LLM prompt |
| **Memory Integration** | `_check_memory()` queries the `interactions` table before each tweet; if a user was replied to today, the agent switches to `follow` instead of replying again |
| **Rate-Pressure Awareness** | `rate_pressure` is computed at cycle start; if `> 0.85`, the agent routes all actions to `scroll_timeline` until pressure drops |

### Inviolable floors

These two probability floors are enforced in `_decide_action()` and **cannot be reasoned around**. They guarantee the learning loop always has signal:

```
reply_prob  >= 0.15   (MIN_REPLY_PROB)
follow_prob >= 0.05   (MIN_FOLLOW_PROB)
```

If all tweets score LOW intent and every probability roll misses, the **forced-fallback reply** fires: one guaranteed reply on the first tweet in the results, regardless of intent score.

---

## 4. Self-Learning System

The bot replaces hardcoded action probabilities with an adaptive, reward-driven decision system. No ML frameworks are required — UCB1 bandits, Bayesian smoothing, and a daily learning loop are built entirely on SQLite.

### Data flow: interactions → reward → policy → action

```
Every reply sent
    │
    ▼
interactions table  (intent, reply_style, tweet_id, user_handle, sent_at)
    │
    │  [15% of cycles, main thread — OutcomeUpdater]
    ▼
Browser checks:  did they reply back?  did they follow?
    │  Updates: got_reply_back, got_follow, outcome_score
    │
    │  [every ~100 min, background thread — scheduler]
    ▼
Stale rows marked checked_at  (rows > 48h without browser check)
    │
    │  [once per day, background thread — LearningLoop]
    ▼
Reply bandit updated   AVG(outcome_score) per style → normalised reward → UCB1 arms
Phrase bandit updated  time-weighted conversion_yield per phrase → UCB1 arms
    │
    │  [every cycle start — AgentController.strategy_lookup_tool()]
    ▼
RewardAggregator snapshot → rate_pressure, best_style, keyword_rewards
    │
    │  [every tweet — PolicyEngine]
    ▼
evidence-adjusted probabilities  (reply_prob, follow_prob, style_weights)
    + minimum floors enforced (reply >= 0.15, follow >= 0.05)
    │
    ▼
UCB1 bandit selects:  grok | curiosity | standard
                      search phrase
```

### Components

| Module | File | Role |
|--------|------|------|
| OutcomeUpdater | `core/outcome_updater.py` | Browser-checks past replies; marks stale rows |
| RewardAggregator | `core/reward_aggregator.py` | Read-only stats grouped by style / intent / phrase |
| UCB1Bandit | `core/bandit.py` | Adaptive arm selection with sliding-window memory + zero-reward boost |
| PolicyEngine | `core/policy.py` | Converts intent + reward data → bounded action probabilities with floors |
| LearningLoop | `core/learning.py` | Daily batch update: pushes outcomes into bandit arms |

### How the bandit learns

The reply-style bandit (`reply_style` namespace) has three arms: `grok`, `curiosity`, `standard`.

Each arm stores `(trials, total_reward)`. On every daily learning cycle, the bandit receives `normalised_avg_outcome_score` (in [0,1]) as a reward for each style. UCB1 selects:

```
score(arm) = avg_reward(arm) + C × √( ln(total_trials) / trials(arm) )
```

The confidence term is large when an arm is under-tried (exploration), small when well-tried (exploitation). A 15% epsilon floor ensures no arm is permanently abandoned. A sliding window (`WINDOW_SIZE=30`) prevents stale history from dominating.

**Zero-reward boost:** When all arms have zero reward (cold start), epsilon raises to 0.40, ensuring all styles are explored before the policy commits to one.

### How the policy calibrates probabilities

```
baseline reply_prob (from Config)
    ± adjustment bounded to [-0.10, +0.20]   ← only fires with >= 10 samples
    × AGGRESSION_LEVEL (global multiplier)
    → minimum floors applied (reply >= 0.15, follow >= 0.05)
    → final reply_prob
```

**Penalty behaviour:** The policy does not penalise `avg_outcome_score = 0.0`. Zero is the default value for unchecked interactions. Penalty fires only when `0 < avg < 0.5` — a non-zero but weak result that represents genuine underperformance.

### Cold-start protection

When total checked interactions < 10, the policy switches to **cold-start mode**:

- All reward-based probability adjustments are skipped
- Style weights widened to `{grok: 1.5, curiosity: 1.5, standard: 1.0}` for broader exploration
- Baseline Config probabilities used directly

---

## 5. Execution Flow

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
  ├── 7. log "AgentController (ReAct)" mode active
  ├── 8. start_scheduler()            Start BackgroundScheduler (daemon thread)
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
  ├── _check_and_post_daily()           ← independent of engagement
  │     DB count gate → in-memory gate → date gate → generate → post
  │
  └── run_engagement(page)              ← delegates to AgentController
```

### One engagement cycle (AgentController.run_cycle)

```
AgentController.run_cycle()
  │
  ├── Pre-flight: detection cooldown check
  │
  ├── strategy_lookup_tool()            THOUGHT: snapshot rewards + rate state
  │     └── RewardAggregator            style_rewards, keyword_rewards, rate_pressure
  │         if rate_pressure > 0.85 → THOUGHT: will use low-cost actions this cycle
  │
  ├── _choose_search_phrase()           THOUGHT: 75% INTENT_KEYWORDS / 25% UCB1 bandit
  │     if strategy has recommended_phrase → log it as context for THOUGHT
  │
  ├── search_tool(phrase)               ACTION: 3-tier fallback search
  │     tier 1: exact phrase
  │     tier 2: simplified (drop first word)
  │     tier 3: backup phrase from bandit
  │
  └── Per-tweet ReAct sub-loop:
        ├── THOUGHT: tweet N/total
        ├── analyze_intent_tool()       ACTION: score_intent + LLM override at boundary
        ├── _check_memory(handle)       THOUGHT: prior interaction? → shift reply → follow
        ├── PolicyEngine                STRATEGY: evidence-adjusted probabilities
        ├── _decide_action()            THOUGHT: rate_pressure + memory + intent + policy
        ├── engagement_action_tool()    ACTION: reply / follow / like / quote / scroll
        │     └── if reply:
        │           └── _do_reply()     self-correction loop (MAX_REGENERATIONS=3)
        │                 ├── _generate_candidate()  → LLM with correction hint on retry
        │                 ├── _analyze_reply()       → validate + signal_density + named_role
        │                 └── if passed: reply_tweet() → rate_limiter.record_action()
        └── OBSERVE: result → refresh rate counts → next tweet

  └── Inviolable floor:
        if actions == 0 → THOUGHT: forcing fallback reply on first tweet
```

### Intent scoring (multi-pass, inside analyze_intent_tool)

```
score_intent(tweet_text)
  ├── Pass 1: single HIGH phrase match        → return 3 immediately
  │     70+ phrases: "need clients", "automation not working", "struggling to get clients"
  │
  ├── Pass 2: struggle-marker accumulation
  │     25 partial frustration markers
  │     2+ markers → return 2; 1 marker + "?" → return 2
  │
  ├── Pass 3: MEDIUM phrase match
  │     phrase + "?" → promoted to 3 (HIGH)
  │     phrase, no "?" → return 2
  │
  ├── Pass 4: multiple questions
  │     count("?") >= 2 → return 2
  │
  └── Default → return 1 (LOW)

  [If score == 2 and REFLECTION_ENABLED]:
  └── LLMIntentScorer.score()   THOUGHT: LLM override for nuanced boundary cases
        negation detected → downgrade; intent adjusted → log as LLM-override
```

---

## 6. Key Components

### AgentController (`core/agent_controller.py`)

The primary execution hub. Implements the full ReAct loop for one engagement cycle.

**Callable tools:**

| Tool | Method | Purpose |
|---|---|---|
| `strategy_lookup_tool` | `strategy_lookup_tool()` | Reads RewardAggregator + rate state before cycle |
| `search_tool` | `search_tool(query)` | 3-tier fallback search; returns tweet elements |
| `analyze_intent_tool` | `analyze_intent_tool(text)` | score_intent + optional LLM boundary override |
| `engagement_action_tool` | `engagement_action_tool(action, tweet, ...)` | Routes Like/Follow/Reply/Quote/Scroll |

**Internal reasoning:**

| Method | Role |
|---|---|
| `_check_memory(handle)` | Queries `interactions` for prior contact; informs action decision |
| `_decide_action(...)` | Core reasoning: intent + policy + memory + rate_pressure → action type |
| `_do_reply(...)` | Self-correction loop; diagnoses ContentModerator gate failures |
| `_generate_candidate(...)` | LLM generation with correction hint on retry |
| `_choose_search_phrase(...)` | 75/25 split: INTENT_KEYWORDS vs UCB1 bandit |
| `_thought() / _act() / _observe()` | Structured ANSI-colored console logging |

### Rate Limiter (`core/rate_limiter.py`)

Four independent enforcement layers — all configurable via `.env`:

| Layer | Default | Description |
|---|---|---|
| Daily limit | e.g. 15 replies/day | Hard cap per action type |
| Hourly limit | `daily ÷ 12` | Auto-calculated |
| 2-min cluster | 5 same actions | Prevents action bursts |
| 10-min global | 8 total actions | Prevents any burst pattern |

Per-action minimum spacing: replies 120s, posts 300s, follows 60s, likes 30s.

The agent checks `rate_limiter.can_perform_action()` inside `engagement_action_tool()` before every action — this check is inviolable and cannot be bypassed by agent reasoning.

### Content Moderator (`content/content_moderator.py`)

Rule-based scoring and validation. No AI used here.

| Method | Description |
|---|---|
| `validate(text)` | Length, banned patterns, punctuation; returns `(bool, reason)` |
| `is_generic(text)` | Multi-word low-effort phrase detection |
| `has_named_role(text)` | Requires VA, junior, CFO, founder, etc. |
| `signal_density(text)` | 0–4 score across: tool name, number, outcome verb, consequence phrase |
| `score_quality(text)` | Composite 0–1 score used for cache prioritisation |

The agent's `_analyze_reply()` function runs all gates and returns structured diagnosis:

```python
{
    "passed": bool,
    "gate_failed": str | None,   # hard validation reason
    "signal_score": int,         # 0-4
    "has_role": bool,
    "quality": float,
    "is_generic": bool,
    "soft_failures": list,       # ["signal_density", "named_role", ...]
}
```

### Session Manager (`core/session_manager.py`)

| Behavior | Default |
|---|---|
| Active hours | 08:00–23:00 UTC |
| Session length | 20–45 min |
| Actions per session | 8–12 target |
| Break length | 30–120 min |
| Browse-only sessions | 5% chance |

### Feedback Tracker (`feedback.py`)

Logs every reply action to `bot.db/interactions`. Key columns:

- `tweet_id`, `reply_id`, `user_handle`
- `tweet_text`, `reply_text`, `intent`, `reply_style`
- `got_reply_back`, `got_follow`, `got_dm` (populated by OutcomeUpdater)
- `outcome_score` — weighted: reply×3, follow×2, DM×5

---

## 7. AI Integration

### Where Claude is used

| Use case | Function | Model | Token budget |
|---|---|---|---|
| Engagement reply (grok style) | `generate_contextual_reply()` | Haiku (configurable) | 150 |
| Engagement reply (standard) | `content_engine.generate_reply()` | Haiku (configurable) | 150 |
| Engagement reply (curiosity) | `content_engine.generate_curiosity_reply()` | Haiku (configurable) | 150 |
| Daily original tweet | `content_engine.generate_daily_tweet()` | Haiku (configurable) | 150 |
| Quote tweet commentary | `content_engine.generate_quote_text()` | Haiku (configurable) | 150 |
| Intent scoring (opt-in) | `LLMIntentScorer.score()` | Haiku | 300 |

### Decision mechanism matrix

| Decision | Mechanism |
|---|---|
| Which search phrase to use? | **Agent** (strategy_lookup_tool → 75% INTENT_KEYWORDS / 25% UCB1 bandit) |
| Should we reply to this tweet? | **Agent** (intent + memory + policy + rate_pressure → _decide_action) |
| Which reply style to use? | **Bandit** (UCB1 across grok / curiosity / standard) |
| What to reply with | **AI** (Claude, system prompt by style; corrected prompt on retry) |
| Is the reply high quality? | **Rules** (ContentModerator: validate + signal_density + named_role + generic) |
| Did the ContentModerator fail? | **Agent** (diagnoses gate, adjusts prompt, retries up to 3×) |
| Is the reply a duplicate? | **Rules** (SHA-256 hash + Jaccard similarity) |
| Should we follow this user? | **Agent** (_decide_action: memory + policy + rate_pressure) |
| Intent classification (fast) | **Rules** (multi-pass keyword scoring, 70+ pain phrases + accumulation) |
| Intent classification (deep) | **AI** (Claude Haiku, negation-aware, boundary cases only) |
| What to post as daily tweet | **AI** (Claude, pillar + hook guided) |
| Does the daily tweet pass? | **Rules** (6-gate pipeline: signal_density, named_role, etc.) |
| When to take breaks | **Rules** (SessionManager) |
| Rate limit enforcement | **Rules** (RateLimiter, 4 layers — inviolable) |
| Minimum activity guarantee | **Agent** (MIN_REPLY_PROB floor + forced-fallback reply) |
| Outcome measurement | **Browser** (OutcomeUpdater, Playwright, main thread) |

---

## 8. Current Features

- **ReAct autonomous agent** — THOUGHT/ACTION/OBSERVE loop drives all engagement decisions; reasoning is visible in real-time console output
- **Strategy-first cycle** — agent reads RewardAggregator before first search; chooses search phrase and style bias from live reward data
- **Self-correcting reply generation** — ContentModerator gate failures trigger diagnosed regeneration with specific correction hints (up to 3 attempts)
- **Memory-aware engagement** — agent queries `interactions` table before each tweet; avoids double-replying to the same user on the same day
- **Rate-pressure routing** — if daily limits are >85% consumed, agent proactively switches to `scroll_timeline` for the remainder of the cycle
- **Daily tweet posting** — one original tweet per day on rotating content pillars; triple-gated against re-posting (DB COUNT, in-memory flag, date check)
- **Intent-based engagement** — HIGH intent users always get a reply; MEDIUM and LOW users engage at policy-adjusted probability with inviolable minimum floors
- **Multi-pass intent scoring** — 70+ HIGH-intent phrases, 25-marker struggle accumulation, and question-based promotion ensure nuanced human frustration is never missed
- **Intent-first search** — 75% of search cycles use explicit pain-signal phrases; 25% use UCB1 bandit over broader pool
- **Forced-fallback reply** — if a cycle produces zero actions, one reply is guaranteed on the first tweet; prevents silent sessions from creating learning gaps
- **Inviolable probability floors** — `reply_prob >= 0.15`, `follow_prob >= 0.05` enforced after the aggression multiplier; cannot be overridden by learning or configuration
- **Curiosity replies** — high-intent users receive a curiosity prompt designed to trigger a DM
- **Follow strategy** — follows proportional to intent; unfollows non-reciprocators after `UNFOLLOW_AFTER_DAYS` days
- **Quote tweets** — policy-adjusted chance per tweet with AI-generated commentary
- **Content quality gates** — 6-layer validation before any daily tweet posts; silence is preferred over low-quality noise
- **Language filtering** — non-English tweets skipped before engaging
- **Rate limiting** — four layers of enforcement across daily, hourly, cluster, and spacing dimensions
- **Human session simulation** — active hours, random session lengths, browse-only sessions, natural breaks
- **Burst typing** — realistic variable-speed character input to avoid bot detection
- **Decision audit logging** — `[THOUGHT]`, `[ACTION]`, `[OBSERVE]` prefixes provide real-time visibility into agent reasoning
- **Background housekeeping** — scheduler keeps the interactions table clean without blocking the main loop
- **Detection cooldown** — 24h automatic cooldown on suspected detection

---

## 9. Configuration Guide

All settings are loaded from `.env`. No code changes required for configuration.

### Required

```env
ANTHROPIC_API_KEY=sk-ant-...
```

### Search & engagement

```env
SEARCH_KEYWORDS=struggling to get clients,need help with automation,no engagement on posts,how to get clients,no sales
INTENT_KEYWORDS=struggling to get clients,need more clients,can't find clients,automation not working,freelancing is so hard,not getting results
LIKE_PROBABILITY=0.6
REPLY_PROBABILITY=0.25
FOLLOW_PROBABILITY=0.15
AGGRESSION_LEVEL=0.6
INTENT_MODE=keyword
```

### Daily tweet

```env
DAILY_TWEET_ENABLED=true
DAILY_TWEET_START_HOUR_UTC=10
DAILY_TWEET_END_HOUR_UTC=13
CONTENT_PILLARS=money:Making money online and financial freedom,building:Building products and side projects,journey:Personal growth and lessons learned
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
ACTIVE_START_HOUR=8
ACTIVE_END_HOUR=23
SESSION_DURATION_MIN=20
SESSION_DURATION_MAX=45
BREAK_DURATION_MIN=30
BREAK_DURATION_MAX=120
MIN_ACTION_INTERVAL_SEC=30
MAX_ACTION_INTERVAL_SEC=180
SESSION_CONTINUE_PROBABILITY=0.40
SESSION_BROWSE_ONLY_PROBABILITY=0.05
```

### AI model

```env
AI_MODEL=claude-haiku-4-5-20251001
AI_MAX_TOKENS=150
```

### Browser

```env
HEADLESS_MODE=true
STEALTH_MODE=true
BROWSER_TIMEOUT_MS=30000
SESSION_FILE=session.json
```

### Unfollow strategy

```env
UNFOLLOW_AFTER_DAYS=7
UNFOLLOW_CHECK_PROBABILITY=0.3
```

### Content safety

```env
BANNED_WORDS=viagra,cialis,pharmacy,mlm,pyramid,dropship
```

### Database & logging

```env
DATABASE_PATH=data/bot.db
LOG_LEVEL=INFO
DEBUG=false
```

---

## 10. Deployment Guide

### Prerequisites

- VPS with at least 1 GB RAM (2 GB recommended for Chromium)
- Ubuntu 22.04 or Debian 12 recommended
- Python 3.10+
- Set VPS timezone to UTC: `sudo timedatectl set-timezone UTC`

### Initial setup

```bash
git clone <repo-url>
cd x-automation-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium
```

### Create authenticated session

```bash
python create_session.py   # run once locally with a display
```

Produces `session.json`. Copy to VPS — loaded on every start.

### Environment file

```bash
cp .env.example .env
nano .env   # add ANTHROPIC_API_KEY and adjust settings
```

### Running as a systemd service (recommended)

Create `/etc/systemd/system/xbot.service`:

```ini
[Unit]
Description=X Automation Bot (Keepdaping)
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
sudo journalctl -u xbot -f
```

### Data directory

```
data/
├── bot.db                   # Posts, replies, follows, interactions, conversions
├── rate_limiter.db          # Action history for rate enforcement
├── session_state.txt        # Session/break state (survives restarts)
├── detection_cooldown.txt   # Written on suspected detection event
└── error_history.log        # Timestamped error traces
```

### Reading live logs

The ReAct agent makes its reasoning visible in the log stream:

```
[THOUGHT ] Pre-flight: checking detection cooldown.
[ACTION  ] strategy_lookup_tool()
[OBSERVE ] Rate remaining={reply:12, follow:9} | pressure=18% | best_style=grok
[THOUGHT ] Search phrase: 'struggling to get clients' (75% intent-targeted path)
[ACTION  ] search_tool(query='struggling to get clients')
[OBSERVE ] Found 8 tweets for 'struggling to get clients'
[THOUGHT ] Intent=HIGH | policy: reply=0.72, follow=0.18 | remaining: replies=12
[THOUGHT ] Decision: execute 'reply' on this tweet.
[ACTION  ] engagement_action_tool(action=reply)
[OBSERVE ] Moderation PASSED (style=grok, quality=0.76, signal=3/4, has_role=True)
[OBSERVE ] Reply posted [style=grok] | reply_id=1923847561234
```

Self-correction in the logs:
```
[OBSERVE ] Moderation FAILED — gates: signal_density | signal_density=1/4 | quality=0.38
[THOUGHT ] Self-correction attempt 2/3. Last failure: 'signal_density'. Trying style='curiosity'.
[OBSERVE ] Moderation PASSED (style=curiosity, quality=0.61, signal=2/4, has_role=True)
```

---

## 11. Safety & Anti-Ban Design

### Browser stealth

- Playwright launched without automation flags (`--enable-automation` removed)
- `navigator.webdriver` overridden to `undefined` via JS injection on every page load
- Persistent Chrome profile reused across runs — same fingerprint as a real user
- Cookie-based authentication — no programmatic login flow

### Human behavior simulation

| Mechanism | Detail |
|---|---|
| Burst typing | Characters typed in variable-speed clusters of 3–7, with pauses after punctuation |
| Natural scrolling | Each scroll split into 3–6 random-pixel steps with mid-scroll hesitations |
| Action spacing | Minimum enforced gaps: 30s likes, 120s replies, 300s posts |
| Random delays | All waits use `random.uniform(min, max)` — never fixed intervals |
| Session structure | 20–45 min active, 30–120 min breaks, sleeps outside configured hours |
| Browse-only sessions | 5% of sessions navigate without taking any actions |
| Timeline browsing | 25% of cycles browse the home timeline before searching |

### Four-layer rate limiting

```
Daily cap        → hard limit per action type (configurable)
Hourly cap       → 1/12 of daily limit (auto-calculated)
2-min cluster    → max 5 same action in 2 minutes
10-min global    → max 8 any actions in 10 minutes
```

All four layers checked inside `engagement_action_tool()` before every action.

### Error handling and detection cooldown

- Errors classified per occurrence (recoverable / browser / detection / fatal)
- Recoverable errors: exponential backoff, capped at 5 minutes
- Detection-signature errors (`403`, `blocked`, `detected`): 24-hour full stop, state persisted to disk
- Browser errors: restart attempted before giving up

### Single browser instance

Exactly one Playwright browser context exists for the entire bot lifecycle. The background scheduler uses only SQLite — it never creates a browser, never navigates, and never competes with the main thread.

---

## 12. Known Limitations

### DM detection is a placeholder

`check_for_dm()` always returns `False`. DM-driven conversions (outcome weight ×5) are never populated. The practical outcome_score maximum is 5 (reply=3 + follow=2) rather than the theoretical 10.

### Phrase-to-outcome correlation is indirect

The `interactions` table does not store which search phrase triggered a given reply. Phrase bandit rewards are computed from `search_log.high_intent_found` (a proxy), not from actual downstream `outcome_score`.

### Learning requires observation volume

Meaningful policy adjustments begin after approximately 10 checked interactions per intent tier (~day 7–10 at conservative limits). Cold-start protection ensures stable baseline behavior during this period.

### No test coverage

No automated tests exist. The content moderator, rate limiter, session manager, intent scorer, bandit, policy engine, and AgentController are deterministic and well-suited to unit testing.

---

## 13. Future Improvements

### High priority

| Improvement | Description |
|---|---|
| Direct phrase attribution | Add `search_phrase TEXT` column to `interactions` so phrase bandit rewards are driven by actual `outcome_score` rather than the `search_log` proxy |
| DM detection | Implement `check_for_dm()` via notifications page scan to unlock the ×5 DM reward component |
| Reply quality parity | Apply the same 6-gate pipeline to engagement replies; the self-correction loop would then learn which quality-gated replies perform best |
| Thompson Sampling | Replace UCB1 with Thompson Sampling (Beta distribution per arm) for more principled uncertainty quantification |

### Medium priority

| Improvement | Description |
|---|---|
| Contextual bandit | Extend reply-style bandit to use context features (intent level, engagement_score, time_of_day) as inputs |
| Bandit dashboard | Expose `UCB1Bandit.get_stats()` and `RewardAggregator` outputs for real-time visibility |
| LLM-driven THOUGHT | Route the `_decide_action` reasoning to a Claude call for fully autonomous decision-making |
| Log rotation | Add file rotation to prevent unbounded `error_history.log` growth |

### Lower priority

| Improvement | Description |
|---|---|
| Test suite | Unit tests for `AgentController`, `UCB1Bandit`, `PolicyEngine`, `RewardAggregator`, `ContentModerator`, `RateLimiter`, and `intent_scorer` |
| Proxy support | IP rotation to reduce detection risk on long-running single-IP VPS deployments |
| Conversation memory | `content/conversation_graph.py` exists behind `CONVERSATION_ENABLED=false`; wire it for multi-turn follow-up with warm leads |

---

## 14. System Evolution

### v1 — Static pipeline

The bot searched generic keywords (`AI`, `startup`, `tech`) and applied hardcoded probabilities. Most tweets scored LOW intent. The reward system recorded zero outcomes, the policy penalised, reply probability dropped toward minimum, and the system collapsed to inaction — a stable negative equilibrium.

### v2 — Intent-first search + Adaptive policy

**Input quality became the primary lever.** The 75% INTENT_KEYWORDS bias pre-filters the tweet pool toward HIGH/MEDIUM intent before scoring begins. Minimum floors (`reply >= 0.15`, `follow >= 0.05`) and forced-fallback reply broke the "collapse to inaction" failure mode.

| Dimension | v1 | v2 |
|---|---|---|
| Search phrases | Generic: `AI`, `startup` | Pain-signal: `struggling to get clients` |
| Policy floors | None | `reply >= 0.15`, `follow >= 0.05` |
| Cold-start handling | Penalty fires on phantom zeros | Guard blocks adjustments until 10 real samples |
| Cycle with no actions | Silent | Forced-fallback reply on first tweet |

### v3 — ReAct AgentController (current)

The static `for tweet in tweets: _process_single_tweet()` loop was replaced with an autonomous agent that **reasons** about each decision.

| Dimension | v2 | v3 |
|---|---|---|
| Execution model | Linear pipeline | ReAct loop (THOUGHT → ACTION → OBSERVE) |
| Primary hub | `core/engagement.py` | `core/agent_controller.py` |
| Search phrase selection | Two-tier static logic | Agent consults strategy_lookup_tool first |
| Reply failure handling | Silent drop | Self-correction: diagnose gate, adjust prompt, retry |
| User interaction memory | None | Queries `interactions` table per tweet |
| Rate pressure handling | Reactive (stops when limit hit) | Proactive: routes to scroll_timeline at >85% |
| Console output | `[Decision]` / `[Policy]` lines | `[THOUGHT]` / `[ACTION]` / `[OBSERVE]` per step |
| Action decision | Probabilistic roll inside pipeline | Reasoned decision in `_decide_action()` |
