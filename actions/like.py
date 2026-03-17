"""Like tweets with human-like behavior."""

import time
from utils.human_behavior import random_delay
from utils.selectors import LIKE_BUTTON
from logger_setup import log


def like_tweet(tweet, page=None, timeout=5000):
    try:
        try:
            if not tweet.is_visible(timeout=500):
                return False
        except Exception:
            return False

        like_btn = tweet.locator(LIKE_BUTTON).first
        if not like_btn:
            return False

        try:
            if not like_btn.is_visible(timeout=1000):
                return False
        except Exception:
            return False

        try:
            like_btn.scroll_into_view_if_needed(timeout=2000)
            time.sleep(0.3)
        except Exception:
            pass

        try:
            like_btn.click(timeout=timeout, force=True)
            random_delay()
            return True
        except Exception:
            like_btn.click(timeout=timeout, force=True)
            random_delay()
            return True

    except Exception as e:
        log.warning(f"Failed to like: {e}")
        return False


def check_if_liked(tweet):
    try:
        like_btn = tweet.locator(LIKE_BUTTON).first
        return like_btn.get_attribute("aria-pressed") == "true"
    except Exception:
        return False
