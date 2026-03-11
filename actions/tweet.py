from utils.human_behavior import random_delay

def post_tweet(page, text):

    page.goto("https://x.com/compose/post")

    page.wait_for_selector('[data-testid="tweetTextarea_0"]')

    page.fill('[data-testid="tweetTextarea_0"]', text)

    page.keyboard.press("Control+Enter")

    random_delay()