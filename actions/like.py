from utils.human_behavior import random_delay

def like_tweet(tweet):

    try:
        btn = tweet.query_selector('[data-testid="like"]')
        if btn:
            btn.click()
            random_delay()
    except:
        pass