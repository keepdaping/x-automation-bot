"""
Unfollow strategy - unfollow users who haven't followed back.
NEW MODULE: Prevents follow/following ratio from getting out of control.
"""

import time
import random
from config import Config
from database import get_stale_follows, mark_unfollowed
from core.rate_limiter import get_rate_limiter
from logger_setup import log


def run_unfollow_cycle(page, max_unfollows: int = None):
    """
    Unfollow users who haven't followed back after N days.
    
    Args:
        page: Playwright page object
        max_unfollows: Max unfollows this cycle (default from config)
    """
    try:
        rate_limiter = get_rate_limiter()
        max_unfollows = max_unfollows or Config.MAX_UNFOLLOWS_PER_DAY
        
        stale = get_stale_follows(days=Config.UNFOLLOW_AFTER_DAYS, limit=max_unfollows)
        
        if not stale:
            log.debug("No stale follows to unfollow")
            return 0
        
        log.info(f"Found {len(stale)} stale follows to unfollow")
        unfollowed = 0
        
        for user in stale:
            if not rate_limiter.can_perform_action("unfollow")[0]:
                log.info("Unfollow rate limit reached")
                break
            
            username = user["username"]
            if not username:
                continue
            
            try:
                success = _unfollow_user_by_profile(page, username)
                if success:
                    mark_unfollowed(user["user_id"])
                    rate_limiter.record_action("unfollow", success=True, target_id=username)
                    unfollowed += 1
                    log.info(f"✓ Unfollowed @{username}")
                    time.sleep(random.uniform(3, 8))
                else:
                    log.debug(f"Failed to unfollow @{username}")
            except Exception as e:
                log.warning(f"Error unfollowing @{username}: {e}")
        
        if unfollowed > 0:
            log.info(f"Unfollow cycle: {unfollowed}/{len(stale)} unfollowed")
        return unfollowed
    
    except Exception as e:
        log.error(f"Unfollow cycle error: {e}")
        return 0


def _unfollow_user_by_profile(page, username: str, timeout=10000) -> bool:
    """Navigate to user profile and click unfollow."""
    try:
        page.goto(f"https://x.com/{username}", wait_until="domcontentloaded", timeout=timeout)
        time.sleep(2)
        
        # Look for "Following" button (indicates we follow them).
        # X renders the button as data-testid="userActions" containing text "Following",
        # or as a standalone role=button with that label.  Try both selectors.
        following_btn = page.locator(
            "[data-testid='userActions'] div[role='button']:has-text('Following'), "
            "div[data-testid='placeholderFollowButton']:has-text('Following'), "
            "div[role='button']:has-text('Following')"
        ).first

        if not following_btn or not following_btn.is_visible(timeout=3000):
            log.debug(f"@{username}: not following or button not found")
            return False
        
        following_btn.click(timeout=5000)
        time.sleep(1)
        
        # Confirm unfollow dialog
        confirm_btn = page.locator("[data-testid='confirmationSheetConfirm']").first
        if confirm_btn and confirm_btn.is_visible(timeout=3000):
            confirm_btn.click(timeout=3000)
            time.sleep(1)
            return True
        
        return False
    
    except Exception as e:
        log.debug(f"Unfollow @{username} failed: {e}")
        return False
