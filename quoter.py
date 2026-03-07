# quoter.py
"""
Quote Tweet System — finds trending tweets in your niche and quote tweets
them with your own opinion. Free exposure to other people's audiences.

Strategy:
  1. Search for recent high-engagement tweets on niche keywords
  2. Pick the most liked tweet not already quote tweeted
  3. Generate a short opinionated response
  4. Post as a quote tweet
"""
from __future__ import annotations

import random
import time
import anthropic
import tweepy

from config import Config
from database import is_tweet_liked, record_like
from logger_setup import log


# ── Configuration ─────────────────────────────────────────────────────────────

SEARCH_KEYWORDS = [
    "freelancing tips",
    "making money online",
    "learn to code",
    "AI tools 2025",
    "building in public",
    "side hustle",
    "self taught developer",
    "solopreneur",
]

MIN_LIKES_TO_QUALIFY = 15
MAX_QUOTE_TWEETS_PER_RUN = 1


# ── Quote tweet prompt ────────────────────────────────────────────────────────

_QUOTE_SYSTEM_PROMPT = """\
You are a young person building in public — learning to code, freelancing, \
and growing an audience online.

Someone posted a tweet in your niche. You want to quote tweet it with your \
own honest opinion or experience that adds value to the conversation.

Rules:
- 1-2 sentences maximum. Under 220 characters.
- Sound like a real person, not a bot. Casual and direct.
- Add your own experience, a contrasting view, or a useful addition.
- Say something that makes people curious about YOU.
- No emojis. No hashtags. No "follow me" phrases.
- Never start with "I" as the first word.
- Output ONLY the quote tweet text. Nothing else.
"""


def _generate_quote_text(original_tweet: str) -> str | None:
    try:
        client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=Config.AI_MODEL,
            max_tokens=120,
            system=_QUOTE_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f'Someone tweeted:\n\n"{original_tweet}"\n\n'
                        "Write a short quote tweet response that adds your perspective."
                    ),
                }
            ],
        )
        text = message.content[0].text.strip().strip('"').strip("'").strip()
        return text[:220] if text else None

    except KeyboardInterrupt:
        raise
    except Exception as exc:
        log.error(f"[Quoter] AI generation failed: {type(exc).__name__}: {exc}")
        return None


def run_quote_tweet_cycle(client: tweepy.Client) -> None:
    """
    Search for viral tweets in niche, pick one, and quote tweet it.
    Called once per GitHub Actions run.
    """
    log.info("─" * 50)
    log.info("[Quoter] Starting quote tweet cycle…")

    keyword = random.choice(SEARCH_KEYWORDS)
    log.info(f"[Quoter] Searching for tweets about: '{keyword}'")

    try:
        results = client.search_recent_tweets(
            query=f"{keyword} -is:retweet -is:reply lang:en",
            tweet_fields=["public_metrics", "author_id", "text"],
            max_results=20,
        )
    except Exception as exc:
        log.error(f"[Quoter] Search failed: {exc}")
        return

    if not results.data:
        log.info("[Quoter] No tweets found for this keyword.")
        return

    # Filter for qualified tweets not already processed
    qualified = [
        t for t in results.data
        if t.public_metrics.get("like_count", 0) >= MIN_LIKES_TO_QUALIFY
        and not is_tweet_liked(f"quoted_{t.id}")
    ]

    if not qualified:
        log.info(f"[Quoter] No qualifying tweets found (need {MIN_LIKES_TO_QUALIFY}+ likes).")
        return

    # Pick the most liked tweet
    target = max(qualified, key=lambda t: t.public_metrics.get("like_count", 0))
    tweet_id = str(target.id)
    tweet_text = target.text
    likes = target.public_metrics.get("like_count", 0)

    log.info(f"[Quoter] Selected tweet ({likes} likes): '{tweet_text[:80]}…'")

    quote_text = _generate_quote_text(tweet_text)
    if not quote_text:
        log.warning("[Quoter] AI returned nothing — skipping.")
        return

    try:
        delay = random.randint(5, 15)
        log.info(f"[Quoter] Waiting {delay}s before posting…")
        time.sleep(delay)

        response = client.create_tweet(
            text=quote_text,
            quote_tweet_id=tweet_id,
        )
        new_id = str(response.data["id"])

        # Mark as processed so we don't quote it again
        record_like(f"quoted_{tweet_id}")

        log.success(
            f"[Quoter] Quote tweet posted — "
            f"our_tweet={new_id} quoting={tweet_id} "
            f"content='{quote_text[:60]}…'"
        )

    except tweepy.errors.Forbidden as exc:
        log.error(f"[Quoter] Forbidden (403): {exc}")
    except tweepy.errors.TooManyRequests as exc:
        log.warning(f"[Quoter] Rate limited (429): {exc}")
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        log.error(f"[Quoter] Unexpected error: {type(exc).__name__}: {exc}")

    log.info("[Quoter] Quote tweet cycle complete.")
