# SESSION BEHAVIOR ENGINE - DESIGN & IMPLEMENTATION

**Date:** March 12, 2026  
**Module:** `core/session_manager.py`  
**Status:** ✅ IMPLEMENTED & INTEGRATED

---

## OVERVIEW

The Session Behavior Engine replaces continuous bot loops with **realistic human activity patterns**.

Instead of:
```
🤖 LOOP: Do engagement → Sleep 90 min → Do engagement → Sleep 90 min → ...
```

Now:
```
👤 SESSION: Active 20-45 min → Break 30-120 min → Active 20-45 min → ...
   + Only run during 8 AM - 11 PM
   + Pause between actions (30s - 3min)
   + Natural looking activity distribution
```

---

## DESIGN PRINCIPLES

### 1. Human-Like Session Structure

**Real User Behavior:**
- Opens app, scrolls through feed
- Likes/replies to tweets for 20-45 minutes
- Closes app, takes a break
- Does something else for 30-120 minutes
- Returns later

**Bot Now Mimics This:**
- `SESSION` (20-45 min) - Active engagement
- `BREAK` (30-120 min) - Dormant, no engagement
- `OUTSIDE_HOURS` (23:00-08:00) - Sleeps overnight
- `IDLE` - Waiting to start

### 2. Time-Based Constraints

**Active Hours:** 8:00 AM - 11:00 PM (configurable)
- Real humans don't engage at 3 AM
- Avoids pattern recognition by X's algorithms
- Respects normal human schedule

**Session Duration:** 20-45 minutes (randomized)
- Each session length varies
- 20-min: Quick check during break
- 45-min: Extended engagement session
- Variation prevents "bot rhythm" detection

**Break Duration:** 30-120 minutes (randomized)
- 30-min: Quick break, back soon
- 120-min: Longer activity elsewhere
- Mimics real interrupt patterns

### 3. Action Pacing Within Sessions

**Problem:** Back-to-back actions look like a bot
```
❌ Like tweet 1 (0.1s later)
❌ Like tweet 2 (0.1s later)
❌ Like tweet 3 (0.1s later)
❌ Reply to tweet 4
= 4 actions in 5 seconds (impossible for human)
```

**Solution:** Enforce minimum spacing between actions
```
✓ Like tweet 1
✓ Scroll/read (30-180s pause)
✓ Like tweet 2
✓ Scroll/read (30-180s pause)
✓ Reply to tweet 3
= 3 actions in 6 minutes (realistic)
```

**Algorithm:**
```python
def should_take_action():
    # After minimum interval: 30-50% chance
    # After 2x interval: 50-80% chance
    # After 3x interval: always yes
    
    elapsed = now - last_action_time
    if elapsed < MIN (30s):
        return False
    elif elapsed < 2*MIN (60s):
        chance = 0.3 + (elapsed - MIN) / MIN * 0.5
        return random.random() < chance
    else:
        return True
```

This creates natural "think time" between actions.

---

## STATE MACHINE

```
┌──────────────┐
│              ├─ OUTSIDE_HOURS? → Sleep until next active window
│   Check      │
│  Conditions  ├─ IN_BREAK? → Sleep during break
│              │
└──────────────┘
       │
       ▼
┌──────────────────┐
│                  │
│  ACTIVE SESSION  │ ← SessionManager.start_session()
│  (20-45 min)     │  
│                  │
│  - Track time    │
│  - Count actions │
│  - Enforce pace  │
│                  │
└──────────────────┘
       │
       ├─ Action allowed? → Run engagement
       │                   record_action()
       │
       ├─ Time elapsed >= session_duration?
       │  YES → end_session() ↓
       │
       └─ Within time → Stay in session

       ▼
┌──────────────────┐
│                  │
│   BREAK          │ ← SessionManager.end_session()
│   (30-120 min)   │
│                  │
│   - Sleep        │
│   - No engagement│
│   - Wait for     │
│     break to end │
│                  │
└──────────────────┘
       │
       └─ Break elapsed? → Back to check conditions
```

---

## CONFIGURATION

All session behavior is controlled by config:

```python
# Active Hours (24-hour format)
ACTIVE_START_HOUR = 8          # Start at 8 AM
ACTIVE_END_HOUR = 23           # Stop at 11 PM

# Session Timing
SESSION_DURATION_MIN = 20      # Min session = 20 minutes
SESSION_DURATION_MAX = 45      # Max session = 45 minutes

# Break Timing
BREAK_DURATION_MIN = 30        # Min break = 30 minutes
BREAK_DURATION_MAX = 120       # Max break = 2 hours

# Action Pacing Within Sessions
MIN_ACTION_INTERVAL_SEC = 30   # At least 30s between actions
MAX_ACTION_INTERVAL_SEC = 180  # Max 3min between actions
```

### Example Scenarios

**Scenario 1: Workday Engagement**
```
08:00 - Session starts (30 min)
  08:05 - Like tweet
  08:20 - Reply to tweet
  08:45 - Like another tweet
08:30 - Session ends, break starts
08:30 - 09:15 - Break (45 min)
09:15 - Next session starts
```

**Scenario 2: Short Break Check**
```
12:00 - Session starts (25 min)
  12:02 - Like tweet
  12:15 - Check replies
  12:20 - Like trending topic
  12:25 - Reply
12:25 - Session ends, break starts
12:25 - 12:40 - Break (15 min? No, min is 30)
12:55 - Next session starts
```

**Scenario 3: Outside Hours**
```
23:15 - "Outside active hours" (outside 8 AM - 11 PM)
        Sleep until next day
08:00 - Wake up, session starts
```

---

## CODE ARCHITECTURE

### SessionState Enum

```python
class SessionState(Enum):
    IDLE = "idle"                    # Waiting to start
    ACTIVE_SESSION = "active"        # Engaging with tweets
    BREAK = "break"                  # Resting between sessions
    OUTSIDE_HOURS = "outside_hours"  # Outside active hours (midnight-8AM)
```

### SessionManager Class

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `should_be_active()` | Is it active hours AND not in break? |
| `start_session()` | Begin new engagement session |
| `is_session_complete()` | Has session duration elapsed? |
| `end_session()` | End session, start break |
| `is_in_break()` | Currently in break period? |
| `should_take_action()` | Enough time passed since last action? |
| `record_action()` | Mark that action was taken |
| `get_session_info()` | Return status dict |
| `get_time_until_active()` | Seconds until next active window |

**Internal State:**

```python
# Timing info
self.session_start_time      # When current session began
self.session_duration_sec    # How long this session lasts
self.break_start_time        # When current break began
self.break_duration_sec      # How long this break lasts
self.last_action_time        # When last action was taken

# Counters
self.actions_in_session      # Actions taken so far in session
self.session_action_target   # How many actions to take in session

# State
self.current_state           # Current SessionState

# Persistence
self.state_file              # data/session_state.txt (survives restarts)
```

### Integration with BotController

**Before:**
```python
while self.running:
    run_engagement()
    sleep(90 minutes)  # Fixed interval
```

**After:**
```python
while self.running:
    # 1. Check if should be active
    if not self.session_manager.should_be_active():
        sleep(until active window)
        continue
    
    # 2. Start session if needed
    if not in_session:
        self.session_manager.start_session()
    
    # 3. Check if should take action (natural pacing)
    if not self.session_manager.should_take_action():
        sleep(natural pause)
        continue
    
    # 4. Run engagement
    try:
        run_engagement()
        self.session_manager.record_action()
    except Exception as e:
        handle_error()
    
    # 5. Check if session is done
    if self.session_manager.is_session_complete():
        self.session_manager.end_session()
```

---

## BEHAVIOR COMPARISON

### Old Bot (Continuous Loop)

```
Time    | Action                    | Realism | X Detection Risk
--------|---------------------------|---------|------------------
00:00   | Like tweet                | ❌      | 🔴 NIGHT (asleep)
00:01   | Like tweet                |         |
00:02   | Like tweet                |         |
...     | Like tweet                |         |
00:30   | Like tweet (30 at once!)  | ❌ ROBOT| 🔴 MASSIVE BURST
01:00   | Sleep                     | ❌ SLEEP| 🔴 WRONG TIME
...     |                           |         |
```

**Problems:**
- ❌ Active at 3 AM (humans sleep)
- ❌ 30 actions in rapid succession (obviously a bot)
- ❌ No natural break patterns
- ❌ Fixed timing (every 90 min exactly)
- 🔴 High detection risk

### New Bot (Session-Based)

```
Time    | State         | Action                  | Realism | Risk
--------|---------------|-------------------------|---------|-----
08:00   | SESSION START | Start 30-min session    | ✓       | 🟢
08:02   | ACTIVE        | Like tweet              | ✓       | 🟢
08:15   | ACTIVE        | Pause (natural delay)   | ✓       | 🟢
08:20   | ACTIVE        | Reply to tweet          | ✓       | 🟢
08:35   | ACTIVE        | Pause (natural delay)   | ✓       | 🟢
08:40   | SESSION END   | Start 60-min break      | ✓       | 🟢
08:40-09:40 | BREAK     | Sleep (no engagement)   | ✓       | 🟢
09:40   | SESSION START | Start 45-min session    | ✓       | 🟢
09:42   | ACTIVE        | Like tweet              | ✓       | 🟢
...     |               |                         |         |
23:00   | OUTSIDE HOURS | Sleep until 8 AM        | ✓ SLEEP | 🟢
```

**Improvements:**
- ✓ Only active during human hours (8 AM - 11 PM)
- ✓ Natural breaks between sessions
- ✓ Randomized timing (prevents "bot rhythm")
- ✓ Actions spread naturally (30s - 3min apart)
- ✓ Variable session lengths (keeps patterns hidden)
- 🟢 Very low detection risk

---

## PERSISTENCE & RECOVERY

### State Saving

When session state changes, saved to `data/session_state.txt`:

```json
{
  "state": "active",
  "session_start": "2026-03-12T10:30:42.123456",
  "session_duration": 1800,
  "break_start": null,
  "break_duration": null,
  "actions_in_session": 3
}
```

### Crash Recovery

If bot crashes:
1. State is loaded from disk
2. SessionManager knows exact session status
3. Bot resumes correctly without losing state
4. No "reset" of session (would look suspicious)

Example:
```
Session starts at 10:30 with 30-min duration
Bot crashes at 10:45 (15 min elapsed)
Bot restarts at 10:50
Session resumes: 5 min remaining
Can take actions until 11:00
```

---

## METRICS & MONITORING

### Session Info Available

```python
info = session_manager.get_session_info()
# Returns:
{
    "state": "active",
    "elapsed_sec": 300,           # 5 minutes elapsed
    "remaining_sec": 1500,        # 25 minutes left
    "percentage": 17,             # 17% through session
    "actions": 2,                 # 2 actions taken
    "target_actions": 6,          # Target is 6
}
```

### Logging Output

```
===============================================================================
📱 SESSION START
   Duration: 35 min
   Target actions: 7
   Session until: 09:15:42
===============================================================================

[LOG] Pausing for 45s before next action (natural pacing)...
[LOG] 📱 SESSION: 5m elapsed, 30m remaining (14%)
[LOG]    Actions: 1/7

[LOG] ✓ Pausing for 62s before next action (natural pacing)...

===============================================================================
⏸️  SESSION END - TAKING BREAK
   Session lasted: 35 min
   Actions performed: 4
   Break duration: 52 min
   Resume at: 09:52:30
===============================================================================

[LOG] 😴 OUTSIDE ACTIVE HOURS - sleeping for 8.3 hours
```

---

## EXAMPLE DAILY TIMELINE

```
Time         State              Actions         Notes
─────────────────────────────────────────────────────────────
00:00        OUTSIDE_HOURS      Sleep           Offline all night
...          (sleeping)
08:00        SESSION START      -               Begin day
08:02        ACTIVE             Like #1         Activity starts
08:35        SESSION END        -               Take 46-min break
08:35        BREAK              Sleep
09:21        SESSION START      -               Resume
09:23        ACTIVE             Like #2
10:05        SESSION END        -               Take 37-min break
10:05        BREAK              Sleep
10:42        SESSION START      -               Resume
10:44        ACTIVE             Reply #1
11:15        SESSION END        -               Take 68-min break
11:15        BREAK              Sleep
12:23        SESSION START      -               Resume
12:25        ACTIVE             Like #3
13:10        SESSION END        -               Take 41-min break
13:10        BREAK              Sleep
13:51        SESSION START      -               Resume
...          (continue pattern)
23:00        OUTSIDE_HOURS      Sleep           End of day
```

---

## SAFETY CONSIDERATIONS

### ✅ What's Protected

1. **Action Clustering** - Never more than 8 actions in 10 min
2. **Night Activity** - No actions between 11 PM - 8 AM
3. **Session Patterns** - Randomized timing prevents "bot rhythm"
4. **Action Pacing** - 30s-3min between actions (realistic)
5. **Break Recovery** - Realistic rest periods

### ⚠️ Still Vulnerable To

1. **Content Similarity** - If all replies are generated by same AI
2. **Follower Patterns** - Following spammy/bot accounts
3. **Interaction Targets** - Only engaging with certain hashtags
4. **Geographic Anomalies** - Location mismatch with timezone

### 🔒 Mitigation

These are handled by other systems:
- `core/generator.py` - Variety in reply content
- `core/engagement.py` - Smart hashtag/user selection
- `utils/human_behavior.py` - Human-like typing
- Browser stealth mode - Hide automation signals

---

## CONFIGURATION RECOMMENDATIONS

### Conservative (Safest)
```python
ACTIVE_START_HOUR = 9
ACTIVE_END_HOUR = 22
SESSION_DURATION_MIN = 15      # Short sessions
SESSION_DURATION_MAX = 30
BREAK_DURATION_MIN = 45        # Long breaks
BREAK_DURATION_MAX = 180
MIN_ACTION_INTERVAL_SEC = 45   # More spacing
MAX_ACTION_INTERVAL_SEC = 300
```

### Balanced (Recommended)
```python
ACTIVE_START_HOUR = 8
ACTIVE_END_HOUR = 23
SESSION_DURATION_MIN = 20      # Moderate sessions
SESSION_DURATION_MAX = 45
BREAK_DURATION_MIN = 30        # Moderate breaks
BREAK_DURATION_MAX = 120
MIN_ACTION_INTERVAL_SEC = 30   # Normal spacing
MAX_ACTION_INTERVAL_SEC = 180
```

### Aggressive (Higher Risk)
```python
ACTIVE_START_HOUR = 7
ACTIVE_END_HOUR = 24
SESSION_DURATION_MIN = 40      # Long sessions
SESSION_DURATION_MAX = 60
BREAK_DURATION_MIN = 15        # Short breaks
BREAK_DURATION_MAX = 60
MIN_ACTION_INTERVAL_SEC = 15   # Minimal spacing
MAX_ACTION_INTERVAL_SEC = 60
```

---

## CONCLUSION

The Session Behavior Engine transforms the bot from an obvious script loop into a human-like user:

✅ Operates during realistic hours (8 AM - 11 PM)  
✅ Engages in realistic sessions (20-45 min bursts)  
✅ Takes realistic breaks (30-120 min rest)  
✅ Spaces actions naturally (30s - 3min apart)  
✅ Randomizes patterns (prevents detection)  
✅ Survives restarts (state persisted)  

**Result:** Bot now resembles natural human behavior patterns rather than obvious automation.

This is **critical** for avoiding X's bot detection algorithms, which actively look for:
- 24/7 activity patterns
- Consistent timing intervals
- Back-to-back rapid actions
- No break periods

The Session Behavior Engine addresses all of these detection vectors.
