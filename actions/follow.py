"""Follow users with tracking for unfollow strategy."""

import re
import time
from utils.human_behavior import random_delay
from utils.selectors import FOLLOW_BUTTON
from database import save_follow
from logger_setup import log

# NEW: Feedback tracking integration
from feedback import FeedbackTracker


def _extract_user_info(tweet) -> dict:
    """Extract user ID and username from tweet element."""
    info = {"user_id": None, "username": ""}
    try:
        # Extract username from profile link
        links = tweet.locator("a[href*='/']").all()
        for link in links:
            href = link.get_attribute("href")
            if href and re.match(r"^/[A-Za-z0-9_]+$", href):
                info["username"] = href.strip("/")
                info["user_id"] = info["username"]  # Use username as ID for now
                break
    except Exception:
        pass
    return info


def follow_user(tweet, timeout=5000):
    """
    Follow a user from a tweet element.
    Returns (success: bool, user_handle: str or None) for feedback tracking.
    """
    user_handle = None
    try:
        follow_btn = tweet.locator(FOLLOW_BUTTON).first

        if not follow_btn or not follow_btn.is_visible(timeout=1000):
            follow_btn = tweet.locator("div[role='button']:has-text('Follow')").first

        if not follow_btn or not follow_btn.is_visible(timeout=1000):
            log.debug("Follow button not found or not visible")
            return False, None

        follow_btn.scroll_into_view_if_needed()
        time.sleep(0.3)

        try:
            follow_btn.click(timeout=timeout)
        except Exception:
            follow_btn.click(timeout=timeout, force=True)

        # Extract user info for tracking
        user_info = _extract_user_info(tweet)
        user_handle = user_info["username"]

        if user_info["user_id"]:
            save_follow(user_info["user_id"], user_info["username"])
            log.debug(f"Tracked follow: @{user_info['username']}")

        # NEW: Log follow to feedback tracker if we have context
        # (This assumes the caller can pass tweet_id later; for now we log basic info)
        try:
            feedback = FeedbackTracker()
            tweet_id = tweet.get_attribute("data-testid-tweet-id") or ""
            feedback.log_reply(  # reusing log_reply as a general action log - can rename later
                tweet_id=tweet_id,
                reply_id="",  # no reply here
                user_handle=user_handle or "",
                tweet_text="",  # optional: pass from caller
                reply_text="",  # not applicable
                intent="follow_action",  # placeholder
                reply_style="follow"
            )
            feedback.close()
        except Exception as e:
            log.warning(f"Follow feedback logging failed: {e}")

        random_delay()
        return True, user_handle

    except Exception as e:
        log.warning(f"Failed to follow: {e}")
        return False, user_handle