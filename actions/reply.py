"""Reply to tweets with human-like typing."""

import time
from utils.human_behavior import random_delay, human_typing
from utils.selectors import REPLY_BUTTON, REPLY_TEXTAREA
from logger_setup import log

# NEW: Feedback tracking
from feedback import FeedbackTracker


def reply_tweet(page, tweet, text, timeout=10000):
    """
    Reply to a tweet with human-like typing.
    Returns (success: bool, reply_id: str or None) so we can track it.
    """
    try:
        reply_btn = tweet.locator(REPLY_BUTTON).first
        if not reply_btn:
            log.warning("Reply button not found")
            return False, None

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
            return False, None

        time.sleep(1)
        page.keyboard.press("Control+Enter")
        time.sleep(1.5)

        # NEW: Try to get the reply tweet ID (your own reply)
        reply_id = None
        try:
            # Wait a moment for the reply to appear
            time.sleep(2)
            # Find the last tweet in the thread or conversation - adjust selector as needed
            your_reply = page.locator("article[data-testid='tweet']").last
            reply_id = your_reply.get_attribute("data-testid-tweet-id") or ""
            if not reply_id:
                log.debug("Could not extract reply_id - will track without it")
        except Exception as e:
            log.debug(f"Failed to get reply_id: {e}")

        random_delay()
        success = True

        # NEW: Log to feedback tracker if we have basic info
        try:
            feedback = FeedbackTracker()
            # Get parent tweet ID and user handle (you may need to pass these from caller)
            # For now we use placeholders - improve later when caller passes them
            tweet_id = tweet.get_attribute("data-testid-tweet-id") or ""
            user_handle = tweet.locator("a[href*='/status/']").first.get_attribute("href").split("/")[1] if tweet else ""
            feedback.log_reply(
                tweet_id=tweet_id,
                reply_id=reply_id or "",
                user_handle=user_handle,
                tweet_text="",          # Pass real text from caller if possible
                reply_text=text,
                intent="unknown",       # Pass real intent from caller
                reply_style="default"   # Pass real style from caller
            )
            feedback.close()
        except Exception as e:
            log.warning(f"Feedback logging failed: {e}")

        return success, reply_id

    except Exception as e:
        log.warning(f"Failed to reply: {e}")
        return False, None