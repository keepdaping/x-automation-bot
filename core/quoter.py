# core/quoter.py
import random
from tweepy import Client
from logger_setup import log
from config import Config



def find_quote_candidate(client: Client) -> str | None:
    q = random.choice(Config.SEARCH_KEYWORDS)
    query = f'"{q}" -is:retweet lang:en'  # removed min_faves

    try:
        results = client.search_recent_tweets(
            query=query,
            max_results=10,
            tweet_fields=["public_metrics", "created_at"],
            expansions=["author_id"]
        )
        if not results.data:
            return None

        # Filter in Python after fetching
        candidates = [t for t in results.data if t.public_metrics.get("like_count", 0) >= 5]
        if not candidates:
            log.info("No tweets with >=12 likes found — skipping quote")
            return None

        chosen = random.choice(candidates)
        log.info(f"Selected quote candidate with {chosen.public_metrics['like_count']} likes")
        return chosen.id

    except tweepy.TweepyException as e:
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