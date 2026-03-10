from __future__ import annotations
import os
import random
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

class Config:
    # X Credentials
    X_API_KEY = os.getenv("X_API_KEY")
    X_API_SECRET = os.getenv("X_API_SECRET")
    X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
    X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")
    X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")

    # Anthropic
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    # AI Models (2026)
    AI_MODEL_DRAFT     = "claude-haiku-4-5"
    AI_MODEL_CRITIQUE  = "claude-sonnet-4-6"
    AI_MAX_TOKENS = 300
    AI_MAX_RETRIES = 3

    # Growth limits (safe 2026)
    MAX_POSTS_PER_DAY = 4
    MIN_INTERVAL_MINUTES = 90
    MAX_LIKES_PER_HOUR = 20
    MAX_REPLIES_PER_HOUR = 5
    MAX_QUOTES_PER_DAY = 3

    # Topics & Formats
    FRIDAY_TOPICS = [ ... ]  # (your original 18 topics kept + expanded)
    FRIDAY_FORMATS = ["HOOK_STORY", "THREAD", "QUOTE_STYLE", "QUESTION_LIST"]

    SEARCH_KEYWORDS = [
    "freelancing tips", "AI tools 2026", "building in public",
    "self taught developer", "side hustle", "learn to code",
    "freelance", "make money online", "indie hacker", "no code"
    ]

    BANNED_WORDS = ["buy my course", "follow for more", "dm me", "link in bio"]

    @classmethod
    def validate(cls):
        missing = [k for k, v in {
            "X_API_KEY": cls.X_API_KEY, "ANTHROPIC_API_KEY": cls.ANTHROPIC_API_KEY,
            # ... all required
        }.items() if not v]
        if missing:
            raise ValueError(f"Missing env vars: {missing}")

    @classmethod
    def pick_topic(cls) -> str:
        day = date.today().timetuple().tm_yday
        return cls.FRIDAY_TOPICS[(day - 1) % len(cls.FRIDAY_TOPICS)]

    @classmethod
    def pick_format(cls) -> str:
        day = date.today().timetuple().tm_yday
        return cls.FRIDAY_FORMATS[(day - 1) % len(cls.FRIDAY_FORMATS)]