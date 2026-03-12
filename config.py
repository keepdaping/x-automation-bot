"""
Configuration management - loads from .env file.

All hardcoded values have been moved to .env.example
Update .env with your own values.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
# IMPORTANT: override=False ensures GitHub Actions secrets are NOT overridden
# by placeholder values in .env file
load_dotenv(override=False)


class Config:
    """Bot configuration with environment variable support"""
    
    # ========== API KEYS ==========
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    
    # Debug: Check where API key came from
    # This helps diagnose issues with GitHub Actions secrets not being loaded
    _api_key_source = "NOT SET"
    if ANTHROPIC_API_KEY:
        if ANTHROPIC_API_KEY == "your_api_key_here":
            _api_key_source = "placeholder (.env file) - INVALID, needs real key!"
        elif ANTHROPIC_API_KEY.startswith("sk-ant-"):
            _api_key_source = "valid (environment variable or GitHub Actions secret)"
        else:
            _api_key_source = "set but format unknown (may be invalid)"
    else:
        _api_key_source = "NOT SET - check GitHub Actions secrets or .env file"
    
    # ========== DEBUG & LOGGING ==========
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # ========== SEARCH & ENGAGEMENT ==========
    SEARCH_KEYWORDS = os.getenv("SEARCH_KEYWORDS", "AI,python,automation").split(",")
    SEARCH_KEYWORDS = [k.strip() for k in SEARCH_KEYWORDS]  # Clean up whitespace
    
    # Engagement probabilities
    LIKE_PROBABILITY = float(os.getenv("LIKE_PROBABILITY", "0.6"))
    REPLY_PROBABILITY = float(os.getenv("REPLY_PROBABILITY", "0.25"))
    FOLLOW_PROBABILITY = float(os.getenv("FOLLOW_PROBABILITY", "0.15"))
    
    # Engagement threshold
    MIN_ENGAGEMENT_SCORE = float(os.getenv("MIN_ENGAGEMENT_SCORE", "5"))
    
    # ========== RATE LIMITS - DAILY ==========
    MAX_LIKES_PER_DAY = int(os.getenv("MAX_LIKES_PER_DAY", "20"))
    MAX_REPLIES_PER_DAY = int(os.getenv("MAX_REPLIES_PER_DAY", "5"))
    MAX_FOLLOWS_PER_DAY = int(os.getenv("MAX_FOLLOWS_PER_DAY", "10"))
    MAX_POSTS_PER_DAY = int(os.getenv("MAX_POSTS_PER_DAY", "2"))
    
    # ========== RATE LIMITS - HOURLY ==========
    MAX_LIKES_PER_HOUR = int(os.getenv("MAX_LIKES_PER_HOUR", "3"))
    MAX_REPLIES_PER_HOUR = int(os.getenv("MAX_REPLIES_PER_HOUR", "1"))
    MAX_FOLLOWS_PER_HOUR = int(os.getenv("MAX_FOLLOWS_PER_HOUR", "2"))
    
    # ========== BROWSER SETTINGS ==========
    HEADLESS_MODE = os.getenv("HEADLESS_MODE", "true").lower() == "true"
    STEALTH_MODE = os.getenv("STEALTH_MODE", "true").lower() == "true"
    BROWSER_TIMEOUT_MS = int(os.getenv("BROWSER_TIMEOUT_MS", "30000"))
    
    # ========== AI SETTINGS ==========
    AI_MODEL = os.getenv("AI_MODEL", "claude-3-haiku-20240307")
    AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "100"))
    AI_QUALITY_THRESHOLD = float(os.getenv("AI_QUALITY_THRESHOLD", "7.5"))
    AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "3"))
    
    # Fallback models if primary fails
    AI_MODELS_TO_TRY = [
        "claude-3-haiku-20240307",           # Fast, cheap
        "claude-3-5-sonnet-20241022",        # Balanced
        "claude-opus-4-1",                   # Fast, expensive
    ]
    
    # ========== HUMAN BEHAVIOR ==========
    TYPING_WPM = int(os.getenv("TYPING_WPM", "60"))
    MIN_ACTION_DELAY_MS = int(os.getenv("MIN_ACTION_DELAY_MS", "2000"))
    MAX_ACTION_DELAY_MS = int(os.getenv("MAX_ACTION_DELAY_MS", "8000"))
    MIN_PAUSE_SECONDS = float(os.getenv("MIN_PAUSE_SECONDS", "2"))
    MAX_PAUSE_SECONDS = float(os.getenv("MAX_PAUSE_SECONDS", "8"))
    CYCLE_INTERVAL_MINUTES = int(os.getenv("CYCLE_INTERVAL_MINUTES", "90"))
    ADD_TIMING_VARIATION = os.getenv("ADD_TIMING_VARIATION", "true").lower() == "true"
    
    # ========== SESSION BEHAVIOR (Human-like activity patterns) ==========
    # Sessions: Period of active engagement (e.g., 8 AM - 11 PM)
    ACTIVE_START_HOUR = int(os.getenv("ACTIVE_START_HOUR", "8"))
    ACTIVE_END_HOUR = int(os.getenv("ACTIVE_END_HOUR", "23"))
    
    # Duration of each engagement session
    SESSION_DURATION_MIN = int(os.getenv("SESSION_DURATION_MIN", "20"))
    SESSION_DURATION_MAX = int(os.getenv("SESSION_DURATION_MAX", "45"))
    
    # Break time between sessions
    BREAK_DURATION_MIN = int(os.getenv("BREAK_DURATION_MIN", "30"))
    BREAK_DURATION_MAX = int(os.getenv("BREAK_DURATION_MAX", "120"))
    
    # Action pacing within sessions
    MIN_ACTION_INTERVAL_SEC = int(os.getenv("MIN_ACTION_INTERVAL_SEC", "30"))
    MAX_ACTION_INTERVAL_SEC = int(os.getenv("MAX_ACTION_INTERVAL_SEC", "180"))
    
    # Behavioral randomization (from simulation analysis for better realism)
    SESSION_CONTINUE_PROBABILITY = float(os.getenv("SESSION_CONTINUE_PROBABILITY", "0.25"))  # 25% chance to extend session
    SESSION_EXTENDED_BREAK_PROBABILITY = float(os.getenv("SESSION_EXTENDED_BREAK_PROBABILITY", "0.20"))  # 20% extended breaks
    SESSION_EXTENDED_BREAK_MIN_HOURS = int(os.getenv("SESSION_EXTENDED_BREAK_MIN_HOURS", "2"))
    SESSION_EXTENDED_BREAK_MAX_HOURS = int(os.getenv("SESSION_EXTENDED_BREAK_MAX_HOURS", "4"))
    FIRST_ACTION_DELAY_SEC_MIN = int(os.getenv("FIRST_ACTION_DELAY_SEC_MIN", "30"))
    FIRST_ACTION_DELAY_SEC_MAX = int(os.getenv("FIRST_ACTION_DELAY_SEC_MAX", "120"))
    SESSION_BROWSE_ONLY_PROBABILITY = float(os.getenv("SESSION_BROWSE_ONLY_PROBABILITY", "0.10"))  # 10% browse without action
    
    # ========== LANGUAGE SETTINGS ==========
    SUPPORTED_LANGUAGES = os.getenv("SUPPORTED_LANGUAGES", "en").split(",")
    SUPPORTED_LANGUAGES = [l.strip() for l in SUPPORTED_LANGUAGES]
    AUTO_TRANSLATE = os.getenv("AUTO_TRANSLATE", "false").lower() == "true"
    LANGUAGE_MIN_CONFIDENCE = float(os.getenv("LANGUAGE_MIN_CONFIDENCE", "0.7"))
    
    # ========== DATABASE ==========
    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/bot.db")
    RATE_LIMITER_DB = os.getenv("RATE_LIMITER_DB", "data/rate_limiter.db")
    ENGAGEMENT_LOG_RETENTION_DAYS = int(os.getenv("ENGAGEMENT_LOG_RETENTION_DAYS", "90"))
    ERROR_LOG_RETENTION_DAYS = int(os.getenv("ERROR_LOG_RETENTION_DAYS", "180"))
    
    # ========== MONITORING ==========
    EXPORT_METRICS = os.getenv("EXPORT_METRICS", "true").lower() == "true"
    METRICS_FILE = os.getenv("METRICS_FILE", "data/metrics.json")
    LOG_TO_DATABASE = os.getenv("LOG_TO_DATABASE", "true").lower() == "true"
    SAVE_ERROR_SCREENSHOTS = os.getenv("SAVE_ERROR_SCREENSHOTS", "false").lower() == "true"
    
    # ========== ERROR RECOVERY ==========
    MAX_CONSECUTIVE_ERRORS = int(os.getenv("MAX_CONSECUTIVE_ERRORS", "5"))
    DETECTION_COOLDOWN_HOURS = int(os.getenv("DETECTION_COOLDOWN_HOURS", "24"))
    
    # ========== DEPLOYMENT ==========
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    MONITORING_PORT = int(os.getenv("MONITORING_PORT", "8000"))
    
    # ========== SESSION ==========
    SESSION_FILE = os.getenv("SESSION_FILE", "session.json")
    AUTO_REFRESH_SESSION = os.getenv("AUTO_REFRESH_SESSION", "true").lower() == "true"
    SESSION_REFRESH_HOURS = int(os.getenv("SESSION_REFRESH_HOURS", "24"))
    
    # ========== LEGACY SETTINGS (keep for compatibility) ==========
    # Banned words list (for content moderation)
    BANNED_WORDS = [
        # Add any words/phrases to block here
    ]
    
    # Viral detection thresholds
    MIN_LIKES_FOR_VIRAL = 20
    MIN_REPLIES_FOR_VIRAL = 3
    
    @classmethod
    def validate(cls):
        """Validate configuration values"""
        
        errors = []
        
        # Check required API key
        if not cls.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY is required (not set in .env)")
        
        # Check probability ranges
        if not (0 < cls.LIKE_PROBABILITY < 1):
            errors.append(f"LIKE_PROBABILITY must be 0-1, got {cls.LIKE_PROBABILITY}")
        
        if not (0 < cls.REPLY_PROBABILITY < 1):
            errors.append(f"REPLY_PROBABILITY must be 0-1, got {cls.REPLY_PROBABILITY}")
        
        if not (0 < cls.FOLLOW_PROBABILITY < 1):
            errors.append(f"FOLLOW_PROBABILITY must be 0-1, got {cls.FOLLOW_PROBABILITY}")
        
        # Check rate limits
        if cls.MAX_LIKES_PER_DAY <= 0:
            errors.append("MAX_LIKES_PER_DAY must be > 0")
        
        if cls.MAX_REPLIES_PER_DAY <= 0:
            errors.append("MAX_REPLIES_PER_DAY must be > 0")
        
        # Check search keywords
        if not cls.SEARCH_KEYWORDS:
            errors.append("SEARCH_KEYWORDS cannot be empty")
        
        # Check typing WPM
        if not (20 <= cls.TYPING_WPM <= 150):
            errors.append(f"TYPING_WPM should be 20-150, got {cls.TYPING_WPM}")
        
        if errors:
            print("\n" + "="*70)
            print("❌ CONFIGURATION ERRORS:")
            print("="*70)
            for error in errors:
                print(f"  ❌ {error}")
            
            # Add diagnostic info for API key issues
            if "ANTHROPIC_API_KEY" in str(errors):
                print("\n📋 API KEY DIAGNOSTICS:")
                print(f"  • API Key Status: {cls._api_key_source}")
                print(f"  • Env Variable Set: {bool(os.getenv('ANTHROPIC_API_KEY'))}")
                print(f"  • Working Directory: {os.getcwd()}")
                print(f"\n🔧 To fix:")
                print(f"  1. Get key from: https://console.anthropic.com/account/keys")
                print(f"  2. Save to .env:  ANTHROPIC_API_KEY=sk-ant-your-key-here")
                print(f"  3. OR set env var: export ANTHROPIC_API_KEY=sk-ant-...")
                print(f"  4. OR in GitHub Actions, add to Secrets tab")
                print(f"     Then add to workflow: env: ANTHROPIC_API_KEY: ${{{{ secrets.ANTHROPIC_API_KEY }}}}")
            
            print("\nFix these errors in your .env file")
            print("="*70 + "\n")
            raise ValueError("Configuration validation failed")
        
        return True
    
    @classmethod
    def print_summary(cls):
        """Print configuration summary for debugging"""
        print("\n" + "="*70)
        print("BOT CONFIGURATION SUMMARY")
        print("="*70)
        print(f"Environment:        {cls.ENVIRONMENT}")
        print(f"Debug Mode:         {cls.DEBUG}")
        print(f"Headless:           {cls.HEADLESS_MODE}")
        print(f"Stealth Mode:       {cls.STEALTH_MODE}")
        print(f"\nSearch Keywords:    {', '.join(cls.SEARCH_KEYWORDS)}")
        print(f"Like Prob:          {cls.LIKE_PROBABILITY*100:.0f}%")
        print(f"Reply Prob:         {cls.REPLY_PROBABILITY*100:.0f}%")
        print(f"Follow Prob:        {cls.FOLLOW_PROBABILITY*100:.0f}%")
        print(f"\nDaily Limits:")
        print(f"  Likes:            {cls.MAX_LIKES_PER_DAY}")
        print(f"  Replies:          {cls.MAX_REPLIES_PER_DAY}")
        print(f"  Follows:          {cls.MAX_FOLLOWS_PER_DAY}")
        print(f"  Posts:            {cls.MAX_POSTS_PER_DAY}")
        print(f"\nAI Model:           {cls.AI_MODEL}")
        print(f"Typing Speed:       {cls.TYPING_WPM} WPM")
        print(f"Action Delay:       {cls.MIN_ACTION_DELAY_MS}-{cls.MAX_ACTION_DELAY_MS}ms")
        print("="*70 + "\n")


# NOTE: Validation is now deferred to bot startup (run_bot.py)
# This allows GitHub Actions to pass environment variables without
# failing immediately at import time
# DO NOT validate here - it breaks CI/CD pipelines!

