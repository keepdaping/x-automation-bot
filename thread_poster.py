# thread_poster.py
"""
Posts multi-tweet threads to X (Twitter).
Handles the reply chain: tweet 1 → tweet 2 replies to 1 → tweet 3 replies to 2 → etc.

NOTE: Deliberately bypasses poster.py's interval guard since thread tweets
are part of a single posting action, not separate independent posts.
Only the first tweet of a thread is recorded in the posts database.
"""
from __future__ import annotations

import time
import tweepy

from config import Config
from database import posts_today, record_post
from moderator import hash_content
from logger_setup import log


# Delay between tweets in a thread (seconds)
INTER_TWEET_DELAY = 8


def _can_post_daily() -> bool:
    count = posts_today()
    if count >= Config.MAX_POSTS_PER_DAY:
        log.warning(
            f"[ThreadPoster] Daily cap reached ({count}/{Config.MAX_POSTS_PER_DAY}). "
            "Skipping thread."
        )
        return False
    return True


def post_thread(
    client: tweepy.Client,
    tweets: list[str],
    source: str,
    topic: str,
) -> bool:
    """
    Post a list of tweets as a thread on X.

    Each tweet replies to the previous one forming a proper thread.
    Only the first tweet is recorded in the posts DB to avoid
    triggering the interval guard for subsequent tweets.

    Args:
        client:  Authenticated tweepy.Client
        tweets:  List of tweet texts (3-5 items)
        source:  'ai' or 'fallback'
        topic:   Topic used to generate the thread

    Returns:
        True if thread posted successfully, False otherwise.
    """
    if not tweets:
        log.error("[ThreadPoster] No tweets provided.")
        return False

    if not _can_post_daily():
        return False

    log.info(
        f"[ThreadPoster] Posting {len(tweets)}-tweet thread "
        f"— topic: '{topic}' source: {source}"
    )

    previous_tweet_id: str | None = None
    posted_ids: list[str] = []

    for i, text in enumerate(tweets, start=1):
        try:
            if previous_tweet_id is None:
                response = client.create_tweet(text=text)
            else:
                response = client.create_tweet(
                    text=text,
                    in_reply_to_tweet_id=previous_tweet_id,
                )

            tweet_id = str(response.data["id"])
            previous_tweet_id = tweet_id
            posted_ids.append(tweet_id)

            log.success(
                f"[ThreadPoster] Tweet {i}/{len(tweets)} posted — "
                f"id={tweet_id} chars={len(text)} "
                f"content='{text[:60]}…'"
            )

            # Record only the first tweet in DB so interval guard works correctly
            if i == 1:
                record_post(
                    content=text,
                    content_hash=hash_content(text),
                    source=source,
                    topic=topic,
                    tweet_id=tweet_id,
                    status="posted",
                )

            # Delay between tweets (skip after last one)
            if i < len(tweets):
                log.info(f"[ThreadPoster] Waiting {INTER_TWEET_DELAY}s before next tweet…")
                time.sleep(INTER_TWEET_DELAY)

        except tweepy.errors.Forbidden as exc:
            log.error(f"[ThreadPoster] Tweet {i} forbidden (403): {exc}")
            return False

        except tweepy.errors.TooManyRequests as exc:
            log.warning(f"[ThreadPoster] Rate limited on tweet {i} (429): {exc}")
            return False

        except tweepy.errors.BadRequest as exc:
            log.error(f"[ThreadPoster] Bad request on tweet {i} (400): {exc}")
            return False

        except KeyboardInterrupt:
            raise

        except Exception as exc:
            log.error(
                f"[ThreadPoster] Unexpected error on tweet {i}: "
                f"{type(exc).__name__}: {exc}"
            )
            return False

    log.info(
        f"[ThreadPoster] Thread complete — "
        f"{len(posted_ids)}/{len(tweets)} tweets posted. "
        f"Root tweet id: {posted_ids[0] if posted_ids else 'none'}"
    )
    return True
