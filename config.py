# config.py
from __future__ import annotations

import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── X API Credentials (OAuth 1.0a) ────────────────────────────────────
    X_API_KEY: str | None             = os.getenv("X_API_KEY")
    X_API_SECRET: str | None          = os.getenv("X_API_SECRET")
    X_ACCESS_TOKEN: str | None        = os.getenv("X_ACCESS_TOKEN")
    X_ACCESS_TOKEN_SECRET: str | None = os.getenv("X_ACCESS_TOKEN_SECRET")
    X_BEARER_TOKEN: str | None        = os.getenv("X_BEARER_TOKEN")

    # ── Anthropic ─────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str | None     = os.getenv("ANTHROPIC_API_KEY")

    # ── Posting behaviour ─────────────────────────────────────────────────
    MAX_POSTS_PER_DAY: int            = int(os.getenv("MAX_POSTS_PER_DAY", "10"))
    MIN_INTERVAL_MINUTES: int         = int(os.getenv("MIN_INTERVAL_MINUTES", "90"))
    MAX_POST_LENGTH: int              = 280

    # ── AI generation ─────────────────────────────────────────────────────
    AI_MODEL: str                     = "claude-haiku-4-5-20251001"
    AI_MAX_TOKENS: int                = 200
    AI_MAX_RETRIES: int               = 3

    # ── Logging ───────────────────────────────────────────────────────────
    LOG_LEVEL: str                    = os.getenv("LOG_LEVEL", "INFO").upper()

    # ── Database ──────────────────────────────────────────────────────────
    DB_PATH: str                      = os.getenv("DB_PATH", "data/bot.db")

    # ── Greeting (once per day) ───────────────────────────────────────────
    # Set to True to allow the bot to prepend a time-appropriate greeting
    # (Good morning / Good afternoon / Good evening) to the first post each day.
    # Greeting is never repeated within the same calendar day.
    ENABLE_DAILY_GREETING: bool       = True

    # ── Daily theme schedule ──────────────────────────────────────────────
    # Each entry maps to one weekday (0 = Monday … 6 = Sunday).
    # "topics" is the pool the bot picks from randomly on that day.
    # Add or rename themes freely — the rotation is purely day-of-week based.
    DAILY_THEMES: dict[int, dict] = {
        0: {  # Monday — Engineering Mindset
            "name": "Engineering Mindset",
            "emoji": "🧠",
            "topics": [
                "a counterintuitive truth about how great engineers think",
                "a mindset shift that separates senior from junior engineers",
                "why writing less code is usually the harder skill",
                "the mental model that changes how you debug complex systems",
            ],
        },
        1: {  # Tuesday — System Design
            "name": "System Design",
            "emoji": "🏗️",
            "topics": [
                "a concise insight about distributed systems trade-offs",
                "why most teams over-engineer their first version",
                "the system design mistake that only shows up at scale",
                "a hard truth about consistency vs availability in real systems",
            ],
        },
        2: {  # Wednesday — API & Backend Craft
            "name": "API & Backend Craft",
            "emoji": "🔌",
            "topics": [
                "a practical API design principle most teams ignore",
                "the HTTP status code engineers misuse most and why it matters",
                "why idempotency is the most underrated backend concept",
                "a backend architecture pattern that saves you at 10x traffic",
            ],
        },
        3: {  # Thursday — Code Quality
            "name": "Code Quality",
            "emoji": "✍️",
            "topics": [
                "a hard-earned lesson about writing code that survives a year",
                "why the best code review catches design issues not style issues",
                "the naming convention mistake that slows every team down",
                "what makes a codebase genuinely maintainable vs just readable",
            ],
        },
        4: {  # Friday — Productivity & Focus
            "name": "Productivity & Focus",
            "emoji": "⚡",
            "topics": [
                "the productivity habit that actually compounds for engineers",
                "why deep work and flow state are not the same thing",
                "the meeting pattern that kills engineering output silently",
                "a counterintuitive truth about shipping faster as a team",
            ],
        },
        5: {  # Saturday — Career & Growth
            "name": "Career & Growth",
            "emoji": "📈",
            "topics": [
                "the career move most engineers regret not making earlier",
                "what distinguishes engineers who grow fast from those who plateau",
                "a hard truth about technical leadership nobody says out loud",
                "why optimising for learning rate beats optimising for salary",
            ],
        },
        6: {  # Sunday — Debugging & Problem Solving
            "name": "Debugging & Problem Solving",
            "emoji": "🔍",
            "topics": [
                "the debugging technique that finds bugs other methods miss",
                "why most production outages are caused by the rollback not the change",
                "a systematic approach to problems that look random",
                "the observability gap that makes hard bugs nearly impossible to trace",
            ],
        },
    }

    # ── Moderation: reject posts containing these phrases ─────────────────
    BLOCKED_KEYWORDS: list[str] = [
        "follow me",
        "retweet",
        "giveaway",
        "click here",
        "buy now",
        "free money",
        "guaranteed",
        "dm me",
        "link in bio",
    ]

    # ── Theme helpers ─────────────────────────────────────────────────────

    @classmethod
    def get_todays_theme(cls) -> dict:
        """Return the theme dict for today's weekday."""
        weekday = date.today().weekday()   # 0 = Monday, 6 = Sunday
        return cls.DAILY_THEMES[weekday]

    @classmethod
    def get_todays_topics(cls) -> list[str]:
        """Return today's topic pool."""
        return cls.get_todays_theme()["topics"]

    # ── Startup validation ────────────────────────────────────────────────

    @classmethod
    def validate(cls) -> None:
        required: dict[str, str | None] = {
            "X_API_KEY":             cls.X_API_KEY,
            "X_API_SECRET":          cls.X_API_SECRET,
            "X_ACCESS_TOKEN":        cls.X_ACCESS_TOKEN,
            "X_ACCESS_TOKEN_SECRET": cls.X_ACCESS_TOKEN_SECRET,
            "X_BEARER_TOKEN":        cls.X_BEARER_TOKEN,
            "ANTHROPIC_API_KEY":     cls.ANTHROPIC_API_KEY,
        }
        missing = [name for name, val in required.items() if not val]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                "Copy .env.example → .env and fill in your credentials."
            )
