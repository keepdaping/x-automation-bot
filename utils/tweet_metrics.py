"""Extract metrics from tweet elements."""

import re
from datetime import datetime, timezone


def _extract_number(text: str) -> int:
    if not text:
        return 0
    text = text.replace(",", "").strip()
    match = re.search(r"\d+", text)
    return int(match.group()) if match else 0


def get_tweet_metrics(tweet):
    metrics = {"likes": 0, "replies": 0, "retweets": 0, "age_seconds": None}

    try:
        metrics["likes"] = _extract_number(tweet.locator('[data-testid="like"]').inner_text())
    except Exception:
        pass
    try:
        metrics["replies"] = _extract_number(tweet.locator('[data-testid="reply"]').inner_text())
    except Exception:
        pass
    try:
        metrics["retweets"] = _extract_number(tweet.locator('[data-testid="retweet"]').inner_text())
    except Exception:
        pass
    try:
        time_el = tweet.locator("time").first
        ts = time_el.get_attribute("datetime")
        if ts:
            ts = ts.strip()
            if ts.endswith("Z"):
                ts = ts[:-1] + "+00:00"
            dt = datetime.fromisoformat(ts)
            metrics["age_seconds"] = max(0, (datetime.now(timezone.utc) - dt).total_seconds())
    except Exception:
        pass

    return metrics
