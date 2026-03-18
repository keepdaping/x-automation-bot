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
from database import log_conversion, init_conversion_tracking
from logger_setup import log
from config import Config


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


def run_engagement(page, config=None, keyword=None):
    """
    Run one cycle of engagement with all safety checks.
    
    FIXED: This function is now independent of DAILY_TWEET_ENABLED.
    """
    try:
        rate_limiter = get_rate_limiter()
        error_handler = get_error_handler()
        content_engine = get_content_engine()

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

        # Search for tweets — mix topic + intent keywords
        # 40% chance to use pain-based intent keywords for lead discovery
        intent_keywords = getattr(Config, 'INTENT_KEYWORDS', [])
        if intent_keywords and random.random() < 0.40:
            search_keyword = keyword or random.choice(intent_keywords)
            log.info(f"Using INTENT keyword: {search_keyword}")
        else:
            search_keyword = keyword or random.choice(Config.SEARCH_KEYWORDS)
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

            try:
                metrics = get_tweet_metrics(tweet)
                engagement_score = score_tweet(metrics)
                tweet_text = get_tweet_text(tweet)
                intent = score_intent(tweet_text)
                intent_label = get_intent_label(intent)
                log.debug(f"Score: {engagement_score}, Intent: {intent_label}")

                # ===== INTENT-BASED ENGAGEMENT ROUTING =====
                # High (3)  → always reply (curiosity prompt) + like + follow
                # Medium (2) → 30% reply (standard) + like
                # Low (1)   → like only

                # LIKE (always, all intent levels)
                if random.random() < Config.LIKE_PROBABILITY:
                    if rate_limiter.can_perform_action("like")[0]:
                        try:
                            success = like_tweet(tweet)
                            if success:
                                rate_limiter.record_action("like", success=True, target_id=None)
                                actions_taken += 1
                                error_handler.reset_error_counter()
                                log.info("✓ Liked tweet")
                            else:
                                rate_limiter.record_action("like", success=False)
                        except Exception as e:
                            should_retry, wait_seconds = error_handler.handle_error(e, "like_tweet")
                            rate_limiter.record_action("like", success=False)
                            errors_in_cycle += 1
                            if should_retry and wait_seconds > 0:
                                time.sleep(wait_seconds)

                # REPLY (intent-based routing)
                should_try_reply = False
                use_curiosity = False

                if intent == 3:
                    # High intent → always try to reply with curiosity prompt
                    should_try_reply = True
                    use_curiosity = True
                    log.info(f"🎯 HIGH INTENT: {tweet_text[:60]}...")
                elif intent == 2:
                    # Medium intent → 30% chance standard reply
                    should_try_reply = random.random() < 0.30
                else:
                    # Low intent → use original probability
                    should_try_reply = random.random() < Config.REPLY_PROBABILITY

                if should_try_reply and rate_limiter.can_perform_action("reply")[0]:
                    try:
                        should_reply, reason = should_reply_to_tweet_safe(tweet_text)

                        if should_reply:
                            if use_curiosity:
                                result = content_engine.generate_curiosity_reply(tweet_text)
                            else:
                                result = content_engine.generate_reply(tweet_text)

                            reply = result.text

                            if reply and len(reply) > 0:
                                success = reply_tweet(page, tweet, reply)
                                if success:
                                    rate_limiter.record_action("reply", success=True, target_id=None)
                                    actions_taken += 1
                                    error_handler.reset_error_counter()
                                    reply_type = "curiosity" if use_curiosity else "standard"
                                    log.info(f"✓ Replied [{reply_type}] (intent={intent_label}, quality={result.quality_score:.2f})")

                                    # Log for conversion tracking
                                    if intent >= 2:
                                        try:
                                            log_conversion(
                                                tweet_text=tweet_text,
                                                tweet_url="",
                                                reply_text=reply,
                                                keyword=search_keyword,
                                                intent_score=intent,
                                                intent_label=intent_label,
                                                reply_type=reply_type,
                                            )
                                        except Exception:
                                            pass
                                else:
                                    rate_limiter.record_action("reply", success=False)
                    except Exception as e:
                        should_retry, wait_seconds = error_handler.handle_error(e, "reply_tweet")
                        rate_limiter.record_action("reply", success=False)
                        errors_in_cycle += 1
                        if should_retry and wait_seconds > 0:
                            time.sleep(wait_seconds)

                # FOLLOW (higher chance for high-intent users)
                follow_chance = Config.FOLLOW_PROBABILITY
                if intent == 3:
                    follow_chance = 0.60  # 60% for high-intent
                elif intent == 2:
                    follow_chance = 0.30  # 30% for medium-intent

                if random.random() < follow_chance:
                    if rate_limiter.can_perform_action("follow")[0]:
                        try:
                            success = follow_user(tweet)
                            if success:
                                rate_limiter.record_action("follow", success=True, target_id=None)
                                actions_taken += 1
                                error_handler.reset_error_counter()
                                log.info(f"✓ Followed user (intent={intent_label})")
                            else:
                                rate_limiter.record_action("follow", success=False)
                        except Exception as e:
                            should_retry, wait_seconds = error_handler.handle_error(e, "follow_user")
                            rate_limiter.record_action("follow", success=False)
                            errors_in_cycle += 1
                            if should_retry and wait_seconds > 0:
                                time.sleep(wait_seconds)

                # QUOTE TWEET (10% chance — high-value but use sparingly)
                if random.random() < 0.10:
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

                time.sleep(random.uniform(1, 3))

            except Exception as e:
                log.error(f"Error processing tweet {idx}: {e}")
                errors_in_cycle += 1
                continue

        log.info(f"\nCYCLE COMPLETE: {actions_taken} actions, {errors_in_cycle} errors\n")
        return actions_taken > 0

    except Exception as e:
        log.error(f"Fatal error in engagement cycle: {e}")
        error_handler.handle_error(e, "run_engagement_main")
        return False
