import re
import time
import urllib.parse
from typing import Optional, Set

from utils.human_behavior import natural_scroll
from utils.selectors import SEARCH_RESULTS_CONTAINER, TWEET_ARTICLE
from utils.tweet_metrics import get_tweet_metrics
from utils.engagement_score import score_tweet
from logger_setup import log


# Track tweet IDs processed in this session (in-memory)
_seen_tweet_ids: Set[str] = set()


def reset_seen_tweets() -> None:
    """Clear the in-session cache of seen tweet IDs."""
    global _seen_tweet_ids
    _seen_tweet_ids.clear()


def _extract_tweet_id(tweet) -> Optional[str]:
    """Extract a tweet ID from the tweet element (from the status URL)."""
    try:
        # Find a link that points to /status/<id>
        link = tweet.locator('a[href*="/status/"]').first
        href = link.get_attribute("href")
        if not href:
            return None
        # Extract digits after /status/
        match = re.search(r"/status/(\d+)", href)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def _is_promoted(tweet) -> bool:
    """Detect if a tweet is promoted (ad)."""
    try:
        # Promoted label exists in the tweet header
        if "promoted" in tweet.inner_text().lower():
            return True
    except Exception:
        pass
    return False


def _is_pinned(tweet) -> bool:
    """Detect if a tweet is pinned."""
    try:
        if "pinned" in tweet.inner_text().lower():
            return True
    except Exception:
        pass
    return False


def search_tweets(page, keyword, max_results=5, timeout=15000):
    """Search for tweets with given keyword and return the best tweet elements."""
    try:
        # URL encode the keyword
        encoded_keyword = urllib.parse.quote(keyword)
        search_url = f"https://x.com/search?q={encoded_keyword}&f=live"

        log.info(f"Searching for '{keyword}'...")

        # Navigate to search results
        try:
            page.goto(search_url, wait_until="networkidle", timeout=timeout)
        except Exception:
            log.warning("Search timeout with networkidle, trying load...")
            try:
                page.goto(search_url, wait_until="load", timeout=timeout)
            except Exception:
                log.warning("Search timeout, navigating without wait...")
                page.goto(search_url)

        # Allow tweets to render
        time.sleep(3)

        # Dismiss overlays if any
        try:
            page.press("Escape")
            time.sleep(0.3)
        except Exception:
            pass

        # Ensure enough tweets are loaded by scrolling until we find candidates
        candidates = []
        deadline = time.time() + (timeout / 1000)

        while time.time() < deadline and len(candidates) < max_results:
            # Natural scroll to load more tweets
            natural_scroll(page, pixels=1500)

            # Locate tweets within main results container
            tweet_elements = []
            try:
                container = page.locator(SEARCH_RESULTS_CONTAINER).first
                tweet_elements = container.locator(TWEET_ARTICLE).all()
            except Exception:
                # Fallback: use global tweet selector
                try:
                    tweet_elements = page.locator(TWEET_ARTICLE).all()
                except Exception:
                    tweet_elements = []

            new_candidates = _process_tweet_candidates(tweet_elements, max_results)

            # Accumulate unique candidates (based on tweet_id)
            for cand in new_candidates:
                if len(candidates) >= max_results:
                    break
                if all(existing["tweet_id"] != cand["tweet_id"] for existing in candidates):
                    candidates.append(cand)

            if len(candidates) >= max_results:
                break

        if not candidates:
            log.warning(f"No tweets found for '{keyword}'")
            return []

        # Sort by score and return top results
        candidates.sort(key=lambda x: x["score"], reverse=True)
        selected = [c["tweet"] for c in candidates[:max_results]]

        log.info(f"Returning {len(selected)} tweet candidates for '{keyword}'")
        return selected

    except Exception as e:
        log.error(f"Search failed for '{keyword}': {e}")
        return []


def _process_tweet_candidates(tweet_elements, max_results: int):
    """Filter and score tweet elements into candidate list."""
    candidates = []

    for tweet in tweet_elements:
        try:
            tweet_id = _extract_tweet_id(tweet)
            if not tweet_id or tweet_id in _seen_tweet_ids:
                continue

            if _is_promoted(tweet) or _is_pinned(tweet):
                continue

            metrics = get_tweet_metrics(tweet)
            total_engagement = sum(metrics.values())
            if total_engagement < 3:
                continue

            score = score_tweet(metrics)
            if score <= 0:
                continue

            candidates.append({
                "tweet": tweet,
                "tweet_id": tweet_id,
                "score": score,
            })

            # Track seen tweets in-session
            _seen_tweet_ids.add(tweet_id)

            if len(candidates) >= max_results:
                break

        except Exception:
            continue

    return candidates


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
