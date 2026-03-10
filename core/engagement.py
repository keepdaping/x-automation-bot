# core/engagement.py
import time
import random
from tweepy import Client
from logger_setup import log


def engage_with_replies(client: Client, tweet_id: str, already_liked: set):
    try:
        replies = client.get_tweets(
            id=tweet_id,
            expansions=["referenced_tweets.id"],
            tweet_fields=["conversation_id", "in_reply_to_user_id"]
        )
        # very simplified
        for reply in (replies.data or []):
            if reply.id not in already_liked:
                time.sleep(random.uniform(4, 18))
                client.like(reply.id)
                already_liked.add(reply.id)
                log.info(f"Liked reply {reply.id}")
    except Exception as e:
        log.warning(f"Engagement error: {e}")