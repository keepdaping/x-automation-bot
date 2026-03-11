from utils.human_behavior import random_delay

def reply_tweet(page, tweet, text):

    try:

        btn = tweet.query_selector('[data-testid="reply"]')

        btn.click()

        page.wait_for_selector('[data-testid="tweetTextarea_0"]')

        page.fill('[data-testid="tweetTextarea_0"]', text)

        page.keyboard.press("Control+Enter")

        random_delay()

    except:
        pass