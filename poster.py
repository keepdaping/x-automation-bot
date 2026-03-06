# poster.py
"""
Handles the act of posting a tweet and recording the result.

Responsibilities:
  - Daily rate-limit enforcement  (reads from DB, not in-memory dict)
  - Startup interval guard        (no post if last post was too recent)
  - Tweepy error handling
  - Recording post outcome to DB  (this is the only place hashes are persisted)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import tweepy

from config import Config
from database import posts_today, last_posted_at, record_post
from moderator import hash_content
from logger_setup import log


def _can_post_daily() -> bool:
    count = posts_today()
    if count >= Config.MAX_POSTS_PER_DAY:
        log.warning(
            f"Daily cap reached ({count}/{Config.MAX_POSTS_PER_DAY}). "
            "Skipping this cycle."
        )
        return False
    return True


def _interval_guard() -> bool:
    """
    Prevent rapid consecutive posts (e.g. after a restart or crash loop).
    Returns False if the last post was less than MIN_INTERVAL_MINUTES ago.
    """
    last = last_posted_at()
    if last is None:
        return True  # no post history — always allow

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    elapsed_minutes = (now - last).total_seconds() / 60

    if elapsed_minutes < Config.MIN_INTERVAL_MINUTES:
        remaining = int(Config.MIN_INTERVAL_MINUTES - elapsed_minutes)
        log.warning(
            f"Interval guard: last post was {int(elapsed_minutes)}m ago. "
            f"Next post allowed in ~{remaining}m."
        )
        return False
    return True


def post_tweet(
    client: tweepy.Client,
    text: str,
    source: str,
    topic: str,
) -> bool:
    """
    Post `text` to X and persist the result to the database.

    Args:
        client:  Authenticated Tweepy v2 client.
        text:    The content to post (already moderation-approved).
        source:  'ai' or 'fallback' — for logging and audit trail.
        topic:   The topic string used to generate this post.

    Returns:
        True on success, False on any failure.
    """
    if not _can_post_daily():
        return False

    if not _interval_guard():
        return False

    content_hash = hash_content(text)

    try:
        response = client.create_tweet(text=text)
        tweet_id = response.data["id"]

        # ── Persist ONLY on confirmed success ────────────────────────────
        record_post(
            content=text,
            content_hash=content_hash,
            source=source,
            topic=topic,
            tweet_id=tweet_id,
            status="posted",
        )

        label = "AI-generated" if source == "ai" else "FALLBACK"
        log.success(
            f"[{label}] Posted — id={tweet_id} "
            f"[{posts_today()}/{Config.MAX_POSTS_PER_DAY} today]"
        )
        log.debug(f"Content: {text}")
        return True

    except tweepy.errors.Forbidden as exc:
        # 403 — duplicate content on X, suspended account, missing write scope
        log.error(f"Twitter 403 Forbidden: {exc}")
        _record_failure(content_hash, text, source, topic, "twitter_403")

    except tweepy.errors.Unauthorized as exc:
        log.error(f"Twitter 401 Unauthorized — check OAuth tokens: {exc}")
        _record_failure(content_hash, text, source, topic, "twitter_401")

    except tweepy.errors.TooManyRequests as exc:
        log.error(f"Twitter 429 Too Many Requests: {exc}")
        _record_failure(content_hash, text, source, topic, "twitter_429")

    except tweepy.errors.TwitterServerError as exc:
        log.error(f"Twitter 5xx Server Error (X outage?): {exc}")
        _record_failure(content_hash, text, source, topic, "twitter_5xx")

    except tweepy.TweepyException as exc:
        log.error(f"Tweepy error: {exc}")
        _record_failure(content_hash, text, source, topic, "tweepy_error")

    except KeyboardInterrupt:
        raise

    except Exception as exc:
        log.error(f"Unexpected posting error: {type(exc).__name__}: {exc}")
        _record_failure(content_hash, text, source, topic, f"unexpected:{type(exc).__name__}")

    return False


def _record_failure(
    content_hash: str,
    content: str,
    source: str,
    topic: str,
    reason: str,
) -> None:
    """Record a failed post attempt. Hash is NOT added to duplicate store."""
    record_post(
        content=content,
        content_hash=content_hash,
        source=source,
        topic=topic,
        tweet_id=None,
        status="failed",
        rejection_reason=reason,
    )
