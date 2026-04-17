# CLAUDE.md — System Prompt Extension for X Automation Bot (Keepdaping)

This file is automatically loaded by Claude Code at the start of every session. It gives you the architectural context, constraints, and behavioral rules you need to maintain and extend this codebase correctly without breaking the agentic loop.

---

## Project Identity

- **Brand:** Keepdaping (one word, no space, no hyphen — always written as a single word)
- **Goal:** Autonomous high-intent lead generation on X (Twitter) for Keepdaping brand
- **Architecture:** ReAct (Reason + Act) — autonomous agent loop, not a static pipeline
- **Language:** Python 3.10+, Playwright (sync API), SQLite, Anthropic Claude API

---

## Primary Execution Hub

```
core/agent_controller.py  ← THIS IS THE BRAIN
```

All engagement reasoning, tool selection, and action decisions flow through `AgentController`. When you make changes to engagement behavior, **start here**. `core/engagement.py` is now a thin wrapper that handles periodic side-effects (outcome checks, timeline browse, unfollow, daily reflect) then calls `AgentController.run_cycle()`.

**Never reintroduce** the old static `for tweet in tweets: _process_single_tweet()` loop into `engagement.py`. That pattern has been replaced by the ReAct cycle.

---

## Architecture in One View

```
BotController (run_bot.py)
    └── run_engagement(page)          ← public API, unchanged
              └── AgentController.run_cycle()
                    │
                    ├── strategy_lookup_tool()    THOUGHT: rewards + rate snapshot
                    ├── _choose_search_phrase()   THOUGHT: 75% intent / 25% UCB1 bandit
                    ├── search_tool(phrase)       ACTION: 3-tier fallback search
                    └── per-tweet loop:
                          ├── analyze_intent_tool()    ACTION: intent score + LLM override
                          ├── _check_memory(handle)    THOUGHT: prior interaction?
                          ├── PolicyEngine             STRATEGY: evidence-adjusted probs
                          ├── _decide_action()         THOUGHT: final action choice
                          └── engagement_action_tool() ACTION: execute
                                └── _do_reply()        self-correction loop (3 attempts)
```

---

## The ReAct Loop — Rules for Maintaining It

### Log every step with the correct prefix

All reasoning, actions, and observations must use these three methods on `AgentController`:

```python
self._thought("text")   # cyan  — reasoning, decisions, memory observations
self._act("tool_name", "args")  # yellow — tool invocations
self._observe("text")   # green — results of tool calls
self._warn("text")      # red   — failures, skips, rate limit blocks
```

**Do not use `log.info()` directly inside AgentController methods.** Always route through these four helpers so the ReAct structure stays coherent in the log stream.

### Tools must be callable methods

The four defined tools (`strategy_lookup_tool`, `search_tool`, `analyze_intent_tool`, `engagement_action_tool`) each:

1. Call `self._act(...)` at their start to log the invocation
2. Call `self._observe(...)` to log their result before returning
3. Return structured data (dict or tuple) — never side-effect-only

If you add a new capability, implement it as a new `_tool_name_tool()` method following this pattern.

### Rate limit check is inviolable

Inside `engagement_action_tool()`, `rate_limiter.can_perform_action(action_type)` is called before **every** non-scroll action. This check **must not be removed, bypassed, or moved** downstream of the action attempt. The agent is permitted to reason about rate pressure but is never permitted to act in violation of the limiter.

---

## Inviolable Safety Floors

These two values must be enforced as hard minimums **after** the AGGRESSION_LEVEL multiplier is applied. They exist so the learning loop always has signal to work with. **Never remove or soften them.**

```python
MIN_REPLY_PROB  = 0.15   # reply_prob >= 0.15, always
MIN_FOLLOW_PROB = 0.05   # follow_prob >= 0.05, always
```

They are enforced by `PolicyEngine.get_action_probabilities()` (in `core/policy.py`) and separately in `AgentController._decide_action()` for the LOW-intent path.

The **forced-fallback reply** at the end of `run_cycle()` is also inviolable: if `self._actions == 0` after the full tweet loop, the agent must attempt a reply on `first_tweet`. Log this with:

```python
self._thought(
    "INVIOLABLE FLOOR: Zero actions taken this cycle. "
    "Forcing 1 reply on first tweet to maintain learning signal "
    "(MIN_REPLY_PROB cannot be reasoned away)."
)
```

---

## Self-Correction Loop — How to Extend It

The self-correction loop lives in `AgentController._do_reply()`. It loops up to `MAX_REGENERATIONS = 3` times. On each failed moderation attempt, `_analyze_reply()` returns which gates failed:

```python
{
    "passed": bool,
    "gate_failed": str | None,       # hard validation failure reason
    "signal_score": int,             # 0-4 from ContentModerator.signal_density()
    "has_role": bool,                # ContentModerator.has_named_role()
    "quality": float,                # ContentModerator.score_quality()
    "is_generic": bool,              # ContentModerator.is_generic()
    "soft_failures": list,           # ["signal_density", "named_role", "generic"]
}
```

Correction hints are injected into `_generate_candidate()` based on `last_failure`. The three current correction hints:

| Gate failure | Correction prompt sent to LLM |
|---|---|
| `signal_density` | "Include a specific tool (e.g. n8n, Zapier, Python), a number, and a concrete outcome or consequence." |
| `named_role` | "Reference a specific role: founder, VA, junior dev, CFO, recruiter, or client." |
| `generic` | "Avoid generic filler. Make a specific, direct observation about the real-world implication." |

To add a new gate check, add it to `_analyze_reply()` and add a corresponding correction hint in `_generate_candidate()`.

---

## Memory System — How to Use It

`_check_memory(user_handle)` queries the `interactions` table via direct SQLite (not through the `database.py` abstraction, to avoid circular imports at this module level). It returns:

```python
{
    "style":          str,   # last reply style used
    "days_ago":       int,   # how many days since last interaction
    "outcome_score":  float, # outcome_score from that interaction
    "got_reply_back": bool,
    "got_follow":     bool,
}
```

The memory result feeds directly into `_decide_action()`. Current behavioral rules:

- `days_ago == 0` → switch from `reply` to `follow` (avoid same-day double contact)
- `got_reply_back == True` → boost `reply_probability` by 1.5× (warm lead)

To add new memory-driven behaviors, modify `_decide_action()` after the memory block. Always log the reasoning with `self._thought(...)`.

---

## Strategy Snapshot — Read Before Every Cycle

`strategy_lookup_tool()` must be the **first tool called** in `run_cycle()`, immediately after the detection-cooldown check. It provides:

```python
{
    "style_rewards":     dict,   # smoothed_score per reply style (from RewardAggregator)
    "keyword_rewards":   dict,   # conversion_yield per search phrase
    "rate_remaining":    dict,   # remaining daily actions per type
    "rate_pressure":     float,  # 0.0–1.0; >0.85 triggers low-cost routing
    "recommended_style": str,
    "recommended_phrase": str | None,
}
```

The `rate_pressure` value must be threaded into `_decide_action()` on every tweet. If `rate_pressure > 0.85`, `_decide_action()` must return `"scroll_timeline"` regardless of intent.

On cold start (empty DB), `RewardAggregator` returns empty dicts. `strategy_lookup_tool()` handles this gracefully with fallback values. **Do not add special-case logic** for cold start in the agent — the aggregator already handles it.

---

## Search Phrase Selection — The 75/25 Split

`_choose_search_phrase()` maintains a deliberate split:

- **75%** → random pick from `Config.INTENT_KEYWORDS` (pain-signal phrases, pre-filtered)
- **25%** → UCB1 bandit over `Config.SEARCH_PHRASES` (learns conversion yield)

**Do not change this ratio** without a documented reason. The 75% intent-keyword bias is the primary mechanism that pre-filters the tweet pool toward HIGH/MEDIUM intent. The 25% bandit path exists to prevent the intent keywords from completely starving the broader phrase pool.

The `strategy` snapshot from `strategy_lookup_tool()` is passed to `_choose_search_phrase()` so the agent can log what the bandit currently recommends before making its selection. This is informational — the bandit still makes its own UCB1 selection.

---

## Extending the Agent — Checklist

When adding a new capability to `AgentController`:

- [ ] Does it involve an external operation (search, DB read, Playwright action)? → Make it a `_tool_name_tool()` method with `_act()` at start and `_observe()` at end
- [ ] Does it involve reasoning or a decision? → Add it inside `_decide_action()` or as a `_thought()` block in `run_cycle()`
- [ ] Does it touch the `interactions` table? → Use direct `sqlite3.connect(DB_PATH)` to avoid circular imports
- [ ] Does it perform an engagement action? → Route through `engagement_action_tool()` so the rate limit check fires automatically
- [ ] Does it change reply generation? → Add to `_generate_candidate()` and update `_analyze_reply()` if a new gate is introduced
- [ ] Does it change action probabilities? → Respect the `MIN_REPLY_PROB = 0.15` and `MIN_FOLLOW_PROB = 0.05` floors

---

## File Responsibilities — What Lives Where

| File | Responsibility | What NOT to put here |
|---|---|---|
| `core/agent_controller.py` | ReAct loop, tool methods, memory, self-correction, action decisions | Playwright browser lifecycle, daily tweet logic |
| `core/engagement.py` | Side-effects (outcome checks, browse, unfollow, reflect); delegates to AgentController | Tweet-level reasoning, action decisions |
| `run_bot.py` | Session management, daily tweet, main loop | Engagement routing, reply generation |
| `core/reply_handler.py` | Reply generation and feedback logging (still used by pipeline.py) | Action decision logic — that belongs in AgentController |
| `core/policy.py` | Evidence-adjusted probabilities; enforces MIN floors | Action selection (that's AgentController._decide_action) |
| `core/reward_aggregator.py` | Read-only DB aggregation — never writes | Any writes to the DB |
| `content/content_moderator.py` | Validation rules and quality scoring | LLM calls, DB access |

---

## Console Log — What Good Output Looks Like

A healthy cycle looks like this in the logs:

```
======================================================================
AGENT CYCLE STARTING  [ReAct mode — AgentController]
======================================================================
[THOUGHT ] Pre-flight: checking detection cooldown.
[ACTION  ] strategy_lookup_tool()
[OBSERVE ] Rate remaining={reply:12, follow:9, like:18, quote:2} | pressure=18% | best_style=grok | best_phrase='struggling to get clients'
[THOUGHT ] Consulting bandit rewards and intent keyword pool for search phrase.
[THOUGHT ] Search phrase: 'struggling to get clients' (75% intent-targeted path)
[ACTION  ] search_tool(query='struggling to get clients')
[OBSERVE ] Found 8 tweets for 'struggling to get clients'
[THOUGHT ] Found 8 tweets for 'struggling to get clients'. Will analyze intent and choose an engagement action for each.

[THOUGHT ] — Tweet 1/8 —
[ACTION  ] analyze_intent_tool(text='Every tool I try just breaks after a week...')
[OBSERVE ] Intent=HIGH (score=3)
[THOUGHT ] Memory: no prior interaction with @founder_jane.
[THOUGHT ] Intent=HIGH | policy: reply=0.72, follow=0.18 | remaining: replies=12, follows=9
[THOUGHT ] Decision: execute 'reply' on this tweet.
[ACTION  ] engagement_action_tool(action=reply)
[OBSERVE ] Moderation PASSED (style=grok, quality=0.76, signal=3/4, has_role=True)
[OBSERVE ] Reply posted [style=grok] | reply_id=1923847561234

[AGENT] CYCLE COMPLETE — 3 actions | 0 errors | 2 high-intent tweets
```

A self-correction event looks like:

```
[ACTION  ] engagement_action_tool(action=reply)
[OBSERVE ] Moderation FAILED — gates: signal_density | signal_density=1/4 | has_named_role=False | quality=0.38 | is_generic=False
[THOUGHT ] Self-correction attempt 2/3. Last failure: 'signal_density'. Trying style='curiosity'.
[OBSERVE ] Moderation PASSED (style=curiosity, quality=0.61, signal=2/4, has_role=True)
[OBSERVE ] Reply posted [style=curiosity] | reply_id=1923847561299
```

A rate-pressure deflection looks like:

```
[OBSERVE ] Rate remaining={reply:2, follow:1, like:3, quote:0} | pressure=87% | ...
[THOUGHT ] Rate pressure 87% is HIGH. Choosing scroll_timeline to conserve limits.
[ACTION  ] engagement_action_tool(action=scroll_timeline)
[OBSERVE ] scroll_timeline (low-cost action)
```

---

## What Not to Do

- **Do not** bypass `engagement_action_tool()` and call `reply_tweet()`, `like_tweet()`, or `follow()` directly from `run_cycle()`. All actions must pass through the rate-limit gate.
- **Do not** add hardcoded action probabilities to `run_cycle()`. Probabilities belong in `PolicyEngine` (evidence-based) or `_decide_action()` (floor enforcement).
- **Do not** lower `MIN_REPLY_PROB` below `0.15` or `MIN_FOLLOW_PROB` below `0.05`. These floors are the only thing that guarantees the learning loop has signal.
- **Do not** use `log.info()` inside `AgentController` methods for reasoning steps. Use `self._thought()`, `self._act()`, `self._observe()`.
- **Do not** add a new engagement path that bypasses `AgentController`. The `run_engagement()` function in `engagement.py` must remain the single entry point, and it must delegate to `AgentController`.
- **Do not** write to the database from `RewardAggregator`. It is read-only by design.
- **Do not** run Playwright from the background scheduler thread. Playwright's sync API is not thread-safe. Only the main thread (via `AgentController`) touches the browser.
- **Do not** reintroduce the old static pipeline (`_process_single_tweet` loop) into the engagement path. It still exists for use by `AgentController` internally but must not replace the ReAct cycle.

---

## Key Constants

```python
MAX_REGENERATIONS = 3       # max self-correction attempts per reply (agent_controller.py)
MIN_REPLY_PROB    = 0.15    # inviolable floor (policy.py + agent_controller.py)
MIN_FOLLOW_PROB   = 0.05    # inviolable floor (policy.py)
RATE_PRESSURE_THRESHOLD = 0.85  # above this → scroll_timeline routing
INTENT_KEYWORD_WEIGHT   = 0.75  # 75% of search cycles use INTENT_KEYWORDS
BANDIT_WEIGHT           = 0.25  # 25% use UCB1 bandit over SEARCH_PHRASES
```

---

## Database Schema Quick Reference

| Table | Key columns | Written by |
|---|---|---|
| `interactions` | tweet_id, user_handle, reply_style, intent, sent_at, outcome_score, got_reply_back, got_follow | FeedbackTracker (via reply_handler) |
| `follows` | user_id, username, followed_at, followed_back, unfollowed_at | follow_handler |
| `posts` | text_hash, tweet_id, topic, pillar, format | BotController._post_daily_tweet |
| `search_log` | phrase, tweets_found, actions_taken, high_intent_found, timestamp | AgentController.run_cycle |
| `bandit_arms` | namespace, arm, trials, total_reward | UCB1Bandit (learning.py) |
| `action_history` | action_type, timestamp, success, target_id | RateLimiter |

The `interactions` table is the single source of truth that feeds the entire learning loop. The agent's `_check_memory()` reads it directly via `sqlite3` (not through `database.py`) to avoid circular imports.

---

## Testing a Change to the Agent

Since no automated tests exist, validate changes manually:

1. **Confirm the ReAct log structure is intact** — every cycle must produce `[THOUGHT]`, `[ACTION]`, `[OBSERVE]` lines in the expected order
2. **Confirm rate limit check still fires** — add a test with a saturated limiter and confirm the agent logs `[WARN]` and does not attempt the blocked action
3. **Confirm inviolable floors hold** — set `AGGRESSION_LEVEL=0.0` and confirm `reply_prob` is still `>= 0.15` in the `[THOUGHT]` log
4. **Confirm self-correction fires** — temporarily return a low-quality string from `_generate_candidate()` and confirm the agent retries with a logged correction
5. **Confirm forced-fallback fires** — set `REPLY_PROBABILITY=0.0` and confirm the end-of-cycle `[THOUGHT]` about the inviolable floor appears and a reply is attempted
