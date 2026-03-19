# Full System Audit: AI Twitter Content Engine

---

## 1. SYSTEM FLOW ANALYSIS

### How the components interact

```
prompts.py
  ↓ injects pattern + seed + voice rules
engine.py (generate_daily_tweet)
  ↓ calls LLM → validates → retries up to 3x
content_moderator.py (validate + is_vague + signal_density + score_quality)
  ↓ gates output; computes float score
content_cache.py
  ↓ stores tweet by seed hash; serves on exact/semantic match
```

### Bottleneck 1: The seed is hashed as the cache key

In `content_cache.py`, `_hash_tweet(text)` MD5s the seed string.
`engine.py` passes `seed = topic or pillar["description"]` as the cache
key. If `topic` is None, every invocation for the same pillar hits the
same cache slot and **returns the same tweet**, regardless of which
pattern was selected. The retry/pattern rotation logic is silently
bypassed by the cache on the second run of any pillar.

**Fix**: key the cache on `seed + pattern_name + date` to allow daily
rotation within the same pillar.

### Bottleneck 2: `generate_daily_tweet` returns a bare `str`, not a `GenerationResult`

Every other method returns `GenerationResult`. `generate_daily_tweet`
returns `str` or `""`. This means:
- Signal density is never logged for daily tweets that escape via best_tweet
- The caller cannot check `result.retries` or `result.signal_density`
- Metrics tracking is incomplete — you cannot tell post-hoc how many
  daily posts were low-signal best-effort vs genuine passes

### Bottleneck 3: `best_tweet` fallback silently allows weak content

```python
# engine.py lines ~120-130
if signal > best_signal:
    best_signal = signal
    best_tweet = tweet
...
if best_tweet:
    return best_tweet  # posts with no signal gate
```

A tweet with `signal_density=0.25` (one signal, e.g. just an outcome
word) can be posted if all three retries fail. This is the primary
reason mid-quality content escapes. There is no minimum threshold on
`best_signal` before posting. The system will post "replaced a task.
now costs less. the math is brutal" — passes one outcome check, zero
tools, zero numbers, zero implication = 0.25 density, still posts.

**Fix**: require `best_signal >= 0.50` to post, else return empty and
skip the slot. Skipping one day is better than posting noise.

### Bottleneck 4: Cache semantic matching is too broad for daily tweets

`_semantic_similarity` uses Jaccard word overlap at threshold 0.70.
Two seed scenarios like:
- "Automated a $50/hour task with a $0.50 API call"
- "Automated invoice processing for a small firm"

Share the word "automated" and numbers — Jaccard overlap may hit 0.70+,
causing the cache to return the reply from scenario A when scenario B
is requested. **All six seed scenario categories share vocabulary
("automated", "replaced", "workflow", "cost")**, making semantic cache
collisions structurally likely.

**Fix**: disable semantic cache matching for daily tweet generation.
Reserve it only for reply matching where the inputs are user tweets
(much higher lexical diversity).

### Hidden Failure Mode: Pattern selection is random but seed selection is also random

`_get_random_pattern()` and `_get_random_seed()` both run at call time.
There is nothing preventing the same pattern from being selected 5 days
in a row, or the same seed scenario. With 6 patterns and ~32 seed
scenarios, the birthday paradox means a repeat is likely within 8-10
posts. The system has **no state tracking for used patterns or seeds**.

**Fix**: persist last-N used pattern+seed pairs in the DB and exclude
them from selection.

---

## 2. CONTENT QUALITY ANALYSIS

### Why outputs are still weak

**Problem A: Patterns enforce structure but not emotional direction**

`system_consequence` says:
> "Line 3: the uncomfortable consequence nobody wants to say"

This instruction has no teeth. The model interprets "uncomfortable
consequence" as a mild observation: "the value of that role dropped
overnight." That reads like a think-piece, not a punch. Compare:

- Current output tendency: "the value of that role dropped overnight"
- What actually triggers a reply: "the VA doesn't know yet"
- What actually gets bookmarked: "a $47/month stack doing a $4,500/month
  job. nobody's told them."

The difference is **named stakes**: a specific person, not a general
"role". The patterns never require the consequence to be directed at a
specific identifiable person or category of person.

**Problem B: Examples in patterns are too good**

```python
"example": "automated a task we were paying $60k/year for\nnow costs $20/month\nnobody got fired. but the value of that role dropped overnight"
```

The model pattern-matches to this and generates near-copies:
> "replaced a $40k workflow\nnow $15/month\nthe team still exists. but the work doesn't"

This is example contamination. The model is learning the *surface
structure* of the example (X cost → Y cost → oblique observation) and
reproducing it with different numbers. Outputs feel samey after ~20
posts because they all follow the pattern's example, not the pattern's
intent.

**Fix**: remove examples from patterns entirely OR rotate 3+ distinct
examples per pattern with different structures.

**Problem C: "Write as if you personally experienced this scenario"
is too permissive**

```python
# prompts.py line ~230
pillar_instruction = f"""
SPECIFIC SCENARIO TO WRITE ABOUT: {seed}
Write as if you personally experienced this scenario.
"""
```

"Write as if" gives the model permission to narrate, not experience.
Narration produces: "imagine you automated a process that cost $60k..."
or "I've seen this happen where..." — both hedge the specificity.

**Fix**: "Write this as a first-person statement of something that
happened. Not 'imagine'. Not 'I've seen'. It happened. State it."

**Problem D: Last line is underspecified in every pattern**

Every pattern's Line 3 is: "the uncomfortable consequence" or "what
you learned" or "a question that makes people think." None of them
specify the *mechanism* of the ending. The LLM chooses the safest
ending that technically satisfies the constraint: a general observation.

The last line must do one of three specific jobs:
1. Name a person or role who is about to lose something (fear)
2. Create a math problem the reader can't stop thinking about (dread)
3. State a position the reader will disagree with (debate)

"the value of that role dropped overnight" does none of these. It's a
hedge dressed up as a punchline.

---

## 3. SIGNAL VALIDATION CRITIQUE

### Current: 2-of-4 threshold

```python
def has_real_signal(text: str) -> bool:
    ...
    return signals_found >= 2
```

**The threshold is gameable without enforcement of which 2 signals.**

A tweet can pass with:
- outcome verb ("replaced") + implication word ("now") 
- = zero tools, zero numbers, still passes

Example that currently passes `has_real_signal`:
> "replaced the workflow that used to eat our mornings. now it just runs."

- Tool: ❌
- Number: ❌
- Outcome: ✅ ("replaced")
- Implication: ✅ ("now")
- Result: passes. Posts. Gets 3 impressions.

### The real failure: implication words are too broad

```python
IMPLICATION_WORDS = [
    "means", "realized", "now", "overnight", "anymore", "yet",
    "for now", "what happens", "nobody", "somehow", "worse",
    ...
]
```

"now" and "yet" appear in almost every sentence in English. These are
not implication signals — they are filler words that happen to be on
the list. Any tweet will contain "now" or "yet" or "means" regardless
of specificity.

### Proposed replacement: require tool OR number as mandatory

The fix is a stricter compound rule, not just a higher count:

```python
def has_real_signal(text: str) -> bool:
    # Rule: Must have (tool OR number) AND (outcome OR strong implication)
    # "strong implication" requires more than filler words
    
    has_tool = any(tool in text.lower() for tool in KNOWN_TOOLS)
    has_number = any(re.search(p, text.lower()) for p in NUMBER_PATTERNS)
    has_outcome = any(re.search(rf"\b{w}\b", text.lower()) for w in OUTCOME_WORDS)
    has_strong_impl = _has_strong_implication(text)
    
    anchor = has_tool or has_number          # Must have at least one anchor
    consequence = has_outcome or has_strong_impl   # Must have consequence
    
    return anchor and consequence
```

```python
STRONG_IMPLICATION_PHRASES = [
    "doesn't know yet", "still on retainer", "won't last", "for now",
    "this is how it starts", "gets cheaper", "changes what",
    "nobody got", "the job didn't", "they don't know",
    "asked why they're still", "what happens when",
    "that's somehow worse", "nobody talks about the part",
    "the math is", "they only see the",
]

def _has_strong_implication(text: str) -> bool:
    t = text.lower()
    return any(phrase in t for phrase in STRONG_IMPLICATION_PHRASES)
```

This eliminates the "now" and "yet" false positives and requires every
tweet to have at least one concrete anchor (tool or number) plus a
genuine consequence phrase.

---

## 4. MISSING LAYERS

### Missing Layer 1: Ending enforcement

There is no programmatic check that the last line of a tweet does any
work. The system validates length, signals, and vagueness — but not
the ending specifically. The last line is where engagement is won or
lost.

Add to `content_moderator.py`:

```python
WEAK_ENDINGS = [
    "the tools are there", "adapt or get left behind",
    "that's the reality", "this is the world we live in",
    "things are changing", "just something to think about",
    "make of that what you will", "the future is here",
    "it is what it is", "time will tell",
    "dropped overnight",    # too soft — "dropped" without naming who
    "changed everything",   # vague
    "and it works",         # no tension
]

@classmethod
def has_strong_ending(cls, text: str) -> bool:
    """Check that the last line creates tension, not closure."""
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    if not lines:
        return False
    last = lines[-1].lower()
    if any(phrase in last for phrase in cls.WEAK_ENDINGS):
        return False
    # Last line must do one of: name a person/role, contain a number,
    # ask a question, or contain a strong implication phrase
    has_person = any(w in last for w in ["va", "dev", "junior", "senior",
        "client", "freelancer", "team", "manager", "cfo", "employee",
        "recruiter", "bookkeeper", "contractor"])
    has_question = "?" in last
    has_strong_impl = _has_strong_implication(last)
    has_number = any(re.search(p, last) for p in NUMBER_PATTERNS)
    return has_person or has_question or has_strong_impl or has_number
```

### Missing Layer 2: Opinion enforcement

The system has "debate triggers" as suggestions in the prompt:
```
DEBATE TRIGGERS (add when natural — don't force):
- "this is how it starts"
```

"Don't force" is the problem. The model always chooses not to force.
An opinion or position needs to be *required* in at least 2 of every 5
posts (rotation), not suggested optionally.

Add a `require_opinion` flag to the pattern selection logic. When True,
the prompt adds: "You MUST take a side. Not 'this could go either way.'
Pick the uncomfortable interpretation and state it as fact."

### Missing Layer 3: Named-person specificity

The most viral tweets in this niche always name a role: "the VA",
"the junior", "the recruiter", "the CFO". The patterns suggest this
but don't require it. Add to signal validation:

```python
ROLE_SIGNALS = [
    "va", "virtual assistant", "junior", "senior", "mid-level",
    "freelancer", "contractor", "developer", "recruiter", "bookkeeper",
    "cfo", "manager", "team", "client", "employee", "analyst",
]

def has_named_role(text: str) -> bool:
    t = text.lower()
    return any(role in t for role in ROLE_SIGNALS)
```

Require `has_named_role` OR `has_tool` — one of these must be present.
A tweet about "a workflow" with no tool and no named person is abstract.
A tweet about "a VA" or "n8n" is concrete.

### Missing Layer 4: Recency signal injection

`industry_observation` pattern requires "something specific happening
RIGHT NOW (what you noticed this week)" — but there is no mechanism
to inject actual temporal context. The LLM has no idea what week it
is or what is happening in the AI space right now. Every "this week"
tweet is fabricated without current context.

Either: (a) inject a real news/context string via a web search step
before generation, or (b) remove the recency claim from patterns and
use static but timeless observations. Fake recency that gets fact-checked
by Grok is worse than no recency.

---

## 5. PROMPT ENGINEERING REVIEW

### What is working

- Structural patterns are well-defined and cover distinct engagement mechanics
- Seed scenarios are genuinely specific (dollar amounts, tool names, job roles)
- ANTI-PATTERNS section is explicit and catches real failure modes
- The "SO WHAT?" enforcement is the strongest single addition

### What is still too safe

**The VOICE_RULES hedge the output:**
```
- Slightly bold opinions
- Light curiosity
```

"Slightly bold" and "light curiosity" are safe-mode instructions.
For a niche authority account in 2026, the voice needs to be:
- Declarative, not hedged
- Willing to be wrong
- Willing to name who gets hurt

**The hook_format mapping is weak:**
```python
"hot_take": "Start with a bold opinion that makes people stop scrolling."
"contrarian": "Challenge something most people believe. Offer a better way."
```

These are meta-descriptions. The model produces "safe bold opinions"
because "bold opinion" is under-defined. Replace with structural
constraints:

```python
"hot_take": (
    "Your first line must contradict something the majority of developers "
    "believe is true. State it as fact, not opinion. No hedging."
),
"contrarian": (
    "Start with the conventional wisdom (what most people say). "
    "Second line: directly contradict it. Third line: give the one "
    "number or name that proves your version."
),
```

### The example contamination problem (critical)

Every pattern has one example. After ~15 posts, the model has seen
enough of its own output (via the cache pattern) to converge on
example-like structures. Three fixes:

1. Add 2 alternative examples per pattern marked "VARIATION"
2. Add a "STRUCTURE YOU MUST NOT USE:" section with the primary example
   structure listed as forbidden after 10 posts
3. Rotate examples programmatically: `random.choice(pattern['examples'])`

---

## 6. ENGINE LOGIC IMPROVEMENTS

### Problem: Retry escalations are additive, not transformative

```python
RETRY_ESCALATIONS = [
    "\n\nIMPORTANT: Your previous attempt was too vague...",
    "\n\nCRITICAL: Two attempts failed. Use this structure EXACTLY...",
    "\n\nFINAL ATTEMPT — use this format...",
]
```

Adding text to the same prompt doesn't fix the problem that created
vague content in the first place: the base prompt is being followed
but producing a compliant-but-weak result. Retry 2 forces a rigid
format — but Retry 1 just asks harder for what was already asked.

Better retry strategy: change the *generation mode* on retry.

```python
RETRY_STRATEGIES = [
    # Retry 1: Switch to a different, simpler pattern
    {
        "mode": "pattern_switch",
        "instruction": "Use ONLY the displacement_report pattern. "
                       "Line 1: old cost. Line 2: new tool + new cost. "
                       "Line 3: who is affected and how. No variations."
    },
    # Retry 2: Force minimum viable tweet
    {
        "mode": "minimum_viable",
        "instruction": "Write the shortest possible version: "
                       "[tool] replaced [task]. costs [$X] now. "
                       "[one-word consequence for the person who did it before]. "
                       "Nothing else. Under 100 characters."
    },
    # Retry 3: Raw format injection
    {
        "mode": "fill_in_blank",
        "instruction": "Complete this template with real values:\n"
                       "[TOOL] replaced [SPECIFIC_TASK].\n"
                       "old cost: [DOLLAR_OR_HOURS]. new cost: [DOLLAR].\n"
                       "[ROLE] still [CURRENT_STATUS]. [IMPLICATION]."
    },
]
```

### Problem: Validation order is suboptimal

Current order in `generate_daily_tweet`:
1. validate (basic moderation)
2. is_vague_content
3. has_real_signal
4. is_duplicate_reply

The expensive duplicate check runs *after* signal validation. Since
duplicates are rare early in a run, this is fine — but as the cache
grows, it should run *before* signal validation to avoid the cost of
signal checks on content that will be rejected anyway. Minor, but worth
noting.

More critically: **`is_generic` is never called in `generate_daily_tweet`**.
It is called in `generate_reply` but not in the daily tweet path. A
tweet that says "automation is the future" passes `is_vague_content`
(not in VAGUE_PATTERNS) and passes `has_real_signal` if it contains
"automation" (which could be an outcome-adjacent word). The `is_generic`
check would catch "automation is the future" via `vague_authority`
patterns. Add it to the daily tweet validation chain.

```python
# Add to generate_daily_tweet validation block
if self.moderator.is_generic(tweet):
    logger.info(f"Attempt {attempt}: generic content — retrying")
    continue
```

### Problem: No minimum `best_signal` threshold before posting

```python
if best_tweet:
    logger.warning(f"Posting best-effort tweet...")
    return best_tweet
```

A tweet with `signal_density=0.0` can be returned here. Add:

```python
MIN_FALLBACK_SIGNAL = 0.50

if best_tweet and best_signal >= MIN_FALLBACK_SIGNAL:
    return best_tweet

logger.error("No tweet met minimum signal threshold. Skipping post.")
return ""  # Caller should handle empty string as skip-post
```

---

## 7. CONTENT MODERATOR REVIEW

### `signal_density` is correct in structure but broken by implication word list

As detailed in Section 3: "now", "yet", "means", "somehow" appear in
nearly all English sentences. The implication bucket adds +0.25 to
almost every tweet. Effective signal density for most outputs is
inflated by ~0.25 because of this. The fix is `STRONG_IMPLICATION_PHRASES`
as listed in Section 3.

### `score_quality` still rewards length over substance

```python
if 20 <= length <= 150:
    score += 0.15
```

A 100-character motivational tweet scores +0.15. A 200-character
displacement report with three specific signals scores +0.10. The
length bonus actively penalizes the more valuable, longer-form content
this niche requires. Flatten this:

```python
# Replace length scoring with:
if 30 <= length <= 280:
    score += 0.05  # Minimal flat bonus; signal density does the real work
```

### `is_generic` is not called in the daily tweet path

Covered in Section 6. Add it.

### Missing: Ending strength check

Covered in Section 4. Add `has_strong_ending` as a gate in both
`score_quality` (bonus) and the validation chain (soft gate on retry
but not hard block).

---

## 8. BEFORE vs AFTER EXAMPLES

### Example 1: `system_consequence` pattern

**Before (current system output):**
```
automated a process we were paying $40k/year for
now $15/month
the team still exists. but the work doesn't.
```
Problems: "the work doesn't" is vague. Who is the team? What happens
to them? The ending has no named stakes. Zero debate trigger.

**After:**
```
automated a task that cost $40k/year
make.com + gpt-4o. $18/month now
the person who did it manually is still employed
nobody's had that conversation yet
```
Why better: named person (person who did it), explicit tension
("nobody's had that conversation yet"), specific tool, specific number,
two strong implication phrases.

---

### Example 2: `displacement_report` pattern

**Before:**
```
client's weekly research was a 4hr VA job
n8n + perplexity agent. $0.60/run
the VA is still on retainer. for now.
```
This is the pattern example itself. The model reproduces near-identical
versions. Good structure, but contaminated by example reuse.

**After (different structure, same pattern):**
```
3-person research team. 6 hrs/week per person
perplexity + claude pipeline does it in 40 mins now
they still exist. their budget review is next quarter.
```
Why better: names a *group* (3-person team), concrete hours (6 hrs ×
3), named tool stack, and the ending creates a specific dread (budget
review) not a vague hedge ("for now").

---

### Example 3: `cost_reality` pattern

**Before:**
```
$50/hour task replaced by a $0.50 API call
the math is brutal
what happens when every company figures this out?
```
This is almost the pattern example verbatim. Model pattern-matched.

**After:**
```
copywriting that billed at $75/hr
claude does 80% of it. costs $0.04/1000 words
clients don't know yet
the ones who find out will ask why they're still paying
```
Why better: named a specific job type (copywriting), specific billing
rate, specific tool, specific cost unit (per 1000 words), two-beat
ending that creates a specific fear (client discovering the math).

---

### Example 4: `agent_reality` — failure pattern

**Before:**
```
built an AI workflow for client onboarding
replaced 4 hours of manual work
works 90% of the time. breaks in ways that make no sense.
```
Again the pattern example. Model defaults to it.

**After:**
```
agent passed every test I gave it
first real user broke it in 11 minutes
she typed her company name with a dot in it
that's the gap between demo and production
```
Why better: the failure is *specific* (dot in company name), names
a person ("she"), and the last line names the real insight (demo vs
production gap) instead of "breaks in ways that make no sense."

---

## 9. FINAL SYSTEM REDESIGN

### What to remove

- Single examples per pattern. Replace with 3 rotated examples.
- "Write as if you personally experienced this" → remove "as if"
- Implication word list from signal detection (too broad)
- Semantic cache matching for daily tweets
- Length-weighted score bonus

### What to change

- `has_real_signal`: require anchor (tool OR number) + consequence
  (outcome OR strong implication phrase). Current 2-of-4 is gameable.
- `generate_daily_tweet`: return `GenerationResult`, not `str`
- `best_tweet` fallback: require `best_signal >= 0.50`
- Cache key for daily tweets: `seed + pattern_name + date`
- Retry logic: change generation *mode* per retry, not just add text
- Add `is_generic` to daily tweet validation chain
- Add `has_strong_ending` to validation and score_quality

### What to add

1. **Ending enforcer** (`has_strong_ending` in `content_moderator.py`)
2. **Named-role signal** (`has_named_role` in signal validation)
3. **Pattern + seed deduplication** (track last-N used in DB)
4. **Opinion rotation flag** (require_opinion every ~3 posts)
5. **Minimum fallback signal threshold** (0.50 before posting)
6. **`is_generic` in daily tweet path**

### Priority order for implementation

| Priority | Change | Expected Impact |
|---|---|---|
| 1 | Fix implication word list → strong implications only | Eliminates false signal passes |
| 2 | Add `best_signal >= 0.50` fallback gate | Stops weak content from posting |
| 3 | Add `has_strong_ending` check | Increases reply rate on endings |
| 4 | Add `is_generic` to daily tweet path | Catches motivational filler |
| 5 | Remove/rotate pattern examples | Eliminates example contamination |
| 6 | Change retry strategy to mode-switching | Better recovery from weak first attempts |
| 7 | Add named-role signal requirement | Forces specificity |
| 8 | Pattern + seed deduplication tracking | Prevents repetition over time |

The single highest-ROI change is Priority 1: the signal validation is
currently passing content it shouldn't pass because "now" and "yet"
are on the implication list. Fix that, and the retry system starts
working as intended.
