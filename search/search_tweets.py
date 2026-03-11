from utils.human_behavior import random_delay


def search_tweets(page, keyword):

    url = f"https://x.com/search?q={keyword}&f=live"

    page.goto(url)

    random_delay()

    page.mouse.wheel(0, 1500)

    page.wait_for_timeout(2000)

    tweets = page.locator("article").all()

    return tweets[:5]