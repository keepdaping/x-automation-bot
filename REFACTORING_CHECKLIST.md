# 🚀 Quick Refactoring Action Plan

**Print this and check off as you go!**

---

## CRITICAL ISSUES AT A GLANCE

| Issue | Impact | Effort | Status |
|-------|--------|--------|--------|
| 20 markdown files (chaos) | 🔴 High | 1h | Not started |
| Duplicate `score_tweet()` | 🟡 Medium | 30m | Not started |
| Dead code in `scheduler.py` | 🟡 Medium | 15m | Not started |
| Redundant `behavior_patterns.py` | 🟡 Medium | 20m | Not started |
| Unused generators/posting | 🟠 Low | Remove later | Not started |
| Files scattered in root | 🟡 Medium | 1.5h | Not started |
| Missing type hints | 🟠 Low | 2h | Not started |
| Missing docstrings | 🟠 Low | 1.5h | Not started |

**Total Effort**: 6-8 hours  
**Start**: After shadow test  
**Block**: No (non-blocking refactor)  

---

## PHASE 1: DOCUMENTATION CLEANUP ✅

**Time**: 30 minutes  
**Files Affected**: 20 markdown files

### What to Keep
- [ ] README.md - Primary documentation
- [ ] SESSION_BEHAVIOR_*.md (2 files) - Essential for ops
- [ ] Keep: QUICK_START.md or IMPLEMENTATION_CHECKLIST.md (consolidate these 2 to 1)

### What to Delete (8 files)
- [ ] TIER1_AUDIT_REPORT.md
- [ ] TIER1_AUDIT_FINDINGS_SUMMARY.md
- [ ] TIER1_COMPLETE_FINAL_REPORT.md
- [ ] TIER1_CRITICAL_FIXES_SUMMARY.md
- [ ] TIER1_IMPLEMENTATION_SUMMARY.md
- [ ] TIER1_QUICK_REFERENCE.md
- [ ] TECHNICAL_REVIEW.md
- [ ] REDESIGN_GUIDE.md

### What to Archive (5 files)
Create `docs/archived/` folder and move:
- [ ] 24H_SIMULATION_SUMMARY.md
- [ ] SIMULATION_ANALYSIS.md
- [ ] IMPROVEMENT_ANALYSIS.md
- [ ] TIMELINE_EXAMPLES.md
- [ ] LANGUAGE_DETECTION.md

### What to Consolidate (2 files → 1)
- [ ] Merge COMPLETE_README.md into README.md (delete original)
- [ ] Consolidate QUICK_START.md + IMPLEMENTATION_CHECKLIST.md → 1 file

### What to Create (3 new files)
- [ ] docs/DEPLOYMENT.md (from SESSION_BEHAVIOR_*.md)
- [ ] docs/DEVELOPMENT.md (contributor guide)
- [ ] docs/ARCHITECTURE.md (this ARCHITECTURE_AUDIT.md)

---

## PHASE 2: DELETE DEAD CODE ✅

**Time**: 15 minutes  
**Easy wins - Just delete!**

### Files to Delete
```bash
# Delete completely
rm core/scheduler.py
rm utils/posting_schedule.py

# Move to tests/
mv test_playwright.py tests/test_installation.py
mv verify_api_models.py tests/verify_models.py
mv verify_session.py tests/verify_session.py
```

### Remove from requirements.txt
- [ ] Search for `apscheduler` - Delete the line if found
- [ ] Verify no other imports of APScheduler
  ```bash
  grep -r "apscheduler" core/ utils/ actions/
  # Should return: no results
  ```

### Verify No Broken Imports
- [ ] Check `core/engagement.py` doesn't import scheduler
- [ ] Search for any `from core.scheduler import`
  ```bash
  grep -r "from core.scheduler" .
  grep -r "import scheduler" .
  ```
- [ ] Should return: no results

---

## PHASE 3: MERGE REDUNDANT CODE ✅

**Time**: 1 hour 30 minutes

### 3.1: Merge `behavior_patterns.py` into `human_behavior.py` (20 min)

**In `utils/human_behavior.py`**, add at the end:
```python
# Legacy aliases (from removed behavior_patterns.py)
def human_activity_pause(min_sec=5, max_sec=15):
    """Simulate user leaving app briefly."""
    pause_time = random.uniform(min_sec, max_sec)
    time.sleep(pause_time)
```

**Then delete**: `utils/behavior_patterns.py`

**Update imports** in:
- [ ] `search/search_tweets.py` - Change `from utils.behavior_patterns` → `from utils.human_behavior`
- [ ] Any other file using it - Find with:
  ```bash
  grep -r "behavior_patterns" core/ actions/ search/
  ```

### 3.2: Fix Duplicate `score_tweet()` (30 min)

**Current state**:
- `utils/engagement_score.py` - Has `score_tweet()` (simple)
- `utils/tweet_metrics.py` - Has `score_tweet()` (with better formatting)

**Action**:
1. Delete `utils/engagement_score.py` entirely
   ```bash
   rm utils/engagement_score.py
   ```

2. In `core/engagement.py`, find this import:
   ```python
   from utils.engagement_score import score_tweet
   ```
   Change to:
   ```python
   from utils.tweet_metrics import score_tweet
   ```

3. Find all other imports:
   ```bash
   grep -r "engagement_score" core/ utils/ actions/
   ```
   Update each one to import from `tweet_metrics` instead

4. Test import works:
   ```python
   python -c "from utils.tweet_metrics import score_tweet; print('✓')"
   ```

### 3.3: Consolidate Tweet-Related Utilities (40 min)

**Goal**: Merge 4 files into 1: `content/tweet_analysis.py`

**Step 1**: Create new file `utils/tweet_analysis.py` with:
```python
"""
Tweet analysis and scoring utilities.
Combines functionality from multiple modules.
"""

# From tweet_metrics.py
from utils.tweet_metrics import get_tweet_metrics, score_tweet

# From tweet_selector.py
def select_best_tweets(tweet_data, limit=5):
    # ... [copy code] ...

# From tweet_text.py
def get_tweet_text(tweet):
    # ... [copy code] ...
```

**Step 2**: Delete old files:
```bash
rm utils/tweet_metrics.py
rm utils/tweet_selector.py
rm utils/tweet_text.py
```

**Step 3**: Update imports in `core/engagement.py`:
```python
# Old:
from utils.tweet_metrics import get_tweet_metrics, score_tweet
from utils.tweet_selector import select_best_tweets
from utils.tweet_text import get_tweet_text

# New:
from utils.tweet_analysis import (
    get_tweet_metrics, 
    score_tweet, 
    select_best_tweets, 
    get_tweet_text
)
```

**Step 4**: Find and update all imports:
```bash
grep -r "tweet_metrics" .
grep -r "tweet_selector" .
grep -r "tweet_text" .
```

**Step 5**: Test imports:
```python
python -c "from utils.tweet_analysis import *; print('✓')"
```

---

## PHASE 4: REORGANIZE DIRECTORY STRUCTURE ✅

**Time**: 1.5 hours

### New Structure to Create

```bash
# Create new directories
mkdir -p config
mkdir -p setup
mkdir -p tools
mkdir -p tests/unit
mkdir -p tests/integration
mkdir -p docs/archived
```

### Move Files to New Locations

```bash
# Configuration
mv config.py config/

# Setup scripts
mv create_session.py setup/
mv import_cookies.py setup/

# Tools
mv simulate_24hours.py tools/

# Tests
mv tests/test_installation.py tests/unit/
mv tests/verify_*.py tests/

# Documentation
mkdir -p docs/archived
# (move all TIER1_*.md files here)
# (keep SESSION_BEHAVIOR_*.md in root for now)
```

### Update Imports (CRITICAL!)

**In `run_bot.py`** (line with config import):
```python
# Old:
from config import Config

# New:
from config.config import Config
```

**In all other Python files**:
- Find: `from config import Config`
- Replace: `from config.config import Config`

**Search & replace command**:
```bash
grep -r "^from config import" . --include="*.py" | grep -v "config.py:"
# This shows all files that import config
# Update each one
```

### Test That Everything Still Imports

```bash
python -c "from config.config import Config; print('✓ Config imports')"
python -c "from setup.create_session import *; print('✓ Setup imports')"
python -c "from tools.simulate_24hours import *; print('✓ Tools import')"
```

---

## PHASE 5: ADD TYPE HINTS ✅

**Time**: 2 hours (focus on critical files first)

### Priority 1: Core Engagement (30 min)

**File**: `core/engagement.py`

```python
# Add at top:
from typing import Optional, List, Tuple
from playwright.sync_api import Page

# Update function signatures:
def run_engagement(page: Page, config: Optional[Config] = None) -> bool:
    """
    Run one cycle of engagement with all safety checks.
    
    Args:
        page: Playwright page object
        config: Optional config object
        
    Returns:
        True if engagement successful, False otherwise
    """
    # ... implementation ...
```

### Priority 2: Actions (30 min)

**Files**: `actions/like.py`, `actions/reply.py`, `actions/follow.py`

```python
# In each action file:
from typing import Optional
from playwright.sync_api import Page

def like_tweet(tweet: Page.Locator, page: Optional[Page] = None) -> bool:
    """Like a single tweet."""
    # ...

def reply_tweet(
    page: Page, 
    tweet: Page.Locator, 
    text: str, 
    timeout: int = 10000
) -> bool:
    """Reply to a tweet."""
    # ...
```

### Priority 3: Utilities (1 hour)

**File**: `utils/human_behavior.py`
```python
from typing import Optional, Dict, Tuple
from playwright.sync_api import Page

def random_delay(min_seconds: float = 1.5, max_seconds: float = 4) -> None:
    """Add random delay between actions."""
    # ...

def natural_scroll(
    page: Page, 
    pixels: int = 1500, 
    delay_between_scrolls: int = 300
) -> None:
    """Scroll page in natural, human-like manner."""
    # ...
```

---

## PHASE 6: ADD DOCSTRINGS ✅

**Time**: 1.5 hours (focus on public APIs)

### Template for All Functions

```python
def function_name(param1: Type1, param2: Type2) -> ReturnType:
    """
    One-line summary of what function does.
    
    Longer description if needed. Explain the purpose and behavior.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: When/why this exception is raised
        
    Example:
        >>> result = function_name(value1, value2)
        >>> print(result)
        expected_output
        
    Note:
        Any special notes or caveats
    """
    # implementation
```

### Critical Files to Document

1. **`core/engagement.py`** - main engagement loop
2. **`actions/*.py`** - each action method
3. **`utils/human_behavior.py`** - behavior utilities
4. **`core/rate_limiter.py`** - rate limiting logic
5. **`core/session_manager.py`** - session behavior

---

## PHASE 7: STANDARDIZE CODE STYLE ✅

**Time**: 1 hour

### Naming Conventions Rules

**Functions**: verb_object pattern
```python
# Good ✓
def like_tweet():
def follow_user():
def get_tweet_metrics():

# Bad ✗
def tweet_like():
def userFollow():
def metrics_get():

# Exception: Getters and setters
def is_visible():    # Boolean check  
def has_element():   # Boolean check
def set_value():     # Setter
def get_value():     # Getter (OK)
```

### Logging Standards

**Rules**:
- NO emojis in logs (machine-readable)
- Consistent log levels
- Include context/values

```python
# Good ✓
log.info("Tweet liked (score: 8.5)")
log.debug("Retry attempt 2 of 5")
log.warning("Rate limit at 90%: %d/%d actions", used, limit)
log.error("Failed to load page: %s", error_msg)

# Bad ✗
log.info("✓ Tweet liked")          # Emoji
log.info("Retrying...")             # No context
log.warning("rate limit")           # Lowercase, vague
log.error("FAILED!!")               # All caps, vague
```

### Apply to Files

- [ ] Find all `log.info()` with emojis and remove them
- [ ] Find all `log.warning()` and add context if missing
- [ ] Find all `log.error()` and ensure message + exception included

**Command**:
```bash
# Find lines with emojis in logs
grep -r "log\." core/ utils/ actions/ | grep -E "[😴🔴❤️🚫⚠️]"
```

---

## PHASE 8: FINAL VALIDATION ✅

**Time**: 1 hour

### Run These Checks

```bash
# 1. Check all imports work
python -c "
import run_bot
import core.engagement
import actions.like
import actions.reply
import actions.follow
import utils.human_behavior
import utils.tweet_analysis
import search.search_tweets
print('✓ All imports successful')
"

# 2. Check for import errors
python -m py_compile run_bot.py
python -m py_compile core/engagement.py
python -m py_compile actions/*.py
python -m py_compile utils/*.py
python -m py_compile search/*.py

# 3. Lint check (if using pylint)
# pylint core/ utils/ actions/ search/ --errors-only

# 4. Type check (if using mypy - optional)
# mypy core/ utils/ actions/ search/

# 5. Test simulate_24hours still works
python tools/simulate_24hours.py
# Should complete with no errors

# 6. Test run_bot starts (don't need headless, just check imports)
python -c "from run_bot import BotController; print('✓ Bot controller loads')"
```

### Create Test Checklist

```python
# tests/test_after_refactor.py

def test_imports():
    """Verify all modules import correctly."""
    from core import engagement
    from actions import like, reply, follow
    from utils import human_behavior, tweet_analysis
    from search import search_engine
    assert True

def test_config_loads():
    """Verify config can be loaded."""
    from config.config import Config
    assert Config.MAX_LIKES_PER_DAY > 0

def test_bot_initializes():
    """Verify bot can initialize without error."""
    # This would need a mock page, but simple check:
    from run_bot import BotController
    assert BotController is not None
```

Run with: `python -m pytest tests/test_after_refactor.py`

---

## CLEANUP CHECKLIST (Master Checklist)

### FILES TO DELETE
- [ ] core/scheduler.py
- [ ] utils/posting_schedule.py
- [ ] utils/engagement_score.py
- [ ] utils/behavior_patterns.py
- [ ] utils/tweet_metrics.py
- [ ] utils/tweet_selector.py
- [ ] utils/tweet_text.py
- [ ] TIER1_AUDIT_REPORT.md and 6 others (archive first)
- [ ] TECHNICAL_REVIEW.md
- [ ] REDESIGN_GUIDE.md
- [ ] TYPING_SPEED_ANALYSIS.md
- [ ] LANGUAGE_DETECTION.md (archive)

### FILES TO MERGE
- [ ] behavior_patterns.py → human_behavior.py
- [ ] engagement_score.py → tweet_metrics.py
- [ ] tweet_selector.py → tweet_metrics.py
- [ ] tweet_text.py → tweet_metrics.py
- [ ] Consolidate tweet files → tweet_analysis.py

### FILES TO MOVE
- [ ] config.py → config/config.py
- [ ] create_session.py → setup/
- [ ] import_cookies.py → setup/
- [ ] simulate_24hours.py → tools/
- [ ] test_*.py, verify_*.py → tests/

### FILES TO UPDATE (IMPORTS)
- [ ] run_bot.py
- [ ] core/engagement.py
- [ ] search/search_tweets.py
- [ ] actions/*.py
- [ ] All other Python files

### IMPROVEMENTS ADD TO FILES
- [ ] Type hints (critical 5 files, then rest)
- [ ] Docstrings (all public functions)
- [ ] Standardize naming
- [ ] Remove emojis from logs
- [ ] Add error handling

### DOCUMENTATION
- [ ] Create docs/ folder structure
- [ ] Create docs/DEPLOYMENT.md
- [ ] Create docs/DEVELOPMENT.md
- [ ] Archive old reports
- [ ] Update README.md

---

## FINAL VALIDATION

After all changes, run:

```bash
# Full import test
python -c "
from run_bot import BotController
from core.engagement import run_engagement
from actions.like import like_tweet
from actions.reply import reply_tweet
from actions.follow import follow_user
from search.search_engine import search_tweets
from config.config import Config
from utils.human_behavior import random_delay
from utils.tweet_analysis import get_tweet_metrics, score_tweet
print('✓✓✓ ALL IMPORTS SUCCESSFUL ✓✓✓')
"

# Simulate 24 hours (should work instantly since already compiled)
python tools/simulate_24hours.py | head -20

# Count Python files
find . -name "*.py" -type f | wc -l
# Should be ~22 (down from 32)

# Count Markdown files
find . -name "*.md" -type f | wc -l
# Should be ~3 (down from 20)

echo "✓✓✓ REFACTORING COMPLETE ✓✓✓"
```

---

## TIME ESTIMATE BREAKDOWN

| Phase | Task | Time |
|-------|------|------|
| 1 | Documentation cleanup | 30m |
| 2 | Delete dead code | 15m |
| 3.1 | Merge behavior_patterns | 20m |
| 3.2 | Fix duplicate score_tweet | 30m |
| 3.3 | Consolidate tweet files | 40m |
| 4 | Reorganize directories | 1.5h |
| 5 | Add type hints | 2h |
| 6 | Add docstrings | 1.5h |
| 7 | Standardize style | 1h |
| 8 | Testing & validation | 1h |
| **TOTAL** | **Full Refactoring** | **~8 hours** |

---

## DO THIS AFTER SHADOW TEST ✅

**When**: After 24-hour shadow test passes  
**Why**: Refactoring doesn't block testing  
**Risk**: Low (code cleanup, not feature changes)  

**Order**:
1. Shadow test on test account (24h)
2. If successful: Shallow the codebase (8h)
3. Then: Production test (48-72h)

---

**Print this checklist and check off each item as you complete it!**

Last updated: March 12, 2026
