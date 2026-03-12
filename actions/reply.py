import time
from utils.human_behavior import random_delay, random_delay_range, human_typing
from utils.selectors import REPLY_BUTTON, REPLY_TEXTAREA
from logger_setup import log


def reply_tweet(page, tweet, text, timeout=10000):
    """
    Reply to a tweet with human-like typing
    
    Args:
        page: Playwright page object
        tweet: Tweet element (article)
        text: Reply text
        timeout: Action timeout
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Find reply button
        reply_btn = tweet.locator(REPLY_BUTTON).first
        
        if not reply_btn:
            log.warning("Reply button not found")
            return False
        
        # Scroll into view
        reply_btn.scroll_into_view_if_needed()
        time.sleep(0.5)
        
        # Click reply button
        try:
            reply_btn.click(timeout=timeout)
        except:
            log.warning("Gentle click failed, force clicking...")
            reply_btn.click(timeout=timeout, force=True)
        
        # Wait for reply textarea to appear
        page.wait_for_selector(REPLY_TEXTAREA, timeout=timeout)
        time.sleep(1)
        
        # Find and fill textarea
        text_area = page.locator(REPLY_TEXTAREA).first
        if not text_area:
            text_area = page.locator("div[role='textbox']").first
        
        if text_area:
            # FIXED: Use human_typing for realistic speed (was too fast!)
            # WPM parameter: 60 = average typing speed
            human_typing(text_area, text, wpm=60)
        else:
            log.error("Could not find textarea for reply")
            return False
        
        # Submit reply
        time.sleep(1)
        page.keyboard.press("Control+Enter")
        time.sleep(1.5)
        
        log.debug(f"✓ Reply posted")
        random_delay()
        return True
    
    except Exception as e:
        log.warning(f"Failed to reply: {e}")
        return False