from utils.human_behavior import random_delay, random_scroll

def search_tweets(page, keyword):

    url = f"https://x.com/search?q={keyword}&f=live"

    page.goto(url)

    random_delay()

    random_scroll(page)

    tweets = page.query_selector_all("article")

    page.mouse.wheel(0, 1200)

    return tweets[:5]