"""
Engagement orchestrator — delegates to AgentController (ReAct mode).

The public surface is unchanged: run_engagement(page, ...) is the single
entry point called by run_bot.py.  Internally it now creates an
AgentController instance and runs one ReAct cycle instead of the old
static for-loop over _process_single_tweet().

Legacy helpers (select_search_phrase, search_with_fallback) are kept for
backward-compatibility with any direct callers.
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
    Pick a search phrase for the next search cycle.

    Selection strategy (two-tier):
      75% of cycles → pick directly from INTENT_KEYWORDS (explicit pain-signal
                      phrases).  These target tweets whose text already contains
                      frustration/struggle language, so matched tweets score HIGH
                      or MEDIUM intent far more often than generic keywords do.
      25% of cycles → use the UCB1 bandit over the full SEARCH_PHRASES pool.
                      The bandit learns which broader phrases yield the best
                      conversion, and the 25% allocation prevents intent keywords
                      from completely starving the broader phrase pool.

    Note: `_select_search_keyword()` below is legacy code that was never wired
    into the live path.  This function is the active selection entry point.
    """
    from core.bandit import get_phrase_bandit

    intent_keywords = [k for k in getattr(Config, "INTENT_KEYWORDS", []) if k != exclude]

    # ── 75% path: pain-signal phrase (intent-targeted) ────────────────────
    if intent_keywords and random.random() < 0.75:
        chosen = random.choice(intent_keywords)
        log.info(f"Search phrase (intent-targeted, 75% path): '{chosen}'")
        return chosen

    # ── 25% path: UCB1 bandit over full phrase pool ───────────────────────
    phrases = getattr(Config, "SEARCH_PHRASES", None) or (
        getattr(Config, "SEARCH_KEYWORDS", []) + getattr(Config, "INTENT_KEYWORDS", [])
    )
    if not phrases:
        return random.choice(["need more clients", "automation not working", "building in public"])

    candidates = [p for p in phrases if p != exclude] or phrases

    try:
        bandit = get_phrase_bandit(candidates)
        chosen = bandit.select()
        log.info(f"Search phrase (bandit, 25% path): '{chosen}'")
        return chosen
    except Exception as e:
        log.warning(f"Phrase bandit failed, falling back to random: {e}")
        return random.choice(candidates)


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
    Run one ReAct engagement cycle via AgentController.

    Drop-in replacement for the old static while-loop implementation.
    All safety guarantees (rate limits, detection cooldown, MIN_REPLY_PROB
    floor, forced-fallback reply) are enforced inside AgentController.
    """
    from core.agent_controller import AgentController

    # Ensure required tables exist
    try:
        init_conversion_tracking()
        init_search_log()
    except Exception as e:
        log.warning(f"DB init warning (non-fatal): {e}")

    # Periodic side-effects that don't belong in the per-tweet loop
    rate_limiter = get_rate_limiter()
    error_handler = get_error_handler()
    content_engine = get_content_engine()

    if random.random() < 0.15:
        try:
            from core.outcome_updater import get_outcome_updater
            get_outcome_updater().check_pending_with_page(page, limit=3)
        except Exception as e:
            log.debug(f"Outcome check skipped: {e}")

    if random.random() < 0.25:
        _browse_timeline(page, rate_limiter)

    if random.random() < Config.UNFOLLOW_CHECK_PROBABILITY:
        run_unfollow_cycle(page)

    _maybe_daily_reflect(content_engine)

    # Delegate the full ReAct cycle to AgentController
    try:
        agent = AgentController(page, feedback_tracker=feedback_tracker)
        success = agent.run_cycle(keyword=keyword)
        # Only close the tracker when AgentController owns it (i.e. caller
        # did not pass one — same contract as the old _owns_feedback flag).
        agent.close()
        return success
    except Exception as e:
        log.error(f"Fatal error in AgentController cycle: {e}")
        error_handler.handle_error(e, "run_engagement_main")
        return False
