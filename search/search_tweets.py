import time
import urllib.parse
from utils.human_behavior import random_delay, natural_scroll
from utils.selectors import SEARCH_RESULTS_CONTAINER, TWEET_ARTICLE
from logger_setup import log


def search_tweets(page, keyword, max_results=5, timeout=15000):
    """
    Search for tweets with given keyword and return result elements
    
    Args:
        page: Playwright page object
        keyword: Search keyword/phrase
        max_results: Max tweets to return
        timeout: Navigation timeout
    
    Returns:
        List of tweet article elements
    """
    try:
        # URL encode the keyword
        encoded_keyword = urllib.parse.quote(keyword)
        search_url = f"https://x.com/search?q={encoded_keyword}&f=live"
        
        log.info(f"Searching for '{keyword}'...")
        
        # Navigate to search results
        try:
            page.goto(search_url, wait_until="networkidle", timeout=timeout)
        except:
            log.warning(f"Search timeout with networkidle, trying load...")
            try:
                page.goto(search_url, wait_until="load", timeout=timeout)
            except:
                log.warning(f"Search timeout, navigating without wait...")
                page.goto(search_url)
        
        # Wait longer for JavaScript to render tweets
        time.sleep(4)
        
        # Dismiss any overlays
        try:
            page.press("Escape")
            time.sleep(0.5)
        except:
            pass
        
        # Scroll to trigger lazy-loading
        log.info("Scrolling to load tweets...")
        for i in range(3):
            page.evaluate("window.scrollBy(0, 500)")
            time.sleep(1)
        
        # Scroll back to top
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)
        
        # Try multiple selectors for tweets
        all_tweets = []
        selectors_to_try = [
            "article",  # Most common
            "[role='article']",
            "[data-testid='tweet']",
            "div[lang]",  # X uses lang attributes on tweet containers
        ]
        
        for selector in selectors_to_try:
            try:
                log.info(f"Trying selector: {selector}")
                # Wait for at least one element
                page.wait_for_selector(selector, timeout=5000)
                elements = page.locator(selector).all()
                
                if elements and len(elements) > 0:
                    log.info(f"Found {len(elements)} elements with selector '{selector}'")
                    all_tweets = elements
                    break
            except Exception as e:
                log.debug(f"Selector '{selector}' failed: {e}")
                continue
        
        if not all_tweets:
            log.warning(f"No tweets found for '{keyword}'")
            return []
        
        log.info(f"Found {len(all_tweets)} tweets, returning top {min(max_results, len(all_tweets))}")
        
        # Return limited results
        return all_tweets[:max_results]
    
    except Exception as e:
        log.error(f"Search failed for '{keyword}': {e}")
        return []


def search_with_retry(page, keyword, max_retries=2):
    """Search with automatic retry on failure"""
    for attempt in range(max_retries):
        try:
            tweets = search_tweets(page, keyword)
            if tweets:
                return tweets
            else:
                log.warning(f"No results on attempt {attempt + 1}")
        except Exception as e:
            log.error(f"Search attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
    
    return []
