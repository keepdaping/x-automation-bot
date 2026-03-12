def get_tweet_text(tweet):
    """Extract text content from a tweet element"""
    try:
        text = tweet.locator('[data-testid="tweetText"]').inner_text()
        return text.strip()
    except:
        return ""
