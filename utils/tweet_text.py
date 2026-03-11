def get_tweet_text(tweet):

```
try:
    text = tweet.locator('[data-testid="tweetText"]').inner_text()
    return text.strip()

except:
    return ""
```
