"""
Main engagement engine with rate limiting and error recovery.

This module orchestrates all bot actions (like, reply, follow) with:
- Rate limiting to prevent detection
- Error recovery with exponential backoff
- Structured logging for debugging
- Graceful degradation
"""

import random
import time
from typing import Optional

from search.search_tweets import search_tweets
from actions.like import like_tweet
from actions.reply import reply_tweet
from actions.follow import follow_user

from core.generator import generate_contextual_reply
from core.rate_limiter import get_rate_limiter
from core.error_handler import get_error_handler
from utils.tweet_metrics import get_tweet_metrics
from utils.engagement_score import score_tweet
from utils.tweet_text import get_tweet_text
from utils.language_handler import should_reply_to_tweet_safe
from logger_setup import log


def run_engagement(page, config=None):
    """
    Run one cycle of engagement with all safety checks and rate limiting.
    
    This is the main bot function that:
    1. Searches for tweets
    2. Scores them
    3. Performs actions (like, reply, follow) with rate limiting
    4. Handles errors gracefully
    
    Args:
        page: Playwright page object
        config: Config object (optional, uses global if not provided)
    """
    
    try:
        # Get global singletons
        rate_limiter = get_rate_limiter()
        error_handler = get_error_handler()
        
        # Check if in detection cooldown
        if error_handler.is_in_detection_cooldown():
            log.critical("⏸️  Bot is in detection cooldown - skipping engagement")
            return False
        
        log.info("=" * 70)
        log.info("ENGAGEMENT CYCLE STARTING")
        log.info("=" * 70)
        
        # Get remaining actions for today
        remaining = rate_limiter.get_remaining_actions()
        log.info(f"Daily limits remaining: {remaining}")
        
        # If no actions allowed today, skip
        total_remaining = sum(remaining.values())
        if total_remaining == 0:
            log.info("❌ Daily action limits reached - skipping cycle")
            return False
        
        # Search for tweets
        log.info("Searching for relevant tweets...")
        try:
            tweets = search_tweets(page, random.choice(config.SEARCH_KEYWORDS if config else ["AI"]))
        except Exception as e:
            error_handler.handle_error(e, "search_tweets")
            return False
        
        if not tweets:
            log.warning("No tweets found in search")
            return False
        
        log.info(f"Found {len(tweets)} tweets")
        
        # Process each tweet
        actions_taken = 0
        errors_in_cycle = 0
        
        for idx, tweet in enumerate(tweets, 1):
            log.debug(f"\n--- Processing tweet {idx}/{len(tweets)} ---")
            
            try:
                # Get tweet metrics
                metrics = get_tweet_metrics(tweet)
                score = score_tweet(metrics)
                log.debug(f"Metrics: {metrics}, Score: {score}")
                
                # LIKE ACTION
                if random.random() < 0.6:  # 60% chance
                    if rate_limiter.can_perform_action("like")[0]:
                        try:
                            log.debug("Attempting like...")
                            success = like_tweet(tweet)
                            
                            if success:
                                rate_limiter.record_action("like", success=True, target_id=None)
                                actions_taken += 1
                                error_handler.reset_error_counter()
                                log.info("✓ Liked tweet")
                            else:
                                rate_limiter.record_action("like", success=False)
                                log.debug("✗ Like failed")
                        
                        except Exception as e:
                            should_retry, wait_seconds = error_handler.handle_error(e, "like_tweet")
                            rate_limiter.record_action("like", success=False)
                            errors_in_cycle += 1
                            
                            # If error handler says to retry, sleep for the backoff time
                            if should_retry and wait_seconds > 0:
                                log.warning(f"Backoff: waiting {wait_seconds}s before retry...")
                                time.sleep(wait_seconds)
                    else:
                        reason = rate_limiter.can_perform_action("like")[1]
                        log.debug(f"Like skipped: {reason}")
                
                # REPLY ACTION
                if random.random() < 0.25:  # 25% chance
                    if rate_limiter.can_perform_action("reply")[0]:
                        try:
                            log.debug("Attempting reply...")
                            tweet_text = get_tweet_text(tweet)
                            
                            # Check language
                            should_reply, reason = should_reply_to_tweet_safe(tweet_text)
                            
                            if not should_reply:
                                log.debug(f"Reply skipped: {reason}")
                            else:
                                # Generate reply
                                reply = generate_contextual_reply(tweet_text)
                                
                                if reply and len(reply) > 0:
                                    success = reply_tweet(page, tweet, reply)
                                    
                                    if success:
                                        rate_limiter.record_action("reply", success=True, target_id=None)
                                        actions_taken += 1
                                        error_handler.reset_error_counter()
                                        log.info(f"✓ Replied to tweet")
                                    else:
                                        rate_limiter.record_action("reply", success=False)
                                        log.debug("✗ Reply failed")
                                else:
                                    log.debug("Reply generation failed or empty")
                        
                        except Exception as e:
                            should_retry, wait_seconds = error_handler.handle_error(e, "reply_tweet")
                            rate_limiter.record_action("reply", success=False)
                            errors_in_cycle += 1
                            
                            # If error handler says to retry, sleep for the backoff time
                            if should_retry and wait_seconds > 0:
                                log.warning(f"Backoff: waiting {wait_seconds}s before retry...")
                                time.sleep(wait_seconds)
                    else:
                        reason = rate_limiter.can_perform_action("reply")[1]
                        log.debug(f"Reply skipped: {reason}")
                
                # FOLLOW ACTION
                if random.random() < 0.15:  # 15% chance
                    if rate_limiter.can_perform_action("follow")[0]:
                        try:
                            log.debug("Attempting follow...")
                            success = follow_user(tweet)
                            
                            if success:
                                rate_limiter.record_action("follow", success=True, target_id=None)
                                actions_taken += 1
                                error_handler.reset_error_counter()
                                log.info("✓ Followed user")
                            else:
                                rate_limiter.record_action("follow", success=False)
                                log.debug("✗ Follow failed")
                        
                        except Exception as e:
                            should_retry, wait_seconds = error_handler.handle_error(e, "follow_user")
                            rate_limiter.record_action("follow", success=False)
                            errors_in_cycle += 1
                            
                            # If error handler says to retry, sleep for the backoff time
                            if should_retry and wait_seconds > 0:
                                log.warning(f"Backoff: waiting {wait_seconds}s before retry...")
                                time.sleep(wait_seconds)
                    else:
                        reason = rate_limiter.can_perform_action("follow")[1]
                        log.debug(f"Follow skipped: {reason}")
                
                # Small delay between tweets in batch
                time.sleep(random.uniform(1, 3))
            
            except Exception as e:
                log.error(f"Unexpected error processing tweet {idx}: {e}")
                errors_in_cycle += 1
                # Continue to next tweet
                continue
        
        # Log cycle summary
        log.info("\n" + "=" * 70)
        log.info(f"CYCLE COMPLETE: {actions_taken} actions, {errors_in_cycle} errors")
        log.info("=" * 70 + "\n")
        
        return actions_taken > 0
    
    except Exception as e:
        log.error(f"Fatal error in engagement cycle: {e}")
        error_handler.handle_error(e, "run_engagement_main")
        return False