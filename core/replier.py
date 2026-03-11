# core/replier.py

import random
from tweepy import Client
from logger_setup import log
from core.moderator import is_safe_content


SEARCH_QUERY = (
    "AI OR coding OR programming OR startups OR automation "
    "-is:retweet lang:en min_faves:50"
)


def should_reply_to(text: str) -> bool:
    text = text.lower()

    if len(text.split()) >= 12:
        return True

    if "?" in text:
        return True

    return False


def generate_reply_text(parent_text: str) -> str | None:

    replies = [
        "This is a great point. Most people underestimate how important this is.",
        "Agree with this. The real advantage comes when you apply it consistently.",
        "Interesting perspective. Have you noticed how this changes once you scale?",
        "This is one of those ideas that sounds simple but is actually powerful.",
        "Completely agree. More people should talk about this.",
        "Well said. This is something beginners often overlook."
    ]

    reply = random.choice(replies)

    if len(reply) > 260:
        reply = reply[:260]

    if not is_safe_content(reply):
        return None

    return reply


def reply_to_tweets(client: Client):

    tweets = client.search_recent_tweets(
        query=SEARCH_QUERY,
        max_results=10
    )

    if not tweets.data:
        log.info("No tweets found for replying")
        return

    for tweet in tweets.data:

        if not should_reply_to(tweet.text):
            continue

        reply = generate_reply_text(tweet.text)

        if not reply:
            continue

        try:

            client.create_tweet(
                text=reply,
                in_reply_to_tweet_id=tweet.id
            )

            log.success(f"Replied to tweet {tweet.id}")

        except Exception as e:

            log.error(f"Reply failed: {e}")