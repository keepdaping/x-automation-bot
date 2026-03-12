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
            page.goto(search_url, wait_until="domcontentloaded", timeout=timeout)
        except:
            log.warning(f"Search timeout, retrying with longer wait...")
            page.goto(search_url, timeout=timeout + 5000)
        
        # Wait for results to load
        time.sleep(2)
        
        # Dismiss any overlays that might block interactions
        try:
            page.press("body", "Escape")
            time.sleep(0.5)
        except:
            pass
        
        # Apply natural scrolling behavior
        natural_scroll(page, pixels=1500, delay_between_scrolls=300)
        
        time.sleep(2)
        
        # Get all tweet articles
        try:
            page.wait_for_selector(TWEET_ARTICLE, timeout=5000)
            all_tweets = page.locator(TWEET_ARTICLE).all()
            
            if not all_tweets:
                log.warning(f"No tweets found for '{keyword}'")
                return []
            
            log.info(f"Found {len(all_tweets)} tweets, returning top {max_results}")
            
            # Return limited results
            return all_tweets[:max_results]
        
        except Exception as e:
            log.error(f"Error waiting for tweets: {e}")
            return []
    
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
