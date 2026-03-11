import random

from search.search_tweets import search_tweets
from actions.like import like_tweet
from actions.reply import reply_tweet
from actions.follow import follow_user
from core.generator import generate_reply
from utils.tweet_metrics import get_tweet_metrics
from utils.engagement_score import score_tweet
from core.generator import generate_contextual_reply
from utils.tweet_text import get_tweet_text


def run_engagement(page):

    tweets = search_tweets(page, "AI")

    for tweet in tweets:
        metrics = get_tweet_metrics(tweet)

        score = score_tweet(metrics)

        print("Metrics:", metrics, "Score:", score)
        
        
        if score < 20:
            continue

        like_tweet(tweet)

        reply = generate_reply("")

        reply_tweet(page, tweet, reply)
        
        if random.random() < 0.3:
            
            follow_user(tweet)