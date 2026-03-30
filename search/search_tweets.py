"""
Tweet search with scoring and deduplication.

FIXED: _seen_tweet_ids is now capped at _MAX_SEEN_IDS entries. Without this
cap the set grows for the entire lifetime of the process, consuming memory
and causing the bot to skip tweet IDs it encountered hours or days ago.
"""

import random
import re
import time
import urllib.parse
from typing import Optional, Set

from utils.human_behavior import natural_scroll
from utils.selectors import SEARCH_RESULTS_CONTAINER, TWEET_ARTICLE
from utils.tweet_metrics import get_tweet_metrics
from utils.engagement_score import score_tweet
from logger_setup import log

# Module-level dedup set — prevents processing the same tweet twice per session.
# Capped at _MAX_SEEN_IDS: when full, the set is cleared so old IDs don't
# block new searches indefinitely.
_seen_tweet_ids: Set[str] = set()
_MAX_SEEN_IDS = 500


def reset_seen_tweets() -> None:
    """Manually clear the dedup set (e.g. at session start)."""
    global _seen_tweet_ids
    _seen_tweet_ids.clear()


def _extract_tweet_id(tweet) -> Optional[str]:
    try:
        link = tweet.locator('a[href*="/status/"]').first
        href = link.get_attribute("href")
        if href:
            match = re.search(r"/status/(\d+)", href)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None


def _is_promoted(tweet) -> bool:
    try:
        return "promoted" in tweet.inner_text().lower()
    except Exception:
        return False


def search_tweets(page, keyword, max_results=8, timeout=15000):
    global _seen_tweet_ids

    try:
        encoded = urllib.parse.quote(keyword)
        search_url = f"https://x.com/search?q={encoded}&f=live"
        log.info(f"Searching '{keyword}'...")

        try:
            page.goto(search_url, wait_until="networkidle", timeout=timeout)
        except Exception:
            try:
                page.goto(search_url, wait_until="load", timeout=timeout)
            except Exception:
                page.goto(search_url)

        time.sleep(3)

        try:
            page.press("Escape")
        except Exception:
            pass

        candidates = []
        deadline = time.time() + (timeout / 1000)

        while time.time() < deadline and len(candidates) < max_results:
            natural_scroll(page, pixels=1500)

            tweet_elements = []
            try:
                container = page.locator(SEARCH_RESULTS_CONTAINER).first
                tweet_elements = container.locator(TWEET_ARTICLE).all()
            except Exception:
                try:
                    tweet_elements = page.locator(TWEET_ARTICLE).all()
                except Exception:
                    pass

            for tweet in tweet_elements:
                if len(candidates) >= max_results:
                    break
                try:
                    tweet_id = _extract_tweet_id(tweet)
                    if not tweet_id:
                        continue

                    # Cap the dedup set to prevent unbounded growth
                    if len(_seen_tweet_ids) >= _MAX_SEEN_IDS:
                        _seen_tweet_ids.clear()
                        log.debug(
                            f"_seen_tweet_ids cleared (reached {_MAX_SEEN_IDS} entry cap)"
                        )

                    if tweet_id in _seen_tweet_ids:
                        continue

                    if _is_promoted(tweet):
                        continue

                    metrics = get_tweet_metrics(tweet)
                    if sum(metrics.values()) < 3:
                        continue

                    s = score_tweet(metrics)
                    if s <= 0:
                        continue

                    if all(c["tweet_id"] != tweet_id for c in candidates):
                        candidates.append({"tweet": tweet, "tweet_id": tweet_id, "score": s})
                        _seen_tweet_ids.add(tweet_id)

                except Exception:
                    continue

        if not candidates:
            log.warning(f"No tweets found for '{keyword}'")
            return []

        candidates.sort(key=lambda x: x["score"], reverse=True)
        selected = []
        available = candidates.copy()
        weights = [c["score"] for c in available]

        while available and len(selected) < max_results:
            choice = random.choices(available, weights=weights, k=1)[0]
            selected.append(choice["tweet"])
            idx = available.index(choice)
            available.pop(idx)
            weights.pop(idx)

        log.info(f"Returning {len(selected)} tweets for '{keyword}'")
        return selected

    except Exception as e:
        log.error(f"Search failed for '{keyword}': {e}")
        return []
