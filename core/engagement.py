"""
Main engagement engine with rate limiting and error recovery.

FIXED: Engagement loop no longer nested under DAILY_TWEET_ENABLED check.
FIXED: Removed unused get_llm_intent_scorer import (the post-reply dead block
       that called it was removed in Phase 1; import was the only reference).
ADDED: Unfollow strategy integration.
ADDED: Feedback tracker ownership guard (only close locally-created trackers).
"""

import random
import time
from datetime import date
from typing import Optional

from utils.human_behavior import natural_scroll
from search.search_tweets import search_tweets
from actions.like import like_tweet
from actions.reply import reply_tweet
from actions.follow import follow_user
from actions.quote_tweet import quote_tweet
from actions.unfollow import run_unfollow_cycle
from utils.selectors import TWEET_ARTICLE, TWEET_TIMESTAMP

from content.engine import get_content_engine, GenerationResult
from core.rate_limiter import get_rate_limiter
from core.error_handler import get_error_handler
from core.generator import generate_contextual_reply
from utils.tweet_metrics import get_tweet_metrics
from utils.engagement_score import score_tweet
from utils.tweet_text import get_tweet_text
from utils.language_handler import should_reply_to_tweet_safe
from utils.intent_scorer import score_intent, get_intent_label
from utils.llm_intent_scorer import get_llm_intent_scorer

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


def _attempt_reply(tweet, page, rate_limiter, error_handler, content_engine,
                   search_keyword, tweet_text, intent, intent_label,
                   use_curiosity, feedback, reflection_summary=""):
    """Attempt to reply to a tweet. Returns (actions_taken, errors_in_cycle)"""
    actions_taken = 0
    errors_in_cycle = 0

    if rate_limiter.can_perform_action("reply")[0]:
        try:
            should_reply, reason = should_reply_to_tweet_safe(tweet_text)

            if should_reply:
                # --- Reply generation strategy ---
                if use_curiosity and getattr(Config, "GROK_STYLE", True):
                    # Grok-style: direct, truth-seeking, bypasses curiosity fluff
                    user_msg = f'Reply to this tweet from someone who needs real help:\n\n"{tweet_text}"'
                    if reflection_summary:
                        user_msg += f"\n\nContext about their pain: {reflection_summary}"
                    generated_text = generate_contextual_reply(
                        tweet_text=tweet_text,
                        system_prompt=Config.GROK_SYSTEM_INSTRUCTION,
                        user_message=user_msg,
                    )
                    # Moderation guard — Grok path skips content_engine so validate inline
                    from content.content_moderator import ContentModerator
                    _grok_valid = (
                        generated_text
                        and len(generated_text.strip()) >= 8
                        and ContentModerator.validate(generated_text)[0]
                        and not ContentModerator.is_generic(generated_text)
                    )
                    if _grok_valid:
                        result = GenerationResult(
                            text=generated_text,
                            source="grok",
                            quality_score=0.85,
                        )
                        reply_type = "grok"
                    else:
                        log.warning("Grok reply failed moderation — falling back to curiosity")
                        result = content_engine.generate_curiosity_reply(tweet_text)
                        reply_type = "curiosity"
                elif use_curiosity:
                    result = content_engine.generate_curiosity_reply(tweet_text)
                    reply_type = "curiosity"
                else:
                    result = content_engine.generate_reply(tweet_text)
                    reply_type = "standard"

                reply = result.text

                if reply and len(reply) > 0:
                    success, reply_id = reply_tweet(page, tweet, reply)
                    if success:
                        rate_limiter.record_action("reply", success=True, target_id=reply_id)
                        actions_taken += 1
                        error_handler.reset_error_counter()
                        log.info(
                            f"✓ Replied [{reply_type}] "
                            f"(intent={intent_label}, quality={result.quality_score:.2f}) "
                            f"| Reply ID: {reply_id}"
                        )

                        # Feedback logged here (single source of truth)
                        try:
                            tweet_id = tweet.get_attribute("data-testid-tweet-id") or ""
                            feedback.log_reply(
                                tweet_id=tweet_id,
                                reply_id=reply_id or "",
                                user_handle="",
                                tweet_text=tweet_text,
                                reply_text=reply,
                                intent=intent_label,
                                reply_style=reply_type,
                                reflection_summary=reflection_summary,
                            )
                        except Exception as e:
                            log.warning(f"Feedback log failed: {e}")

                    else:
                        rate_limiter.record_action("reply", success=False)
        except Exception as e:
            should_retry, wait_seconds = error_handler.handle_error(e, "reply_tweet")
            rate_limiter.record_action("reply", success=False)
            errors_in_cycle += 1
            if should_retry and wait_seconds > 0:
                time.sleep(wait_seconds)

    return actions_taken, errors_in_cycle


def _attempt_follow(tweet, rate_limiter, error_handler, intent_label, feedback):
    """Attempt to follow a user. Returns (actions_taken, errors_in_cycle)"""
    actions_taken = 0
    errors_in_cycle = 0

    if rate_limiter.can_perform_action("follow")[0]:
        try:
            success, followed_handle = follow_user(tweet)
            if success:
                rate_limiter.record_action("follow", success=True, target_id=followed_handle)
                actions_taken += 1
                error_handler.reset_error_counter()
                log.info(f"✓ Followed @{followed_handle} (intent={intent_label})")

                # Feedback logged here (single source of truth)
                try:
                    tweet_id = tweet.get_attribute("data-testid-tweet-id") or ""
                    feedback.log_reply(
                        tweet_id=tweet_id,
                        reply_id="",
                        user_handle=followed_handle or "",
                        tweet_text="",
                        reply_text="",
                        intent=intent_label,
                        reply_style="follow",
                    )
                except Exception as e:
                    log.warning(f"Follow feedback log failed: {e}")
            else:
                rate_limiter.record_action("follow", success=False)
        except Exception as e:
            should_retry, wait_seconds = error_handler.handle_error(e, "follow_user")
            rate_limiter.record_action("follow", success=False)
            errors_in_cycle += 1
            if should_retry and wait_seconds > 0:
                time.sleep(wait_seconds)

    return actions_taken, errors_in_cycle


def _attempt_quote(tweet, page, rate_limiter, error_handler, content_engine):
    """Attempt to quote a tweet. Returns (actions_taken, errors_in_cycle)"""
    actions_taken = 0
    errors_in_cycle = 0

    if rate_limiter.can_perform_action("quote")[0]:
        try:
            tweet_text = get_tweet_text(tweet)
            should_reply, reason = should_reply_to_tweet_safe(tweet_text)

            if should_reply and len(tweet_text) > 20:
                commentary = content_engine.generate_quote_text(tweet_text)
                if commentary and len(commentary) > 5:
                    success = quote_tweet(page, tweet, commentary)
                    if success:
                        rate_limiter.record_action("quote", success=True, target_id=None)
                        actions_taken += 1
                        error_handler.reset_error_counter()
                        log.info(f"✓ Quote tweeted: {commentary[:50]}...")
                    else:
                        rate_limiter.record_action("quote", success=False)
        except Exception as e:
            should_retry, wait_seconds = error_handler.handle_error(e, "quote_tweet")
            rate_limiter.record_action("quote", success=False)
            errors_in_cycle += 1
            if should_retry and wait_seconds > 0:
                time.sleep(wait_seconds)

    return actions_taken, errors_in_cycle


def _process_single_tweet(tweet, page, rate_limiter, error_handler,
                           content_engine, search_keyword, feedback):
    """
    Process a single tweet for engagement actions.
    Returns (actions_taken, errors_in_cycle)
    """
    actions_taken = 0
    errors_in_cycle = 0

    was_high_intent = False

    try:
        metrics = get_tweet_metrics(tweet)
        engagement_score = score_tweet(metrics)
        tweet_text = get_tweet_text(tweet)
        intent = score_intent(tweet_text)
        intent_label = get_intent_label(intent)
        log.debug(f"Score: {engagement_score}, Intent: {intent_label}")

        # ===== CHANGE 8: LLM reflection on high-intent tweets =====
        reflection_summary = ""
        if intent == 3 and getattr(Config, "REFLECTION_ENABLED", True):
            try:
                llm_scorer = get_llm_intent_scorer()
                llm_result = llm_scorer.score(tweet_text)
                # Downgrade if the tweet is negated ("I WAS struggling but now I'm fine")
                if llm_result.get("negation_check"):
                    intent = min(intent, 2)
                    intent_label = get_intent_label(intent)
                    log.info(f"🔄 LLM downgraded intent (negation): {llm_result['reason']}")
                elif llm_result.get("intent_score", 3) < intent:
                    intent = llm_result["intent_score"]
                    intent_label = get_intent_label(intent)
                    log.info(f"🔄 LLM adjusted intent to {llm_result['level']}: {llm_result['reason']}")
                pain_points = llm_result.get("pain_points", [])
                reason = llm_result.get("reason", "")
                reflection_summary = (
                    f"Pain: {', '.join(pain_points)}. {reason}" if pain_points else reason
                )
                if reflection_summary:
                    log.info(f"🔍 Reflection: {reflection_summary}")
            except Exception as e:
                log.warning(f"LLM reflection skipped: {e}")

        # ===== INTENT-BASED ENGAGEMENT ROUTING =====
        should_try_reply = False
        use_curiosity = False

        if intent == 3:
            was_high_intent = True
            should_try_reply = True
            use_curiosity = True
            log.info(f"🎯 HIGH INTENT: {tweet_text[:60]}...")
        elif intent == 2:
            should_try_reply = random.random() < 0.30
        else:
            should_try_reply = random.random() < Config.REPLY_PROBABILITY

        if should_try_reply:
            actions, errors = _attempt_reply(
                tweet, page, rate_limiter, error_handler, content_engine,
                search_keyword, tweet_text, intent, intent_label,
                use_curiosity, feedback, reflection_summary,
            )
            actions_taken += actions
            errors_in_cycle += errors

        # FOLLOW (higher chance for high-intent users)
        follow_chance = Config.FOLLOW_PROBABILITY
        if intent == 3:
            follow_chance = 0.60
        elif intent == 2:
            follow_chance = 0.30

        if random.random() < follow_chance:
            actions, errors = _attempt_follow(
                tweet, rate_limiter, error_handler, intent_label, feedback
            )
            actions_taken += actions
            errors_in_cycle += errors

        # QUOTE TWEET (10% chance)
        if random.random() < 0.10:
            actions, errors = _attempt_quote(
                tweet, page, rate_limiter, error_handler, content_engine
            )
            actions_taken += actions
            errors_in_cycle += errors

        time.sleep(random.uniform(1, 3))

    except Exception as e:
        log.error(f"Error processing tweet: {e}")
        errors_in_cycle += 1

    return actions_taken, errors_in_cycle, was_high_intent


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
