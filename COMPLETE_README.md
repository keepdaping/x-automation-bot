# X (Twitter) Automation Bot - Complete Implementation Guide

> **Browser-based automation without API costs** | Playwright + Python | 24/7 deployment ready

---

## ⚡ Quick Start (5 Minutes)

### 1. Clone and Setup
```bash
cd x-automation-bot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Create Authenticated Session
```bash
python create_session.py
# A browser will open → Log in manually → Saves session.json
```

### 3. Run the Bot
```bash
python run_bot.py
# Bot runs continuously, Ctrl+C to stop
```

---

## 📋 What This Bot Does

✅ **Search** tweets by keyword  
✅ **Like** tweets automatically  
✅ **Reply** with AI-generated contextual responses  
✅ **Follow** relevant users  
✅ **Quote** tweets  
✅ **Post** new tweets  
✅ **Runs 24/7** with rate limiting  
✅ **No API costs** - pure browser automation  

---

## 🏗️ Project Structure

```
browser/
  ├── browser_manager.py    # Core browser lifecycle
  └── stealth.py            # Anti-detection techniques

actions/
  ├── like.py               # Like action
  ├── reply.py              # Reply action
  ├── follow.py             # Follow action
  └── quote.py              # Quote tweet action

core/
  ├── engagement.py         # Main automation loop
  ├── generator.py          # AI content generation
  ├── scheduler.py          # Rate limiting
  └── moderator.py          # Safety checks

search/
  └── search_tweets.py      # Tweet discovery

utils/
  ├── human_behavior.py     # Natural delays & patterns
  ├── selectors.py          # DOM selector management
  ├── performance_tracker.py # Bot health metrics
  └── engagement_score.py   # Score tweets for interaction

config.py                   # Configuration
run_bot.py                  # Main entry point
create_session.py           # Session creator
```

---

## 🔑 Authentication & Session Management

### How Sessions Work

1. **First Time:**
   ```bash
   python create_session.py
   # Opens real Chrome browser
   # You log in manually (X accepts this)
   # Saves authentication cookies to session.json
   ```

2. **Subsequent Runs:**
   ```bash
   python run_bot.py
   # Loads cookies from session.json
   # Already authenticated, no login needed
   ```

3. **Session Refresh:**
   - Lasts ~1 year per login
   - Cookies auto-refresh with each request
   - Regenerate if auth expires

### Security Notes

- **Never commit** `session.json` to git (add to `.gitignore`)
- **Use GitHub Secrets** for API keys in Actions
- **File permissions**: `chmod 600` on `.env` (servers)
- **Rotate** session monthly for security

---

## 🚀 Deployment Options

### Option 1: Local/Personal Computer

```bash
# Install once
pip install -r requirements.txt
playwright install chromium

# Create session
python create_session.py

# Run bot
python run_bot.py
```

**Pros:** Full control, no cloud costs  
**Cons:** Computer must stay on  

---

### Option 2: GitHub Actions (Recommended for Free)

#### Step 1: Add Secrets to GitHub

Go to: **Repo → Settings → Secrets and Variables → Actions**

Add these secrets:
- `ANTHROPIC_API_KEY` - Get from https://console.anthropic.com
- Use existing X API keys if needed (optional)

#### Step 2: Ensure session.json Exists Locally

```bash
python create_session.py
git add session.json  # Single exception to commit
git commit -m "Add authenticated X session"
```

#### Step 3: Workflow Runs Automatically

- Scheduled: Every 6 hours
- Manual trigger: GitHub Actions UI
- Logs available in Actions tab

**Pricing:** Free 2,000 minutes/month (plenty for 6-hourly runs)

---

### Option 3: VPS/Server (DigitalOcean, Linode, AWS)

#### Step 1: SSH & Install

```bash
ssh user@your-vps.com
cd /opt/x-bot

# Install dependencies
apt-get update
apt-get install -y python3.12 python3-pip
pip install -r requirements.txt
playwright install chromium
```

#### Step 2: Configure Environment

```bash
nano .env
# Add your API keys
ANTHROPIC_API_KEY=sk-ant-...

chmod 600 .env  # Restrict permissions
```

#### Step 3: Run with Supervisor (Daemonize)

```bash
sudo apt-get install supervisor

# Create /etc/supervisor/conf.d/x-bot.conf:
[program:x-bot]
directory=/opt/x-bot
command=/usr/bin/python3 /opt/x-bot/run_bot.py
autostart=true
autorestart=true
stderr_logfile=/var/log/x-bot.err.log
stdout_logfile=/var/log/x-bot.out.log

# Start bot
sudo supervisorctl reread && supervisorctl update
sudo supervisorctl start x-bot
```

**Monitoring:**
```bash
sudo supervisorctl status x-bot
tail -f /var/log/x-bot.out.log
```

**Pricing:** ~$5/month for basic VPS

---

## ⚙️ Configuration

Edit `config.py` to customize:

```python
# Rate limits
MAX_LIKES_PER_RUN = 8        # Likes per cycle
MAX_REPLIES_PER_RUN = 4      # Replies per cycle
MAX_QUOTES_PER_RUN = 2       # Quotes per cycle

# Timeouts
TIMEOUT_PAGE_LOAD = 15000    # ms
TIMEOUT_ACTION = 5000        # ms

# AI Settings
AI_MODEL_DRAFT = "claude-3-haiku-20240307"
AI_MAX_TOKENS = 200
AI_MAX_RETRIES = 3

# Delays (human-like behavior)
MIN_DELAY = 1.5              # seconds
MAX_DELAY = 4                # seconds
MIN_DELAY_KEYBOARD = 20      # ms per character
```

---

## 🛡️ Anti-Detection Techniques

The bot includes multiple layers to avoid X detection:

1. **Stealth Scripts** - Hide webdriver flag
2. **Browser Fingerprinting** - Real user agent, viewport
3. **Rate Limiting** - Daily action caps
4. **Natural Behavior** - Random delays, scrolling patterns
5. **Error Handling** - Exponential backoff on failures

To disable stealth (not recommended):
```python
# In browser_manager.py
# inject_stealth_script(self.page)  # Comment out
```

---

## 🐛 Troubleshooting

### Issue: "Not authenticated"
```
❌ Not authenticated to X. Please run: python create_session.py
```

**Solution:**
```bash
python create_session.py
# Log in manually in browser window
# Wait for page to fully load
# Press ENTER to save session
```

### Issue: "Element not clickable"
The DOM might have changed or modal is blocking.

**Solution:**
1. Update selectors in `utils/selectors.py`
2. Run `python create_session.py` again
3. Check X.com login in regular Chrome (may require 2FA)

### Issue: "Timeout exceeded"
Element or page load took too long.

**Solution:**
1. Increase timeout in `config.py`
2. Check internet connection
3. X might be rate-limiting - wait a few minutes

### Issue: "Could not resolve authentication method"
Anthropic API key is missing.

**Solution:**
1. Get key from https://console.anthropic.com/account/keys
2. Add to `.env`: `ANTHROPIC_API_KEY=sk-ant-...`
3. Or GitHub Secrets if using Actions

---

## 📊 Monitoring & Health

### Check Bot Status

**Locally:**
```bash
ps aux | grep run_bot.py  # Linux/Mac
tasklist | findstr python  # Windows
```

**On VPS:**
```bash
sudo supervisorctl status x-bot
tail -f /var/log/x-bot.out.log
```

**GitHub Actions:**
1. Repo → Actions tab
2. Select workflow run
3. View logs in real-time

### Performance Metrics

Bot logs performance to console and `bot_metrics.json`:
```json
{
  "uptime_seconds": 3600,
  "total_cycles": 30,
  "successful_cycles": 28,
  "success_rate_percent": 93.3,
  "likes_today": 8,
  "replies_today": 3,
  "follows_today": 5
}
```

---

## 🔬 Testing

### Test Without Running Full Bot

```python
# Test authentication
python verify_session.py

# Test specific action
from browser.browser_manager import BrowserManager
from actions.like import like_tweet

browser = BrowserManager()
page = browser.start()
# Do something...
browser.close()
```

### Debug Mode

```python
# In config.py
DEBUG = True  # Enables extra logging
HEADLESS = False  # Shows browser window

# In run_bot.py
log.set_level("DEBUG")  # More verbose output
```

---

## 📈 Advanced Usage

### Custom Keywords

Edit `core/engagement.py`:
```python
keywords = [
    "AI automation",
    "web scraping",
    "Python Playwright",
    "your keywords here"
]
```

### Custom Reply Templates

Edit `core/generator.py` to customize AI context and reply style.

### Schedule Different Hours

Edit `.github/workflows/run-bot.yml`:
```yaml
schedule:
  - cron: '0 9 * * *'   # 9 AM daily
  - cron: '0 12 * * *'  # 12 PM daily
  - cron: '0 18 * * *'  # 6 PM daily
```

### Disable AI Replies

In `core/engagement.py`:
```python
# if random.random() < 0.25:
#     reply = generate_contextual_reply(tweet_text)
#     reply_tweet(page, tweet, reply)
```

---

## 📚 API Reference

### BrowserManager

```python
from browser.browser_manager import BrowserManager

browser = BrowserManager()
page = browser.start()              # Launch and authenticate
browser.check_authenticated()        # Verify logged in
browser.restart()                   # Restart on error
browser.close()                     # Graceful shutdown
```

### Actions

```python
from actions import like, reply, follow

# Like a tweet
like.like_tweet(tweet, page)
like.unlike_tweet(tweet)
like.check_if_liked(tweet)

# Reply to tweet
reply.reply_tweet(page, tweet, text)

# Follow user
follow.follow_user(tweet)
follow.unfollow_user(tweet)
```

### Human Behavior

```python
from utils.human_behavior import *

random_delay()                  # 1.5-4 sec pause
random_delay_range(500, 2000)  # milliseconds
natural_scroll(page, 1500)     # Realistic scrolling
random_pause(5, 10)            # Longer pause
human_typing(element, text)    # Type slowly
```

---

## 🤝 Contributing

Found a bug or improvement?

1. Create issue on GitHub
2. Submit pull request
3. Include explanation

---

## ⚠️ Important Disclaimers

- **Use responsibly** - Don't spam, follow X's ToS
- **Account risk** - X may suspend automation accounts
- **Rate limiting** - This bot respects limits to avoid detection
- **Personal use only** - Not for commercial services

---

## 📞 Support

For issues:
1. Check Troubleshooting section
2. Review logs (`tail -f /var/log/x-bot.out.log`)
3. Search GitHub issues
4. Check Docker logs: `docker logs bot-container`

---

## 📄 License

MIT License - Free for personal use

---

## 🎯 Next Steps

- [ ] Setup local environment
- [ ] Create authenticated session
- [ ] Test with `python run_bot.py`
- [ ] Deploy to GitHub Actions or VPS
- [ ] Monitor first 24 hours
- [ ] Adjust engagement parameters

---

**Happy automating! 🚀**
