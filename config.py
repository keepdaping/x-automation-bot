"""
Configuration management - loads from .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv(override=False)


class Config:
    """Bot configuration with environment variable support"""

    # ========== API KEYS ==========
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    _api_key_source = "NOT SET"
    if ANTHROPIC_API_KEY:
        if ANTHROPIC_API_KEY == "your_api_key_here":
            _api_key_source = "placeholder - INVALID"
        elif ANTHROPIC_API_KEY.startswith("sk-ant-"):
            _api_key_source = "valid"
        else:
            _api_key_source = "set but format unknown"

    # ========== DEBUG ==========
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # ========== SEARCH & ENGAGEMENT ==========
    # Default keywords are kept as fallback only — SEARCH_PHRASES and INTENT_KEYWORDS
    # drive the actual search selection (see select_search_phrase in engagement.py).
    SEARCH_KEYWORDS = [k.strip() for k in os.getenv(
        "SEARCH_KEYWORDS",
        "struggling to get clients,need help with automation,"
        "no engagement on posts,how to get clients,"
        "no sales,looking for clients,automation not working,"
        "AI tools for business,freelancing is hard,need more leads"
    ).split(",")]

    # SEARCH_PHRASES: 2-5 word phrases that X search reliably returns results for.
    # Backward compatible: falls back to SEARCH_KEYWORDS + INTENT_KEYWORDS if not set.
    _SEARCH_PHRASES_DEFAULT = (
        "need more clients,nobody sees my content,struggling to get engagement,"
        "how do I grow on twitter,getting zero impressions,freelancing is so hard,"
        "no one is buying,need help with automation,cant find clients,"
        "my tweets get no reach,tired of no engagement,how to get followers,"
        "not making money freelancing,AI tools for business,need to automate my workflow,"
        "building my first SaaS,just started freelancing,learning to code in python,"
        "shipped my first project,building in public update,side project progress,"
        "trying to grow my account,started my own business,first paying customer,"
        "working on AI project,n8n workflow automation,AI agent for business,"
        "automated my workflow,replaced manual process,using AI to save time,"
        "built an automation,chatbot for customer support,AI replacing tasks,"
        "workflow automation tools,zapier vs make"
    )
    _env_phrases = os.getenv("SEARCH_PHRASES")
    if _env_phrases:
        SEARCH_PHRASES = [k.strip() for k in _env_phrases.split(",") if k.strip()]
    else:
        _intent_kws = [k.strip() for k in os.getenv("INTENT_KEYWORDS", "").split(",") if k.strip()]
        _combined = SEARCH_KEYWORDS + _intent_kws
        SEARCH_PHRASES = _combined if _combined else [
            k.strip() for k in _SEARCH_PHRASES_DEFAULT.split(",") if k.strip()
        ]

    # ========== REFLECTION & GROK ==========
    REFLECTION_ENABLED = os.getenv("REFLECTION_ENABLED", "true").lower() == "true"
    GROK_STYLE = os.getenv("GROK_STYLE", "true").lower() == "true"

    GROK_SYSTEM_INSTRUCTION = os.getenv(
        "GROK_SYSTEM_INSTRUCTION",
        "You are Grok-inspired: maximally truth-seeking and helpful. "
        "Be direct, honest, and evidence-based. "
        "Cut the corporate fluff, exaggerated promises, and overly polite curiosity bait. "
        "Acknowledge real problems plainly. Use light wit or sarcasm only when it adds value. "
        "Base every suggestion on what actually works for AI/automation tools. "
        "Output ONLY the reply — nothing else. Under 30 words. "
        "Goal: help the user solve their real problem so they DM for more help.",
    )

    LIKE_PROBABILITY = float(os.getenv("LIKE_PROBABILITY", "0.6"))
    REPLY_PROBABILITY = float(os.getenv("REPLY_PROBABILITY", "0.25"))
    FOLLOW_PROBABILITY = float(os.getenv("FOLLOW_PROBABILITY", "0.15"))
    MIN_ENGAGEMENT_SCORE = float(os.getenv("MIN_ENGAGEMENT_SCORE", "5"))

    # ========== DAILY POSTING ==========
    DAILY_TWEET_ENABLED = os.getenv("DAILY_TWEET_ENABLED", "true").lower() == "true"
    DAILY_TWEET_START_HOUR_UTC = int(os.getenv("DAILY_TWEET_START_HOUR_UTC", "10"))
    DAILY_TWEET_END_HOUR_UTC = int(os.getenv("DAILY_TWEET_END_HOUR_UTC", "13"))
    CACHE_EXPIRY_DAYS = int(os.getenv("CACHE_EXPIRY_DAYS", "30"))

    # ========== CONTENT PILLARS (rotating daily themes) ==========
    CONTENT_PILLARS = [p.strip() for p in os.getenv(
        "CONTENT_PILLARS",
        "money:Making money online and financial freedom,"
        "building:Building products and side projects and shipping code,"
        "journey:Personal growth and lessons learned as a developer"
    ).split(",") if p.strip()]

    VIRAL_HOOKS = [h.strip() for h in os.getenv(
        "VIRAL_HOOKS",
        "hot_take,question,thread_hook,contrarian,story,tip"
    ).split(",") if h.strip()]

    # ========== INTENT KEYWORDS (pain-based lead discovery) ==========
    # These are the primary search phrases (75% of cycles via select_search_phrase).
    # Each phrase is 3-7 words targeting explicit frustration or need expression
    # so that X search results are pre-filtered to high-intent tweets.
    INTENT_KEYWORDS = [k.strip() for k in os.getenv(
        "INTENT_KEYWORDS",
        # Client / revenue pain
        "struggling to get clients,need more clients,can't find clients,"
        "how to get clients,looking for clients,not getting clients,"
        "no one is buying,zero sales,no sales,how to monetize,"
        # Engagement / reach pain
        "no engagement on posts,nobody sees my content,getting zero impressions,"
        "my tweets get no reach,struggling to grow,nobody sees my posts,"
        "tired of no engagement,no views no impressions,"
        # Automation / tool pain
        "need help with automation,automation not working,my automation broke,"
        "workflow not working,need to automate my workflow,"
        # Freelance / business pain
        "freelancing is so hard,freelance is hard,cant find clients,"
        "not making money freelancing,side hustle not working,"
        # Growth / general pain
        "how to get followers,need more leads,not getting results,"
        "trying to grow my account,what am i doing wrong"
    ).split(",") if k.strip()]

    # ========== RATE LIMITS - DAILY ==========
    MAX_LIKES_PER_DAY = int(os.getenv("MAX_LIKES_PER_DAY", "20"))
    MAX_REPLIES_PER_DAY = int(os.getenv("MAX_REPLIES_PER_DAY", "15"))
    MAX_FOLLOWS_PER_DAY = int(os.getenv("MAX_FOLLOWS_PER_DAY", "10"))
    MAX_UNFOLLOWS_PER_DAY = int(os.getenv("MAX_UNFOLLOWS_PER_DAY", "5"))
    MAX_POSTS_PER_DAY = int(os.getenv("MAX_POSTS_PER_DAY", "1"))
    MAX_QUOTES_PER_DAY = int(os.getenv("MAX_QUOTES_PER_DAY", "2"))

    # ========== RATE LIMITS - HOURLY ==========
    MAX_LIKES_PER_HOUR = int(os.getenv("MAX_LIKES_PER_HOUR", "3"))
    MAX_REPLIES_PER_HOUR = int(os.getenv("MAX_REPLIES_PER_HOUR", "2"))
    MAX_FOLLOWS_PER_HOUR = int(os.getenv("MAX_FOLLOWS_PER_HOUR", "2"))

    # ========== UNFOLLOW SETTINGS ==========
    UNFOLLOW_AFTER_DAYS = int(os.getenv("UNFOLLOW_AFTER_DAYS", "7"))
    UNFOLLOW_CHECK_PROBABILITY = float(os.getenv("UNFOLLOW_CHECK_PROBABILITY", "0.3"))

    # ========== BROWSER ==========
    HEADLESS_MODE = os.getenv("HEADLESS_MODE", "true").lower() == "true"
    STEALTH_MODE = os.getenv("STEALTH_MODE", "true").lower() == "true"
    BROWSER_TIMEOUT_MS = int(os.getenv("BROWSER_TIMEOUT_MS", "30000"))

    # ========== AI ==========
    AI_MODEL = os.getenv("AI_MODEL", "claude-haiku-4-5-20251001")
    AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "150"))
    AI_QUALITY_THRESHOLD = float(os.getenv("AI_QUALITY_THRESHOLD", "7.5"))
    AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "3"))

    AI_MODELS_TO_TRY = [
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-6",
    ]

    # ========== CONTENT MODERATION (configurable) ==========
    BANNED_WORDS = [w.strip().lower() for w in os.getenv(
        "BANNED_WORDS",
        "viagra,cialis,pharmacy,mlm,pyramid,dropship"
    ).split(",") if w.strip()]

    # ========== HUMAN BEHAVIOR ==========
    TYPING_WPM = int(os.getenv("TYPING_WPM", "60"))
    MIN_ACTION_DELAY_MS = int(os.getenv("MIN_ACTION_DELAY_MS", "2000"))
    MAX_ACTION_DELAY_MS = int(os.getenv("MAX_ACTION_DELAY_MS", "8000"))
    MIN_PAUSE_SECONDS = float(os.getenv("MIN_PAUSE_SECONDS", "2"))
    MAX_PAUSE_SECONDS = float(os.getenv("MAX_PAUSE_SECONDS", "8"))
    CYCLE_INTERVAL_MINUTES = int(os.getenv("CYCLE_INTERVAL_MINUTES", "90"))
    ADD_TIMING_VARIATION = os.getenv("ADD_TIMING_VARIATION", "true").lower() == "true"

    # ========== SESSION BEHAVIOR ==========
    ACTIVE_START_HOUR = int(os.getenv("ACTIVE_START_HOUR", "8"))
    ACTIVE_END_HOUR = int(os.getenv("ACTIVE_END_HOUR", "23"))
    SESSION_DURATION_MIN = int(os.getenv("SESSION_DURATION_MIN", "20"))
    SESSION_DURATION_MAX = int(os.getenv("SESSION_DURATION_MAX", "45"))
    BREAK_DURATION_MIN = int(os.getenv("BREAK_DURATION_MIN", "30"))
    BREAK_DURATION_MAX = int(os.getenv("BREAK_DURATION_MAX", "120"))
    MIN_ACTION_INTERVAL_SEC = int(os.getenv("MIN_ACTION_INTERVAL_SEC", "30"))
    MAX_ACTION_INTERVAL_SEC = int(os.getenv("MAX_ACTION_INTERVAL_SEC", "180"))
    SESSION_CONTINUE_PROBABILITY = float(os.getenv("SESSION_CONTINUE_PROBABILITY", "0.40"))
    SESSION_EXTENDED_BREAK_PROBABILITY = float(os.getenv("SESSION_EXTENDED_BREAK_PROBABILITY", "0.0"))
    SESSION_EXTENDED_BREAK_MIN_HOURS = int(os.getenv("SESSION_EXTENDED_BREAK_MIN_HOURS", "2"))
    SESSION_EXTENDED_BREAK_MAX_HOURS = int(os.getenv("SESSION_EXTENDED_BREAK_MAX_HOURS", "4"))
    FIRST_ACTION_DELAY_SEC_MIN = int(os.getenv("FIRST_ACTION_DELAY_SEC_MIN", "30"))
    FIRST_ACTION_DELAY_SEC_MAX = int(os.getenv("FIRST_ACTION_DELAY_SEC_MAX", "120"))
    SESSION_BROWSE_ONLY_PROBABILITY = float(os.getenv("SESSION_BROWSE_ONLY_PROBABILITY", "0.05"))

    # ========== LANGUAGE ==========
    SUPPORTED_LANGUAGES = [lang.strip() for lang in os.getenv("SUPPORTED_LANGUAGES", "en").split(",")]
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
    SESSION_FILE = os.getenv("SESSION_FILE", "session.json")
    AUTO_REFRESH_SESSION = os.getenv("AUTO_REFRESH_SESSION", "true").lower() == "true"
    SESSION_REFRESH_HOURS = int(os.getenv("SESSION_REFRESH_HOURS", "24"))

    # ========== LEGACY ==========
    MIN_LIKES_FOR_VIRAL = 20
    MIN_REPLIES_FOR_VIRAL = 3

        # ========== MIGRATION FLAGS (2026 redesign) ==========
    # Phase 1: Intent detection
    INTENT_MODE = os.getenv("INTENT_MODE", "keyword")  # "keyword" | "hybrid" | "llm"

    # Phase 2+: Conversations
    CONVERSATION_ENABLED = os.getenv("CONVERSATION_ENABLED", "false").lower() == "true"

    # Phase 3+: Self-improving
    FEEDBACK_ANALYSIS_ENABLED = os.getenv("FEEDBACK_ANALYSIS_ENABLED", "false").lower() == "true"

    # Safety during migration
    AGGRESSION_LEVEL = float(os.getenv("AGGRESSION_LEVEL", "0.6"))  # 0.0-1.0 multiplier for rates

    @classmethod
    def validate(cls):
        errors = []
        if not cls.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY is required")
        if not (0 <= cls.LIKE_PROBABILITY <= 1):
            errors.append(f"LIKE_PROBABILITY must be 0-1, got {cls.LIKE_PROBABILITY}")
        if not (0 <= cls.REPLY_PROBABILITY <= 1):
            errors.append(f"REPLY_PROBABILITY must be 0-1, got {cls.REPLY_PROBABILITY}")
        if not (0 <= cls.FOLLOW_PROBABILITY <= 1):
            errors.append(f"FOLLOW_PROBABILITY must be 0-1, got {cls.FOLLOW_PROBABILITY}")
        if not cls.SEARCH_KEYWORDS:
            errors.append("SEARCH_KEYWORDS cannot be empty")
        if errors:
            print("\n" + "=" * 70)
            print("❌ CONFIGURATION ERRORS:")
            print("=" * 70)
            for error in errors:
                print(f"  ❌ {error}")
            if "ANTHROPIC_API_KEY" in str(errors):
                print(f"\n📋 API Key Status: {cls._api_key_source}")
                print("   Get key from: https://console.anthropic.com/account/keys")
            print("=" * 70 + "\n")
            raise ValueError("Configuration validation failed")
        return True

    @classmethod
    def get_content_pillar(cls, day_of_year: int) -> dict:
        """Get today's content pillar based on deterministic rotation."""
        if not cls.CONTENT_PILLARS:
            return {"name": "general", "description": "general tech topics"}
        pillar_str = cls.CONTENT_PILLARS[day_of_year % len(cls.CONTENT_PILLARS)]
        if ":" in pillar_str:
            name, desc = pillar_str.split(":", 1)
            return {"name": name.strip(), "description": desc.strip()}
        return {"name": pillar_str, "description": pillar_str}

    @classmethod
    def get_viral_hook(cls) -> str:
        import random
        return random.choice(cls.VIRAL_HOOKS) if cls.VIRAL_HOOKS else "tip"
