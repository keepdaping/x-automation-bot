"""Extract text from tweet elements."""

def get_tweet_text(tweet):
    try:
        return tweet.locator('[data-testid="tweetText"]').inner_text().strip()
    except Exception:
        return ""
