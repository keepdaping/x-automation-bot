from utils.human_behavior import random_delay


def reply_tweet(page, tweet, text):

    try:
        reply_btn = tweet.query_selector('[data-testid="reply"]')

        if reply_btn:
            reply_btn.click()

            page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=10000)

            page.fill('[data-testid="tweetTextarea_0"]', text)

            page.keyboard.press("Control+Enter")

            random_delay()

    except Exception as e:
        print("Reply skipped:", e)