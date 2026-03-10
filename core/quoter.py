# core/quoter.py
import random
from tweepy import Client
from logger_setup import log
from config import Config


def find_quote_candidate(client: Client) -> str | None:
    q = random.choice(Config.SEARCH_KEYWORDS)
    query = f'"{q}" min_faves:12 -is:retweet lang:en'

    try:
        results = client.search_recent_tweets(
            query=query,
            max_results=10,
            expansions=["author_id"],
            tweet_fields=["public_metrics", "created_at"]
        )
        if not results.data:
            return None

        candidates = [t for t in results.data if t.public_metrics["like_count"] >= 12]
        if not candidates:
            return None

        chosen = random.choice(candidates)
        return chosen.id
    except Exception as e:
        log.error(f"Quote search failed: {e}")
        return None


def generate_quote_text(original_text: str) -> str | None:
    client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    prompt = f"""Write a short, strong, value-adding quote-tweet reply (1-2 sentences max).
Original tweet: {original_text}

Rules: honest opinion, add insight or contrarian take, no spam, no tags, no links.
Output ONLY the quote text."""
    try:
        msg = client.messages.create(
            model=Config.AI_MODEL_CRITIQUE,
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text.strip()
    except:
        return None