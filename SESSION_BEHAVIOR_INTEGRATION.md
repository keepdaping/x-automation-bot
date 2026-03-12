# SESSION BEHAVIOR ENGINE - INTEGRATION GUIDE

**Status:** ✅ Fully Integrated  
**Files Modified:**
- `core/session_manager.py` (NEW)
- `run_bot.py` (UPDATED)
- `config.py` (UPDATED)

---

## WHAT'S NEW

### 1. New Module: `core/session_manager.py`

**Purpose:** Manage realistic session-based engagement patterns

**Key Classes:**
- `SessionState` Enum - State machine (IDLE, ACTIVE_SESSION, BREAK, OUTSIDE_HOURS)
- `SessionManager` - Main session controller

**Key Methods:**
```python
session_manager = SessionManager(config)

# Check if should be active
session_manager.should_be_active()

# Start a session
session_manager.start_session()

# Check if can take action (respects pacing)
session_manager.should_take_action()

# Record that action was taken
session_manager.record_action()

# Check if session is complete
session_manager.is_session_complete()

# End session and start break
session_manager.end_session()

# Get status info
session_manager.get_session_info()
session_manager.get_time_until_active()
```

### 2. Updated: `config.py`

**New Configuration Options:**

```python
# SESSION BEHAVIOR - Human-like activity patterns
ACTIVE_START_HOUR = 8           # Start at 8 AM
ACTIVE_END_HOUR = 23            # Stop at 11 PM
SESSION_DURATION_MIN = 20       # Min 20 min sessions
SESSION_DURATION_MAX = 45       # Max 45 min sessions
BREAK_DURATION_MIN = 30         # Min 30 min breaks
BREAK_DURATION_MAX = 120        # Max 120 min breaks
MIN_ACTION_INTERVAL_SEC = 30    # At least 30s between actions
MAX_ACTION_INTERVAL_SEC = 180   # Max 3 min between actions
```

Can be overridden in `.env`:
```bash
ACTIVE_START_HOUR=8
ACTIVE_END_HOUR=23
SESSION_DURATION_MIN=20
SESSION_DURATION_MAX=45
BREAK_DURATION_MIN=30
BREAK_DURATION_MAX=120
MIN_ACTION_INTERVAL_SEC=30
MAX_ACTION_INTERVAL_SEC=180
```

### 3. Updated: `run_bot.py`

**Changes:**

```python
# NEW: Import session manager
from core.session_manager import init_session_manager

class BotController:
    def __init__(self):
        # ... existing code ...
        # NEW: Initialize session manager
        self.session_manager = init_session_manager(Config)
    
    def start(self):
        # ... authentication ...
        
        # NEW: Session-driven engagement loop
        while self.running:
            # Check if should be active
            if not self.session_manager.should_be_active():
                # Sleep until next active window
                continue
            
            # Start session if needed
            if not in_session:
                self.session_manager.start_session()
            
            # Check natural pacing
            if not self.session_manager.should_take_action():
                # Take natural pause
                continue
            
            # Run engagement
            try:
                run_engagement()
                self.session_manager.record_action()  # NEW
            
            # Check if session complete
            if self.session_manager.is_session_complete():
                self.session_manager.end_session()  # NEW
```

---

## HOW TO USE

### Default Behavior

Just run the bot - session manager handles everything:

```bash
python run_bot.py
```

The bot will:
1. ✓ Sleep until 8 AM
2. ✓ Start session at 8 AM
3. ✓ Engage for 20-45 minutes
4. ✓ Take break for 30-120 minutes
5. ✓ Repeat
6. ✓ Sleep after 11 PM

### Custom Session Timing

Edit `.env` to customize:

```bash
# More aggressive (shorter sessions)
SESSION_DURATION_MIN=15
SESSION_DURATION_MAX=30
BREAK_DURATION_MIN=15
BREAK_DURATION_MAX=60

# More conservative (longer breaks)
SESSION_DURATION_MIN=20
SESSION_DURATION_MAX=45
BREAK_DURATION_MIN=60
BREAK_DURATION_MAX=180

# Different active hours (tweeter might use different times)
ACTIVE_START_HOUR=10
ACTIVE_END_HOUR=22
```

### Monitor Session Status

```python
# In your monitoring script
from core.session_manager import get_session_manager

session_mgr = get_session_manager()
info = session_mgr.get_session_info()

print(f"State: {info['state']}")
print(f"Progress: {info['percentage']}%")
print(f"Actions: {info['actions']}/{info['target_actions']}")
```

---

## EXAMPLE LOG OUTPUT

### Session Start
```
======================================================================
📱 SESSION START
   Duration: 32 min
   Target actions: 6
   Session until: 08:47:15
======================================================================
```

### Active Session (Log line when status printed)
```
📱 SESSION: 15m elapsed, 17m remaining (47%)
   Actions: 3/6
```

### Natural Pause Between Actions
```
✓ Pausing for 45s before next action (natural pacing)...
```

### Session End & Break Start
```
======================================================================
⏸️  SESSION END - TAKING BREAK
   Session lasted: 32 min
   Actions performed: 4
   Break duration: 47 min
   Resume at: 08:34:20
======================================================================
```

### Outside Active Hours
```
😴 OUTSIDE ACTIVE HOURS - sleeping for 8.3 hours
```

---

## COMPARISON: BEFORE vs AFTER

### BEFORE (Continuous Loop)

```
Cycle 1: Like tweet → Sleep 90 min
Cycle 2: Reply to tweet → Sleep 90 min
Cycle 3: Like tweet → Sleep 90 min
```

**Problems:**
- ❌ Fixed 90-minute intervals (obvious pattern)
- ❌ Active at all hours (even 3 AM)
- ❌ No break periods
- ❌ Looks like automation

### AFTER (Session-Based)

```
08:00 - SESSION START (25 min)
08:02 - Like tweet
08:35 - Like tweet
08:40 - SESSION END
08:40 - BREAK (45 min)
09:25 - SESSION START (30 min)
09:27 - Reply to tweet
etc.
```

**Improvements:**
- ✓ Variable session timing (20-45 min)
- ✓ Only active 8 AM - 11 PM
- ✓ Realistic breaks (30-120 min)
- ✓ Looks like human behavior

---

## STATE FLOW

**Simplified View:**

```
CHECK CONDITIONS
    ↓
Outside hours? → SLEEP (8h)
    ↓
In break? → SLEEP (30-120 min)
    ↓
Start session? → START SESSION
    ↓
In session? → CHECK ACTION PACING
    ↓
Can take action? → RUN ENGAGEMENT
    ↓
Session complete? → END SESSION + START BREAK
    ↓
[Back to CHECK CONDITIONS]
```

---

## PERSISTENCE

Session state is saved to `data/session_state.txt`:

```json
{
  "state": "active",
  "session_start": "2026-03-12T10:30:42",
  "session_duration": 1800,
  "break_start": null,
  "break_duration": null,
  "actions_in_session": 3
}
```

**This means:**
- ✓ Bot survives crashes without losing session state
- ✓ Session continues correctly after restart
- ✓ No suspicious "reset" patterns

Example:
```
Session starts 10:30 with 30-min duration
Bot crashes at 10:45
Bot restarts at 10:50
Session resumes: 5 min remaining (instead of starting new)
```

---

## TROUBLESHOOTING

### Bot Won't Do Any Actions

**Possible causes:**

1. **Outside active hours?**
   ```bash
   # Check current time vs ACTIVE_START_HOUR/ACTIVE_END_HOUR
   # Bot only active 8 AM - 11 PM by default
   ```

2. **In break period?**
   ```
   Log should show: "⏸️  BREAK:"
   Wait for break to finish
   ```

3. **Waiting for action pacing?**
   ```
   Log should show: "✓ Pausing for Xs before next action"
   This is normal - bot respects natural spacing
   ```

4. **Session target reached?**
   ```
   If actions == target_actions, session ends and break starts
   Wait for break to finish
   ```

### Actions Too Frequent

**Solution:** Increase action spacing

```bash
# In .env
MIN_ACTION_INTERVAL_SEC=60      # At least 60s
MAX_ACTION_INTERVAL_SEC=300     # Max 5 min
```

### Actions Too Infrequent

**Solution:** Decrease action spacing

```bash
# In .env
MIN_ACTION_INTERVAL_SEC=15      # At least 15s
MAX_ACTION_INTERVAL_SEC=90      # Max 90s
```

### Bot Waking Up Too Early/Late

**Solution:** Adjust active hours

```bash
# In .env
ACTIVE_START_HOUR=9             # Start at 9 AM instead of 8
ACTIVE_END_HOUR=22              # Stop at 10 PM instead of 11
```

---

## NEXT STEPS

1. ✅ Run the bot with defaults
2. ✅ Monitor logs for first 24 hours
3. ✅ Verify session behavior (starts, pauses, breaks)
4. ✅ Check rate limiter & error handler still working
5. ✅ Adjust config if needed for your account
6. ✅ Test account health (no warnings from X)

---

## SUMMARY

The Session Behavior Engine makes bots look human by:

✅ Operating in time-bounded sessions (not 24/7)  
✅ Taking realistic breaks between sessions  
✅ Spacing actions naturally (not back-to-back)  
✅ Randomizing all timing (prevents patterns)  
✅ Persisting state (survives crashes)  
✅ Respecting human schedules (8 AM - 11 PM)  

**Result:** Enhanced stealth and reduced detection risk.
