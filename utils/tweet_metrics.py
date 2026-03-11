import re

def extract_number(text):

    if not text:
        return 0

    text = text.replace(",", "")

    match = re.search(r"\d+", text)

    return int(match.group()) if match else 0


def get_tweet_metrics(tweet):

    metrics = {}

    try:
        metrics["likes"] = extract_number(
            tweet.locator('[data-testid="like"]').inner_text()
        )
    except:
        metrics["likes"] = 0

    try:
        metrics["replies"] = extract_number(
            tweet.locator('[data-testid="reply"]').inner_text()
        )
    except:
        metrics["replies"] = 0

    return metrics

def score_tweet(metrics):
import re


def _extract_number(text: str) -> int:
    if not text:
        return 0

    text = text.replace(",", "").strip()

    match = re.search(r"\d+", text)

    if match:
        return int(match.group())

    return 0


def get_tweet_metrics(tweet):

    metrics = {
        "likes": 0,
        "replies": 0,
        "retweets": 0
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

    return metrics
    score = (
        metrics["likes"] * 2
        + metrics["replies"] * 3
    )

    return score