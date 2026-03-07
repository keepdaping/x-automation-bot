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
    ENABLE_DAILY_GREETING: bool       = False

    # ── Daily theme schedule ──────────────────────────────────────────────
    DAILY_THEMES: dict[int, dict] = {
        0: {  # Monday — Making Money Online
            "name": "Making Money Online",
            "emoji": "💰",
            "topics": [
                "an honest truth about freelancing nobody tells beginners",
                "how to land your first client online with no experience",
                "why most people fail at making money online and how to avoid it",
                "a simple way to start earning online with just a laptop",
            ],
        },
        1: {  # Tuesday — AI & Automation
            "name": "AI & Automation",
            "emoji": "🤖",
            "topics": [
                "a free AI tool that saves hours of work every week",
                "how regular people are using AI to make money right now",
                "why ignoring AI tools is the biggest mistake you can make in 2025",
                "a simple automation anyone can build to save time daily",
            ],
        },
        2: {  # Wednesday — Learning & Coding
            "name": "Learning & Coding",
            "emoji": "💻",
            "topics": [
                "an honest lesson from teaching yourself to code",
                "why building real projects beats tutorials every single time",
                "the fastest way to learn coding when you have no money for courses",
                "a relatable struggle every self-taught coder goes through",
            ],
        },
        3: {  # Thursday — Freelancing Tips
            "name": "Freelancing Tips",
            "emoji": "🧑‍💻",
            "topics": [
                "how to price your services when you are just starting out",
                "the biggest mistake new freelancers make with clients",
                "how to find clients on the internet with zero reputation",
                "what nobody tells you about working for yourself",
            ],
        },
        4: {  # Friday — Mindset & Motivation
            "name": "Mindset & Motivation",
            "emoji": "🧠",
            "topics": [
                "a mindset shift that changes how you approach building things",
                "why starting messy beats waiting until you feel ready",
                "an honest truth about the self-improvement journey",
                "what separates people who build things from people who just dream",
            ],
        },
        5: {  # Saturday — Building in Public
            "name": "Building in Public",
            "emoji": "🚀",
            "topics": [
                "a real lesson from building a project from scratch",
                "why sharing your journey online attracts more opportunities",
                "what it actually feels like to build something on your own",
                "a small win worth celebrating when building something new",
            ],
        },
        6: {  # Sunday — Life & Growth
            "name": "Life & Growth",
            "emoji": "🌱",
            "topics": [
                "a life lesson you only learn by doing hard things",
                "why consistency beats motivation every single time",
                "an uncomfortable truth about growing up and chasing goals",
                "what young people building their future need to hear today",
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

    @classmethod
    def get_todays_theme(cls) -> dict:
        weekday = date.today().weekday()
        return cls.DAILY_THEMES[weekday]

    @classmethod
    def get_todays_topics(cls) -> list[str]:
        return cls.get_todays_theme()["topics"]

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
