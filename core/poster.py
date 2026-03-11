# core/poster.py

import time
import random
from tweepy import Client
from logger_setup import log
from database import save_post, is_duplicate
from config import Config
from .moderator import is_safe_content


def can_post_today(client: Client) -> bool:

    from database import count_posts_today

    return count_posts_today() < Config.MAX_POSTS_PER_DAY


def post_tweet(client: Client, text: str, topic: str, fmt: str, score: float) -> str | None:

    if is_duplicate(text):
        log.warning("Duplicate content detected — skipping")
        return None

    if not can_post_today(client):
        log.info("Daily post limit reached")
        return None

    if not is_safe_content(text):
        log.warning("Content failed moderation")
        return None

    try:

        # Ensure tweet length safe
        text = text[:280]

        # Human-like delay
        delay = random.uniform(8, 35)
        log.info(f"Waiting {delay:.1f}s before posting…")

        time.sleep(delay)

        response = client.create_tweet(text=text)

        tweet_id = response.data["id"]

        # Save post once
        save_post(
            text,
            tweet_id,
            str(topic),
            str(fmt),
            float(score)
        )

        log.success(f"Posted tweet → {tweet_id} | score {score:.1f}")

        return tweet_id

    except Exception as e:

        log.error(f"Posting failed: {e}")

        return None