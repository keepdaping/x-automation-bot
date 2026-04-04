"""
Quote tweet attempt logic — generation, posting, and rate limiting.
"""

import time

from actions.quote_tweet import quote_tweet
from utils.language_handler import should_reply_to_tweet_safe
from utils.tweet_text import get_tweet_text
from logger_setup import log


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
