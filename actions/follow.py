"""Follow users with tracking for unfollow strategy."""

import re
import time
from utils.human_behavior import random_delay
from utils.selectors import FOLLOW_BUTTON
from database import save_follow
from logger_setup import log


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
                info["user_id"] = info["username"]  # Use username as ID
                break
    except Exception:
        pass
    return info


def follow_user(tweet, timeout=5000):
    try:
        follow_btn = tweet.locator(FOLLOW_BUTTON).first

        if not follow_btn or not follow_btn.is_visible(timeout=1000):
            follow_btn = tweet.locator("div[role='button']:has-text('Follow')").first

        if not follow_btn or not follow_btn.is_visible(timeout=1000):
            return False

        follow_btn.scroll_into_view_if_needed()
        time.sleep(0.3)

        try:
            follow_btn.click(timeout=timeout)
        except Exception:
            follow_btn.click(timeout=timeout, force=True)

        # Track the follow for unfollow strategy
        user_info = _extract_user_info(tweet)
        if user_info["user_id"]:
            save_follow(user_info["user_id"], user_info["username"])
            log.debug(f"Tracked follow: @{user_info['username']}")

        random_delay()
        return True

    except Exception as e:
        log.warning(f"Failed to follow: {e}")
        return False
