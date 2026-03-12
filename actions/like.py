import time
from utils.human_behavior import random_delay, random_position
from utils.selectors import LIKE_BUTTON
from logger_setup import log


def like_tweet(tweet, page=None, timeout=5000):
    """
    Like a tweet with human-like behavior
    
    Args:
        tweet: Tweet element (article)
        page: Playwright page object (optional, for debugging)
        timeout: Action timeout
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Find like button within tweet
        like_btn = tweet.locator(LIKE_BUTTON).first
        
        if not like_btn:
            log.warning("Like button not found")
            return False
        
        # Check if button is visible
        if not like_btn.is_visible(timeout=1000):
            log.warning("Like button not visible")
            return False
        
        # Scroll into view if needed
        like_btn.scroll_into_view_if_needed()
        time.sleep(0.3)
        
        # Click with slight delay (human-like)
        try:
            like_btn.click(timeout=timeout, force=False)
            log.debug("✓ Tweet liked")
            random_delay()  # Add delay after action
            return True
        except Exception as e:
            log.warning(f"Click failed: {e}, retrying with force...")
            # Force click if gentle click fails
            like_btn.click(timeout=timeout, force=True)
            log.debug("✓ Tweet liked (forced click)")
            random_delay()
            return True
    
    except Exception as e:
        log.warning(f"Failed to like tweet: {e}")
        return False


def unlike_tweet(tweet, page=None):
    """Unlike a tweet"""
    try:
        like_btn = tweet.locator(LIKE_BUTTON).first
        
        if like_btn.is_visible(timeout=1000):
            like_btn.scroll_into_view_if_needed()
            time.sleep(0.2)
            like_btn.click()
            log.debug("✓ Tweet unliked")
            random_delay()
            return True
    except Exception as e:
        log.warning(f"Failed to unlike tweet: {e}")
        return False


def check_if_liked(tweet):
    """Check if a tweet is already liked"""
    try:
        like_btn = tweet.locator(LIKE_BUTTON).first
        # Liked button typically has different styling/aria-pressed state
        aria_pressed = like_btn.get_attribute("aria-pressed")
        return aria_pressed == "true"
    except:
        return False
