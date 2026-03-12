import time
from utils.human_behavior import random_delay
from utils.selectors import FOLLOW_BUTTON
from logger_setup import log


def follow_user(tweet, timeout=5000):
    """
    Follow a user by clicking follow button in tweet
    
    Args:
        tweet: Tweet element (article)
        timeout: Action timeout
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Find follow button in tweet's user section
        follow_btn = tweet.locator(FOLLOW_BUTTON).first
        
        if not follow_btn:
            log.warning("Follow button not found")
            return False
        
        # Check visibility
        if not follow_btn.is_visible(timeout=1000):
            log.warning("Follow button not visible")
            return False
        
        # Scroll into view
        follow_btn.scroll_into_view_if_needed()
        time.sleep(0.3)
        
        # Click follow
        try:
            follow_btn.click(timeout=timeout)
        except:
            log.warning("Gentle click failed, force clicking...")
            follow_btn.click(timeout=timeout, force=True)
        
        log.debug("✓ User followed")
        random_delay()
        return True
    
    except Exception as e:
        log.warning(f"Failed to follow user: {e}")
        return False


def unfollow_user(tweet):
    """
    Unfollow a user
    """
    try:
        follow_btn = tweet.locator(FOLLOW_BUTTON).first
        
        if follow_btn and follow_btn.is_visible(timeout=1000):
            follow_btn.scroll_into_view_if_needed()
            time.sleep(0.2)
            follow_btn.click()
            log.debug("✓ User unfollowed")
            random_delay()
            return True
    except Exception as e:
        log.warning(f"Failed to unfollow user: {e}")
        return False