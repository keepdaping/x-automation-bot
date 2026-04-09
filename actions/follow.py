"""Follow users with tracking for unfollow strategy."""

import re
import time
from utils.human_behavior import random_delay
from utils.selectors import FOLLOW_BUTTON
from database import save_follow
from logger_setup import log

# Known non-user URL paths that the regex must not match as usernames
_NON_USER_PATHS = {
    "home", "explore", "messages", "notifications", "settings",
    "i", "search", "compose", "following", "followers", "bookmarks",
    "lists", "topics", "connect_people", "who_to_follow",
}


def _extract_user_info(tweet) -> dict:
    """Extract user ID and username from tweet element."""
    info = {"user_id": None, "username": ""}
    try:
        # Extract username from profile link
        links = tweet.locator("a[href*='/']").all()
        for link in links:
            href = link.get_attribute("href")
            # Twitter usernames: 1–15 alphanumeric/underscore chars, single path segment
            if href and re.match(r"^/[A-Za-z0-9_]{1,15}$", href):
                candidate = href.strip("/")
                if candidate not in _NON_USER_PATHS:
                    info["username"] = candidate
                    info["user_id"] = candidate  # Use username as ID for now
                    break
    except Exception:
        pass
    return info


def follow_user(tweet, timeout=5000):
    """
    Follow a user from a tweet element.
    Returns (success: bool, user_handle: str or None) for feedback tracking.

    Two-phase design:
      Phase 1 — browser action (click).  Any failure here → return (False, None).
      Phase 2 — DB logging.  Runs in its own try/except so a save failure never
                blocks the True return or masks the fact that the follow occurred.
    """
    user_handle = None

    # ── Phase 1: browser action ───────────────────────────────────────────────
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

    except Exception as e:
        log.warning(f"Failed to follow (browser action): {e}")
        return False, user_handle

    # ── Phase 2: DB logging (isolated — never prevents True return) ───────────
    try:
        user_info = _extract_user_info(tweet)
        user_handle = user_info["username"]

        follow_id = user_info["user_id"] or user_info["username"]
        if not follow_id:
            follow_id = f"unknown_{int(time.time())}"

        save_follow(follow_id, user_info["username"] or "")
        log.info(f"FOLLOW SAVED TO DB: @{user_info['username'] or follow_id}")

    except Exception as save_err:
        log.error(f"Follow executed on X but DB save failed: {save_err}")

    random_delay()
    return True, user_handle