"""
Follow attempt logic — action, rate limiting, and feedback logging.
"""

import time

from actions.follow import follow_user
from logger_setup import log


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
