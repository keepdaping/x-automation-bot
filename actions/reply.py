from utils.human_behavior import random_delay

def quote_tweet(page, tweet, text):

    try:
        quote_btn = tweet.query_selector('[data-testid="retweet"]')

        if quote_btn:
            quote_btn.click()

            page.wait_for_selector('[data-testid="quoteTweet"]', timeout=10000)

            page.click('[data-testid="quoteTweet"]')

            page.wait_for_selector('[data-testid="tweetTextarea_0"]')

            page.fill('[data-testid="tweetTextarea_0"]', text)

            page.keyboard.press("Control+Enter")

            random_delay()

    except Exception as e:
        print("Quote skipped:", e)