"""
Main engagement engine with rate limiting and error recovery.
FIXED: Engagement loop no longer nested under DAILY_TWEET_ENABLED check.
ADDED: Unfollow strategy integration.
"""



import random
import time
from typing import Optional

from utils.human_behavior import natural_scroll
from search.search_tweets import search_tweets
from actions.like import like_tweet
from actions.reply import reply_tweet
from actions.follow import follow_user
from actions.quote_tweet import quote_tweet
from actions.unfollow import run_unfollow_cycle
from utils.selectors import TWEET_ARTICLE, TWEET_TIMESTAMP

from content.engine import get_content_engine
from core.rate_limiter import get_rate_limiter
from core.error_handler import get_error_handler
from utils.tweet_metrics import get_tweet_metrics
from utils.engagement_score import score_tweet
from utils.tweet_text import get_tweet_text
from utils.language_handler import should_reply_to_tweet_safe

from utils.intent_scorer import score_intent, get_intent_label
from utils.llm_intent_scorer import get_llm_intent_scorer  # NEW

from database import log_conversion, init_conversion_tracking
from logger_setup import log
from config import Config

# NEW: Feedback tracking
from feedback import FeedbackTracker


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


def _attempt_reply(tweet, page, rate_limiter, error_handler, content_engine, search_keyword, tweet_text, intent, intent_label, use_curiosity, feedback):
    """Attempt to reply to a tweet. Returns (actions_taken, errors_in_cycle)"""
    actions_taken = 0
    errors_in_cycle = 0

    if rate_limiter.can_perform_action("reply")[0]:
        try:
            should_reply, reason = should_reply_to_tweet_safe(tweet_text)

            if should_reply:
                if use_curiosity:
                    result = content_engine.generate_curiosity_reply(tweet_text)
                else:
                    result = content_engine.generate_reply(tweet_text)

                reply = result.text

                if reply and len(reply) > 0:
                    success, reply_id = reply_tweet(page, tweet, reply)
                    if success:
                        rate_limiter.record_action("reply", success=True, target_id=reply_id)
                        actions_taken += 1
                        error_handler.reset_error_counter()
                        reply_type = "curiosity" if use_curiosity else "standard"
                        log.info(f"✓ Replied [{reply_type}] (intent={intent_label}, quality={result.quality_score:.2f}) | Reply ID: {reply_id}")

                        # === FEEDBACK LOGGING ===
                        try:
                            tweet_id = tweet.get_attribute("data-testid-tweet-id") or ""
                            user_handle = ""  # extracted in reply_tweet if needed
                            feedback.log_reply(
                                tweet_id=tweet_id,
                                reply_id=reply_id or "",
                                user_handle=user_handle,
                                tweet_text=tweet_text,
                                reply_text=reply,
                                intent=intent_label,
                                reply_style=reply_type
                            )
                        except Exception as e:
                            log.warning(f"Feedback log failed: {e}")

                        # Log for conversion tracking
                                # === PHASE 1: LLM INTENT (safe toggle) ===
                        if Config.INTENT_MODE == "llm" or Config.INTENT_MODE == "hybrid":
                            llm_result = get_llm_intent_scorer().score(tweet_text)
                            intent = llm_result["intent_score"]
                            intent_label = llm_result["level"]
                            log.debug(f"LLM intent used: {intent_label}")
                        else:
                            intent = score_intent(tweet_text)
                            intent_label = get_intent_label(intent)
                            
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

                # === FEEDBACK LOGGING ===
                try:
                    tweet_id = tweet.get_attribute("data-testid-tweet-id") or ""
                    feedback.log_reply(
                        tweet_id=tweet_id,
                        reply_id="",  # not a reply
                        user_handle=followed_handle,
                        tweet_text="",
                        reply_text="",
                        intent=intent_label,
                        reply_style="follow"
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


def _process_single_tweet(tweet, page, rate_limiter, error_handler, content_engine, search_keyword, feedback):
    """
    Process a single tweet for engagement actions.
    Returns (actions_taken, errors_in_cycle)
    """
    actions_taken = 0
    errors_in_cycle = 0

    try:
        metrics = get_tweet_metrics(tweet)
        engagement_score = score_tweet(metrics)
        tweet_text = get_tweet_text(tweet)
        intent = score_intent(tweet_text)
        intent_label = get_intent_label(intent)
        log.debug(f"Score: {engagement_score}, Intent: {intent_label}")

        # ===== INTENT-BASED ENGAGEMENT ROUTING =====
        should_try_reply = False
        use_curiosity = False

        if intent == 3:
            should_try_reply = True
            use_curiosity = True
            log.info(f"🎯 HIGH INTENT: {tweet_text[:60]}...")
        elif intent == 2:
            should_try_reply = random.random() < 0.30
        else:
            should_try_reply = random.random() < Config.REPLY_PROBABILITY

        if should_try_reply:
            actions, errors = _attempt_reply(tweet, page, rate_limiter, error_handler, content_engine, search_keyword, tweet_text, intent, intent_label, use_curiosity, feedback)
            actions_taken += actions
            errors_in_cycle += errors

        # FOLLOW (higher chance for high-intent users)
        follow_chance = Config.FOLLOW_PROBABILITY
        if intent == 3:
            follow_chance = 0.60
        elif intent == 2:
            follow_chance = 0.30

        if random.random() < follow_chance:
            actions, errors = _attempt_follow(tweet, rate_limiter, error_handler, intent_label, feedback)
            actions_taken += actions
            errors_in_cycle += errors

        # QUOTE TWEET (10% chance)
        if random.random() < 0.10:
            actions, errors = _attempt_quote(tweet, page, rate_limiter, error_handler, content_engine)
            actions_taken += actions
            errors_in_cycle += errors

        time.sleep(random.uniform(1, 3))

    except Exception as e:
        log.error(f"Error processing tweet: {e}")
        errors_in_cycle += 1

    return actions_taken, errors_in_cycle


def _select_search_keyword(keyword):
    """Select a search keyword, preferring intent keywords occasionally."""
    intent_keywords = getattr(Config, 'INTENT_KEYWORDS', [])
    if intent_keywords and random.random() < 0.40:
        search_keyword = keyword or random.choice(intent_keywords)
        log.info(f"Using INTENT keyword: {search_keyword}")
    else:
        search_keyword = keyword or random.choice(Config.SEARCH_KEYWORDS)
    return search_keyword


def run_engagement(page, config=None, keyword=None, feedback_tracker=None):
    """
    Run one cycle of engagement with all safety checks.
    
    FIXED: This function is now independent of DAILY_TWEET_ENABLED.
    """
    try:
        rate_limiter = get_rate_limiter()
        error_handler = get_error_handler()
        content_engine = get_content_engine()

        # NEW: Feedback tracker
        feedback = feedback_tracker if feedback_tracker else FeedbackTracker()

        # Ensure conversion tracking table exists
        init_conversion_tracking()

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

        # Search for tweets
        search_keyword = _select_search_keyword(keyword)
        log.info(f"Searching for tweets (keyword: {search_keyword})...")
        try:
            tweets = search_tweets(page, search_keyword)
        except Exception as e:
            error_handler.handle_error(e, "search_tweets")
            return False

        if not tweets:
            log.warning("No tweets found")
            return False

        log.info(f"Found {len(tweets)} tweets")

        actions_taken = 0
        errors_in_cycle = 0

        for idx, tweet in enumerate(tweets, 1):
            log.debug(f"\n--- Processing tweet {idx}/{len(tweets)} ---")
            actions, errors = _process_single_tweet(tweet, page, rate_limiter, error_handler, content_engine, search_keyword, feedback)
            actions_taken += actions
            errors_in_cycle += errors

        feedback.close()  # clean up
        log.info(f"\nCYCLE COMPLETE: {actions_taken} actions, {errors_in_cycle} errors\n")
        return actions_taken > 0

    except Exception as e:
        log.error(f"Fatal error in engagement cycle: {e}")
        error_handler.handle_error(e, "run_engagement_main")
        return False