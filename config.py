from __future__ import annotations
import os
import random
from datetime import date
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

    # AI Models
    AI_MODEL_DRAFT = "claude-haiku-4-5"
    AI_MODEL_CRITIQUE = "claude-sonnet-4-6"

    AI_MAX_TOKENS = 300
    AI_MAX_RETRIES = 3

    # Growth limits
    MAX_LIKES_PER_HOUR = 20
    MAX_REPLIES_PER_HOUR = 5
    MAX_QUOTES_PER_DAY = 3
    MAX_POSTS_PER_DAY = 4
    # Topics
    FRIDAY_TOPICS = [
        "learning to code",
        "AI productivity",
        "building in public",
        "freelancing lessons",
        "developer mindset",
        "startup ideas",
        "automation tools",
        "tech career growth",
        "side hustles",
        "self taught developers",
        "coding habits",
        "digital entrepreneurship",
        "online income",
        "AI workflows",
        "tech learning systems",
        "problem solving",
        "developer discipline",
        "creator economy"
    ]

    FRIDAY_FORMATS = [
        "HOOK_STORY",
        "QUOTE_STYLE",
        "QUESTION_LIST"
    ]

    SEARCH_KEYWORDS = [
        "freelancing tips",
        "AI tools 2026",
        "building in public",
        "self taught developer",
        "side hustle",
        "learn to code",
        "freelance",
        "make money online",
        "indie hacker",
        "no code"
    ]

    BANNED_WORDS = [
        "buy my course",
        "follow for more",
        "dm me",
        "link in bio"
    ]

    @classmethod
    def validate(cls):

        required = {
            "X_API_KEY": cls.X_API_KEY,
            "X_API_SECRET": cls.X_API_SECRET,
            "X_ACCESS_TOKEN": cls.X_ACCESS_TOKEN,
            "X_ACCESS_TOKEN_SECRET": cls.X_ACCESS_TOKEN_SECRET,
            "X_BEARER_TOKEN": cls.X_BEARER_TOKEN,
            "ANTHROPIC_API_KEY": cls.ANTHROPIC_API_KEY
        }

        missing = [k for k, v in required.items() if not v]

        if missing:
            raise ValueError(f"Missing env vars: {missing}")

    @classmethod
    def pick_topic(cls) -> str:
        return random.choice(cls.FRIDAY_TOPICS)

    @classmethod
    def pick_format(cls) -> str:
        return random.choice(cls.FRIDAY_FORMATS)