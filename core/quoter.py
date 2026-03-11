# core/quoter.py

import random
import tweepy
import anthropic
from tweepy import Client
from logger_setup import log
from config import Config


def find_quote_candidate(client: Client) -> str | None:

    q = random.choice(Config.SEARCH_KEYWORDS)

    query = f'"{q}" -is:retweet lang:en'

    try:

        results = client.search_recent_tweets(
            query=query,
            max_results=10,
            tweet_fields=["public_metrics", "created_at"],
            expansions=["author_id"]
        )

        if not results.data:
            return None

        candidates = [
            t for t in results.data
            if t.public_metrics.get("like_count", 0) >= 5
        ]

        if not candidates:

            log.info("No tweets with >=5 likes found — skipping quote")
            return None

        chosen = random.choice(candidates)

        log.info(
            f"Selected quote candidate with {chosen.public_metrics['like_count']} likes"
        )

        return chosen.id

    except tweepy.TweepyException as e:

        log.error(f"Quote search failed: {e}")

        return None


def generate_quote_text(original_text: str) -> str | None:

    client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    prompt = f"""
Write a short value-adding quote tweet (1–2 sentences).

Original tweet:
{original_text}

Rules:
• add insight or contrarian take
• no spam
• no hashtags
• no links
• max 240 characters

Output ONLY the quote text.
"""

    try:

        msg = client.messages.create(
            model=Config.AI_MODEL_CRITIQUE,
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}]
        )

        text = msg.content[0].text.strip()

        if len(text) > 240:
            text = text[:240]

        return text

    except Exception as e:

        log.error(f"Quote generation failed: {e}")

        return None


def quote_tweet(client: Client):

    tweet_id = find_quote_candidate(client)

    if not tweet_id:
        return

    try:

        original = client.get_tweet(tweet_id)

        if not original.data:
            return

        quote_text = generate_quote_text(original.data.text)

        if not quote_text:
            return

        client.create_tweet(
            text=quote_text,
            quote_tweet_id=tweet_id
        )

        log.success(f"Quoted tweet {tweet_id}")

    except Exception as e:

        log.error(f"Quote tweet failed: {e}")