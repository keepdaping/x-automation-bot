#!/usr/bin/env python3
"""
X AUTOMATION BOT - QUICK START GUIDE
====================================

This file documents the complete working implementation.
Follow these steps to get the bot running immediately.

Author: Senior Automation Engineer
Date: March 12, 2026
Status: ✅ PRODUCTION READY
"""

# ============================================================================
# STEP 1: VERIFY YOUR SETUP (RIGHT NOW - 5 MINUTES)
# ============================================================================

"""
Before running the bot, verify:

1. Python 3.10+ installed:
   python --version

2. Project structure correct:
   ✓ config.py exists
   ✓ requirements.txt exists
   ✓ run_bot.py exists
   ✓ browser/ folder with browser_manager.py
   ✓ actions/ folder with like.py, reply.py, follow.py
   ✓ core/ folder with engagement.py
   ✓ utils/ folder with human_behavior.py, selectors.py
   ✓ search/ folder with search_tweets.py

3. Virtual environment:
   python -m venv venv
   source venv/bin/activate  # Linux/Mac: bash
   venv\Scripts\activate      # Windows: PowerShell
"""

# ============================================================================
# STEP 2: INSTALL DEPENDENCIES (5 MINUTES)
# ============================================================================

"""
Installation commands:

pip install -r requirements.txt
playwright install chromium

Wait for installation to complete...
You should see: "Downloading Chromium..." then "Installation complete"
"""

# ============================================================================
# STEP 3: CREATE AUTHENTICATED SESSION (10 MINUTES)
# ============================================================================

"""
THIS IS THE CRITICAL STEP - DO THIS EXACTLY:

$ python create_session.py

You will see:
  1. "Opening X login page..."
  2. A real Chrome browser window opens
  3. X.com login page loads
  
THEN:
  1. Enter your X username/email
  2. Enter your password
  3. If prompted for 2FA - use your authenticator app
  4. Wait for page to fully load (you see the home feed)
  5. Return to terminal and press ENTER

RESULT:
  ✓ Session saved successfully to session.json
  ✓ File created with your authentication cookies

NEVER DELETE session.json - this is your auth!
NEVER COMMIT session.json - add to .gitignore
BACKUP session.json - if lost, run create_session.py again
"""

# ============================================================================
# STEP 4: VERIFY SESSION (2 MINUTES)
# ============================================================================

"""
Verify the session was created correctly:

$ python verify_session.py

Expected output:
  ✓ session.json found
  ✓ Number of cookies: 14+
  ✓ Found important auth cookies: auth_token, ct0
  ✓ Session file looks valid!

If you see "⚠ Warning: Did not find expected auth cookies"
  → session.json exists but might be invalid
  → Run: python create_session.py again
  → Make sure you logged in successfully before pressing ENTER
"""

# ============================================================================
# STEP 5: RUN THE BOT (ONGOING)
# ============================================================================

"""
Now run the bot:

$ python run_bot.py

You should see:
  ======================================================================
  X AUTOMATION BOT STARTING
  ======================================================================
  ✓ Browser launched successfully
  ✓ Loaded 14 cookies from session.json
  ✓ Bot authenticated and ready
  
  Starting engagement loop (Press Ctrl+C to stop)
  
  --- CYCLE 1 ---
  [1/4] Opening X login page...
  [2/4] Page loaded. A browser window will open...
  ... searching for "AI" ...
  ... liking tweets ...
  --- CYCLE 2 ---
  ...

This means the bot is WORKING!

It will:
  - Search for tweets with AI-related keywords
  - Like engaging tweets
  - Reply with AI-generated responses (if Anthropic key set)
  - Follow interesting users
  - Sleep 90-180 seconds
  - Repeat

Press Ctrl+C to stop gracefully.
"""

# ============================================================================
# STEP 6: FIRST-TIME SETUP CHECKLIST
# ============================================================================

"""
✓ Python environment created:  python -m venv venv
✓ Dependencies installed:      pip install -r requirements.txt
✓ Playwright installed:        playwright install chromium
✓ Session created:             python create_session.py
✓ Session verified:            python verify_session.py
✓ Bot tested locally:          python run_bot.py
✓ Bot runs successfully:       CYCLE messages appearing

If all checked ✓ you're ready for deployment!
"""

# ============================================================================
# STEP 7: CONFIGURE THE BOT (OPTIONAL)
# ============================================================================

"""
Edit config.py to customize behavior:

MAX_LIKES_PER_RUN = 8         # Tweets to like per cycle
MAX_REPLIES_PER_RUN = 4       # Replies to send per cycle
MAX_QUOTES_PER_RUN = 2        # Quotes to send per cycle

AI_MODEL_DRAFT = "claude-3-haiku-20240307"  # Cheaper, fast
AI_MODEL_CRITIQUE = "claude-3-sonnet-20240229"  # Better, slower

MIN_DELAY = 1.5               # Minimum pause between actions
MAX_DELAY = 4                 # Maximum pause between actions

Restart bot after changes for new settings to apply.
"""

# ============================================================================
# STEP 8: DEPLOY TO GITHUB ACTIONS (FREE, 24/7)
# ============================================================================

"""
GitHub Actions allows the bot to run 24/7 for FREE!

Setup:

1. Go to your GitHub repo → Settings → Secrets and Variables → Actions

2. Add these secrets:
   Name: ANTHROPIC_API_KEY
   Value: sk-ant-... (from https://console.anthropic.com/account/keys)

3. Commit to GitHub:
   git add .
   git commit -m "X bot - production ready"
   git push

4. Go to Actions tab:
   → Should see "X Bot Automation" workflow
   → Click "Run workflow"
   → Watch it execute

5. Workflow runs automatically:
   → Every 6 hours (configurable)
   → See logs in Actions tab
   → No manual setup needed

NOTE: session.json is already included and will work in Actions!
"""

# ============================================================================
# STEP 9: COMMON ISSUES & FIXES
# ============================================================================

"""
Issue: "Not authenticated to X"
  Fix: Run python create_session.py again
       Make sure you see the home feed before pressing ENTER

Issue: "Could not resolve authentication method"
  Fix: Get API key from https://console.anthropic.com/account/keys
       Add to .env: ANTHROPIC_API_KEY=sk-ant-...

Issue: "Element not clickable" or "Timeout"
  Fix: X.com's HTML changed
       Update selectors in utils/selectors.py
       Refresh by running create_session.py again

Issue: "Browser not launching"
  Fix: Run: playwright install chromium
       Then: python run_bot.py

Issue: "Permission denied" on .env/.ssh
  Fix: chmod 600 .env
       chmod 700 .ssh
"""

# ============================================================================
# STEP 10: MONITORING & MAINTENANCE
# ============================================================================

"""
Monitor locally:
  tail -f logs/bot.log        # View live logs

Monitor on GitHub Actions:
  Repo → Actions → Select run → View logs

Check bot health:
  Look for: "Cycle complete. Sleeping Xs"
  
If you see errors repeatedly:
  1. Check logs first
  2. Regenerate session.json if auth fails
  3. Restart bot: Ctrl+C then python run_bot.py

Monthly maintenance:
  1. Regenerate session.json (keep it fresh)
  2. Check X.com hasn't changed DOM (update selectors.py)
  3. Adjust rate limits if needed
"""

# ============================================================================
# COMPLETE SETUP TIME: ~30 MINUTES
# ============================================================================

"""
Timeline:
  5 min  - Verify setup
  5 min  - Install dependencies
  10 min - Create session (most of this is waiting for X.com)
  2 min  - Verify session
  5 min  - Test bot locally
  3 min  - Deploy to GitHub Actions

Total: ~30 minutes from zero to production
"""

# ============================================================================
# SUCCESS CRITERIA
# ============================================================================

"""
You've successfully setup when you see:

Local bot running:
  $ python run_bot.py
  ✓ Bot authenticated and ready
  --- CYCLE 1 ---
  [CYCLE MESSAGES...]
  ✓ Cycle complete. Sleeping 120s
  --- CYCLE 2 ---
  [CYCLE MESSAGES...]

GitHub Actions running:
  Go to Actions tab
  See "X Bot Automation" workflow
  Click run - see "PASSED" status

Then... DONE! The bot is running 24/7.
"""

# ============================================================================
# NEXT STEPS AFTER SETUP
# ============================================================================

"""
Week 1:
  - Monitor bot for issues
  - Check GitHub Actions logs daily
  - Verify tweets are being liked/replied to

Week 2:
  - Adjust parameters in config.py
  - Add custom keywords
  - Fine-tune engagement strategy

Month 1+:
  - Monitor performance metrics
  - Regenerate session.json
  - Plan any improvements or scaling
"""

# ============================================================================
# FILES YOU NEED TO UNDERSTAND
# ============================================================================

"""
Key files (in order of importance):

1. COMPLETE_README.md
   → Full documentation, all features, deployment options

2. run_bot.py
   → Main bot entry point, engagement loop

3. browser/browser_manager.py
   → Browser lifecycle, session loading, anti-detection

4. core/engagement.py
   → What bot does - search, like, reply, follow

5. config.py
   → Configuration, timeouts, rate limits

6. utils/selectors.py
   → DOM selectors (update if X changes HTML)

7. create_session.py
   → How to generate session.json

All other files are supporting utilities and actions.
"""

# ============================================================================
# YOU'RE READY!
# ============================================================================

"""
Everything is set up and ready to go.

Now simply:
  1. python create_session.py
  2. python run_bot.py
  3. git push to GitHub Actions
  4. Wait for bot to like all the tweets 😎

Questions? Check COMPLETE_README.md or REDESIGN_GUIDE.md

Good luck! 🚀
"""
