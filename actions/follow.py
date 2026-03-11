from utils.human_behavior import random_delay


def follow_user(tweet):

    try:

        follow_btn = tweet.locator('[data-testid="follow"]').first

        if follow_btn:

            follow_btn.click()

            random_delay()

    except Exception as e:

        print("Follow skipped:", e)