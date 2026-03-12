import random

from search.search_tweets import search_tweets
from actions.like import like_tweet
from actions.reply import reply_tweet
from actions.follow import follow_user

from core.generator import generate_contextual_reply
from utils.tweet_metrics import get_tweet_metrics
from utils.engagement_score import score_tweet
from utils.tweet_text import get_tweet_text


def run_engagement(page):

    tweets = search_tweets(page, "AI")

    for tweet in tweets:

        metrics = get_tweet_metrics(tweet)
        score = score_tweet(metrics)

        print("Metrics:", metrics, "Score:", score)

        # skip extremely dead tweets
        if score < 1:
            continue

        # like tweets frequently
        if random.random() < 0.6:
            like_tweet(tweet)

        # reply sometimes
        if random.random() < 0.25:

            tweet_text = get_tweet_text(tweet)

            reply = generate_contextual_reply(tweet_text)

            reply_tweet(page, tweet, reply)

        # follow sometimes
        if random.random() < 0.15:
            follow_user(tweet)