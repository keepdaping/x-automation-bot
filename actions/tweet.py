"""
Post a tweet with proper error handling.
REWRITTEN: Added try/except, wait confirmations, timeout fallbacks.
"""

import time
from utils.human_behavior import random_delay, human_typing
from logger_setup import log


def post_tweet(page, text, timeout=15000):
    """
    Post a tweet with error handling and confirmation.
    
    Args:
        page: Playwright page object
        text: Tweet text to post
        timeout: Max wait time in ms
    
    Returns:
        bool: True if tweet was posted successfully
    """
    try:
        # Navigate to compose
        page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=timeout)
        time.sleep(2)

        # Wait for textarea
        textarea = page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=timeout)
        if not textarea:
            log.error("Tweet textarea not found")
            return False

        # Type with human-like speed
        human_typing(textarea, text, wpm=60)
        time.sleep(1)

        # Find and click post button
        post_btn = page.locator('[data-testid="tweetButton"]').first
        if not post_btn or not post_btn.is_visible(timeout=3000):
            log.error("Post button not found or not visible")
            return False

        post_btn.click(timeout=5000)
        time.sleep(2)

        # Verify: check we're no longer on compose page or toast appeared
        try:
            # If textarea is gone, tweet was posted
            page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=3000)
            # Still on compose page = might have failed
            log.warning("Still on compose page after posting - tweet may not have sent")
            return False
        except Exception:
            # Textarea gone = success
            pass

        log.info(f"✓ Tweet posted: {text[:50]}...")
        random_delay()
        return True

    except Exception as e:
        log.error(f"Failed to post tweet: {e}")
        return False
