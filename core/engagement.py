# core/engagement.py

import time
import random
from tweepy import Client
from logger_setup import log


SEARCH_QUERY = (
    "AI OR coding OR programming OR startups OR automation "
    "-is:retweet lang:en min_faves:20"
)


def engage_with_posts(client: Client):

    try:

        tweets = client.search_recent_tweets(
            query=SEARCH_QUERY,
            max_results=10
        )

        if not tweets.data:
            log.info("No tweets found for engagement")
            return

        for tweet in tweets.data:

            delay = random.uniform(4, 18)
            time.sleep(delay)

            try:
                client.like(tweet.id)
                log.info(f"Liked tweet {tweet.id}")

            except Exception as e:
                log.warning(f"Like failed: {e}")

    except Exception as e:

        log.warning(f"Engagement search failed: {e}")


def engage_with_replies(client: Client, tweet_id: str, already_liked: set):

    try:

        replies = client.search_recent_tweets(
            query=f"conversation_id:{tweet_id}",
            max_results=10
        )

        for reply in (replies.data or []):

            if reply.id in already_liked:
                continue

            delay = random.uniform(4, 18)
            time.sleep(delay)

            try:

                client.like(reply.id)

                already_liked.add(reply.id)

                log.info(f"Liked reply {reply.id}")

            except Exception as e:

                log.warning(f"Reply engagement failed: {e}")

    except Exception as e:

        log.warning(f"Engagement error: {e}")