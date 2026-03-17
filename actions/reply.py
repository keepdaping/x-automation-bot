"""Reply to tweets with human-like typing."""

import time
from utils.human_behavior import random_delay, human_typing
from utils.selectors import REPLY_BUTTON, REPLY_TEXTAREA
from logger_setup import log


def reply_tweet(page, tweet, text, timeout=10000):
    try:
        reply_btn = tweet.locator(REPLY_BUTTON).first
        if not reply_btn:
            return False

        reply_btn.scroll_into_view_if_needed()
        time.sleep(0.5)

        try:
            reply_btn.click(timeout=timeout)
        except Exception:
            reply_btn.click(timeout=timeout, force=True)

        page.wait_for_selector(REPLY_TEXTAREA, timeout=timeout)
        time.sleep(1)

        text_area = page.locator(REPLY_TEXTAREA).first
        if not text_area:
            text_area = page.locator("div[role='textbox']").first

        if text_area:
            human_typing(text_area, text, wpm=60)
        else:
            log.error("Could not find reply textarea")
            return False

        time.sleep(1)
        page.keyboard.press("Control+Enter")
        time.sleep(1.5)

        random_delay()
        return True

    except Exception as e:
        log.warning(f"Failed to reply: {e}")
        return False
