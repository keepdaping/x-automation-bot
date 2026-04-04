"""
Engagement orchestrator — search, routing, and cycle management.

Decomposed modules:
  core/reply_handler.py  — _attempt_reply
  core/follow_handler.py — _attempt_follow
  core/quote_handler.py  — _attempt_quote
  core/pipeline.py       — _process_single_tweet
"""

import random
import time
from datetime import date
from typing import Optional

from utils.human_behavior import natural_scroll
from search.search_tweets import search_tweets
from actions.like import like_tweet
from actions.unfollow import run_unfollow_cycle
from utils.selectors import TWEET_ARTICLE, TWEET_TIMESTAMP

from content.engine import get_content_engine
from core.rate_limiter import get_rate_limiter
from core.error_handler import get_error_handler
from core.pipeline import _process_single_tweet

from database import (
    log_conversion, init_conversion_tracking,
    log_search, init_search_log,
    get_phrase_stats, optimize_and_reflect,
)
from logger_setup import log
from config import Config

from feedback import FeedbackTracker

# Tracks the last calendar date on which we ran the daily reflection summary.
_last_reflect_date: Optional[date] = None


def select_search_phrase(exclude: str = None) -> str:
    """
    Pick a search phrase weighted by past 7-day performance.
    Phrases that found more tweets get picked more often.
    New/untested phrases get weight=2.0 so they still get tried.
    Falls back to SEARCH_KEYWORDS + INTENT_KEYWORDS for backward compat.
    """
    phrases = getattr(Config, "SEARCH_PHRASES", None) or (
        getattr(Config, "SEARCH_KEYWORDS", []) + getattr(Config, "INTENT_KEYWORDS", [])
    )
    if not phrases:
        return random.choice(["AI tools for business", "need more clients", "building in public"])

    try:
        stats = get_phrase_stats(days=7)
    except Exception:
        stats = {}

    candidates = [p for p in phrases if p != exclude] or phrases
    weights = []
    for phrase in candidates:
        stat = stats.get(phrase)
        if stat and stat["searches"] > 0:
            weights.append(max(0.5, stat["avg_tweets_found"]))
        else:
            weights.append(2.0)  # Untested phrases get a fair chance

    return random.choices(candidates, weights=weights, k=1)[0]


def search_with_fallback(page, phrase: str):
    """
    Try up to three search strategies before giving up.
    Returns (tweets_list, phrase_actually_used).
    """
    # Strategy 1: exact phrase
    tweets = search_tweets(page, phrase)
    if tweets:
        return tweets, phrase

    # Strategy 2: simplified phrase (drop first word if long enough)
    words = phrase.split()
    if len(words) > 2:
        simplified = " ".join(words[1:])
        log.info(f"Fallback search: trying simplified phrase '{simplified}'")
        tweets = search_tweets(page, simplified)
        if tweets:
            return tweets, simplified

    # Strategy 3: different phrase from pool
    backup = select_search_phrase(exclude=phrase)
    if backup and backup != phrase:
        log.info(f"Fallback search: trying backup phrase '{backup}'")
        tweets = search_tweets(page, backup)
        if tweets:
            return tweets, backup

    return [], phrase


def _maybe_daily_reflect(content_engine):
    """Run optimize_and_reflect() once per calendar day (non-blocking)."""
    global _last_reflect_date
    today = date.today()
    if _last_reflect_date == today:
        return
    _last_reflect_date = today
    try:
        optimize_and_reflect()
    except Exception as e:
        log.warning(f"Daily reflection failed (non-fatal): {e}")


def _browse_timeline(page, rate_limiter):
    """Optional home timeline browsing to mimic human behavior."""
    try:
        page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=20000)
        time.sleep(random.uniform(2, 4))

        for _ in range(random.randint(2, 5)):
            natural_scroll(page, pixels=random.randint(800, 1600))
            time.sleep(random.uniform(1.5, 3.0))

        if random.random() < 0.35:
            tweets = page.locator(TWEET_ARTICLE).all()
            if tweets:
                tweet = random.choice(tweets)
                try:
                    time_link = tweet.locator(TWEET_TIMESTAMP).first
                    if time_link:
                        time_link.click()
                        time.sleep(random.uniform(2, 4))
                        if random.random() < 0.4 and rate_limiter.can_perform_action("like")[0]:
                            if like_tweet(tweet):
                                rate_limiter.record_action("like", success=True, target_id=None)
                except Exception:
                    pass

        try:
            page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pass

    except Exception as e:
        log.debug(f"Timeline browse error: {e}")


def _select_search_keyword(keyword):
    """Select a search keyword, preferring intent keywords occasionally."""
    intent_keywords = getattr(Config, "INTENT_KEYWORDS", [])
    if intent_keywords and random.random() < 0.40:
        search_keyword = keyword or random.choice(intent_keywords)
        log.info(f"Using INTENT keyword: {search_keyword}")
    else:
        search_keyword = keyword or random.choice(Config.SEARCH_KEYWORDS)
    return search_keyword


def run_engagement(page, config=None, keyword=None, feedback_tracker=None):
    """
    Run one cycle of engagement with all safety checks.

    FIXED: Independent of DAILY_TWEET_ENABLED.
    FIXED: Only closes FeedbackTracker when we created it (not the caller's).
    """
    try:
        rate_limiter = get_rate_limiter()
        error_handler = get_error_handler()
        content_engine = get_content_engine()

        # Track ownership so we only close what we create
        _owns_feedback = feedback_tracker is None
        feedback = feedback_tracker if feedback_tracker else FeedbackTracker()

        # Ensure required tables exist
        init_conversion_tracking()
        init_search_log()

        if error_handler.is_in_detection_cooldown():
            log.critical("⏸️  Bot is in detection cooldown - skipping")
            return False

        log.info("=" * 70)
        log.info("ENGAGEMENT CYCLE STARTING")
        log.info("=" * 70)

        remaining = rate_limiter.get_remaining_actions()
        log.info(f"Daily limits remaining: {remaining}")

        total_remaining = sum(remaining.values())
        if total_remaining == 0:
            log.info("❌ Daily limits reached - skipping cycle")
            return False

        # Occasionally browse timeline (human behavior)
        if random.random() < 0.25:
            _browse_timeline(page, rate_limiter)

        # Occasionally run unfollow cycle
        if random.random() < Config.UNFOLLOW_CHECK_PROBABILITY:
            run_unfollow_cycle(page)

        # Run once-per-day reflection/optimization (CHANGE 11)
        _maybe_daily_reflect(content_engine)

        # Search for tweets — weighted phrase selection with fallback (CHANGE 3 & 5)
        if keyword:
            search_keyword = keyword
            tweets, search_keyword = search_with_fallback(page, search_keyword)
        else:
            search_keyword = select_search_phrase()
            log.info(f"Searching for tweets (phrase: '{search_keyword}')...")
            try:
                tweets, search_keyword = search_with_fallback(page, search_keyword)
            except Exception as e:
                error_handler.handle_error(e, "search_tweets")
                return False

        if not tweets:
            log.warning(f"No tweets found for '{search_keyword}' (all fallbacks exhausted)")
            try:
                log_search(search_keyword, tweets_found=0)
            except Exception:
                pass
            return False

        log.info(f"Found {len(tweets)} tweets for '{search_keyword}'")

        actions_taken = 0
        errors_in_cycle = 0
        high_intent_found = 0

        for idx, tweet in enumerate(tweets, 1):
            log.debug(f"\n--- Processing tweet {idx}/{len(tweets)} ---")
            actions, errors, was_high_intent = _process_single_tweet(
                tweet, page, rate_limiter, error_handler,
                content_engine, search_keyword, feedback,
            )
            actions_taken += actions
            errors_in_cycle += errors
            if was_high_intent:
                high_intent_found += 1

        try:
            log_search(search_keyword, len(tweets), actions_taken, high_intent_found)
        except Exception as e:
            log.warning(f"Search log write failed: {e}")

        if _owns_feedback:
            feedback.close()

        log.info(f"\nCYCLE COMPLETE: {actions_taken} actions, {errors_in_cycle} errors\n")
        return actions_taken > 0

    except Exception as e:
        log.error(f"Fatal error in engagement cycle: {e}")
        error_handler.handle_error(e, "run_engagement_main")
        return False
