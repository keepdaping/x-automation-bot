import re
from datetime import datetime, timezone


def _extract_number(text: str) -> int:
    """Extract the first number from text."""
    if not text:
        return 0

    text = text.replace(",", "").strip()
    match = re.search(r"\d+", text)

    if match:
        return int(match.group())

    return 0


def get_tweet_metrics(tweet):
    """Get metrics (likes, replies, retweets) from a tweet element."""
    metrics = {
        "likes": 0,
        "replies": 0,
        "retweets": 0,
        "age_seconds": None,
    }

    try:
        metrics["likes"] = _extract_number(
            tweet.locator('[data-testid="like"]').inner_text()
        )
    except:
        pass

    try:
        metrics["replies"] = _extract_number(
            tweet.locator('[data-testid="reply"]').inner_text()
        )
    except:
        pass

    try:
        metrics["retweets"] = _extract_number(
            tweet.locator('[data-testid="retweet"]').inner_text()
        )
    except:
        pass

    # Estimate tweet age (seconds) using the timestamp element if available
    try:
        time_el = tweet.locator("time").first
        ts = time_el.get_attribute("datetime")
        if ts:
            ts = ts.strip()
            # Convert Zulu time to offset-aware format for fromisoformat
            if ts.endswith("Z"):
                ts = ts[:-1] + "+00:00"
            dt = datetime.fromisoformat(ts)
            metrics["age_seconds"] = max(0, (datetime.now(timezone.utc) - dt).total_seconds())
    except:
        pass

    return metrics


def score_tweet(metrics):
    """Score a tweet based on its engagement metrics."""
    score = (
        metrics.get("likes", 0) * 2
        + metrics.get("replies", 0) * 3
        + metrics.get("retweets", 0) * 1
    )
    return score