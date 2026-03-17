"""
Quote tweet action - retweet with commentary.

Quote tweets are high-value engagement: they boost visibility for both you
and the original author, and your commentary gets seen by both audiences.
"""

import re
import time
from utils.human_behavior import random_delay, human_typing
from utils.selectors import RETWEET_BUTTON
from logger_setup import log


def _extract_tweet_url(tweet) -> str:
    """Extract the tweet URL from a tweet element."""
    try:
        links = tweet.locator('a[href*="/status/"]').all()
        for link in links:
            href = link.get_attribute("href")
            if href and "/status/" in href:
                if not href.startswith("http"):
                    href = "https://x.com" + href
                return href
    except Exception:
        pass
    return ""


def quote_tweet(page, tweet, text, timeout=10000):
    """
    Quote tweet with commentary.

    Args:
        page: Playwright page object
        tweet: Tweet element (article)
        text: Quote commentary text
        timeout: Action timeout

    Returns:
        bool: True if successful
    """
    try:
        # Click the retweet button to open the menu
        retweet_btn = tweet.locator(RETWEET_BUTTON).first
        if not retweet_btn or not retweet_btn.is_visible(timeout=2000):
            log.warning("Retweet button not found")
            return False

        retweet_btn.scroll_into_view_if_needed()
        time.sleep(0.5)
        retweet_btn.click(timeout=timeout)
        time.sleep(1)

        # Click "Quote" from the dropdown menu
        quote_option = page.locator("[data-testid='Dropdown'] a:has-text('Quote')").first
        if not quote_option:
            # Try alternative selector
            quote_option = page.locator("a[href*='/compose/post']:has-text('Quote')").first
        if not quote_option:
            # Try yet another pattern
            quote_option = page.locator("[role='menuitem']:has-text('Quote')").first

        if not quote_option or not quote_option.is_visible(timeout=3000):
            log.warning("Quote option not found in retweet menu")
            # Close the menu
            try:
                page.press("body", "Escape")
            except Exception:
                pass
            return False

        quote_option.click(timeout=timeout)
        time.sleep(2)

        # Find the compose textarea
        textarea = page.locator("[data-testid='tweetTextarea_0']").first
        if not textarea:
            textarea = page.locator("div[role='textbox']").first

        if not textarea or not textarea.is_visible(timeout=5000):
            log.warning("Quote compose textarea not found")
            return False

        # Type the quote commentary
        human_typing(textarea, text, wpm=60)
        time.sleep(1)

        # Click the post button
        post_btn = page.locator("[data-testid='tweetButton']").first
        if not post_btn or not post_btn.is_visible(timeout=3000):
            log.warning("Post button not found for quote tweet")
            return False

        post_btn.click(timeout=5000)
        time.sleep(2)

        log.info(f"✓ Quote tweet posted: {text[:50]}...")
        random_delay()
        return True

    except Exception as e:
        log.warning(f"Failed to quote tweet: {e}")
        # Try to close any open dialogs
        try:
            page.press("body", "Escape")
        except Exception:
            pass
        return False
