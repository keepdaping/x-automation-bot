import random

from config import KEYWORDS
from search.search_tweets import search_tweets
from actions.like import like_tweet
from actions.reply import reply_tweet
from utils.human_behavior import random_delay


def generate_reply():

    replies = [
        "Interesting perspective.",
        "I completely agree.",
        "This is very insightful.",
        "More people should see this.",
        "Great point."
    ]

    return random.choice(replies)


def run_engagement(page):

    keyword = random.choice(KEYWORDS)

    tweets = search_tweets(page, keyword)

    likes = 0
    replies = 0

    for tweet in tweets:

        if likes < 3:
            like_tweet(tweet)
            likes += 1

        if replies < 2:
            text = generate_reply()
            reply_tweet(page, tweet, text)
            replies += 1

        random_delay()