from utils.human_behavior import random_delay


def reply_tweet(page, tweet, text):

    try:

        reply_btn = tweet.locator('[data-testid="reply"]').first

        if reply_btn:

            reply_btn.scroll_into_view_if_needed()

            page.wait_for_timeout(500)

            reply_btn.click(timeout=5000)

            page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=5000)

            page.fill('[data-testid="tweetTextarea_0"]', text)

            page.keyboard.press("Control+Enter")

            random_delay()

    except Exception as e:

        print("Reply skipped:", e)