import tweepy
from config import Config
from logger_setup import log

def get_client() -> tweepy.Client:
    client = tweepy.Client(
        bearer_token=Config.X_BEARER_TOKEN,
        consumer_key=Config.X_API_KEY,
        consumer_secret=Config.X_API_SECRET,
        access_token=Config.X_ACCESS_TOKEN,
        access_token_secret=Config.X_ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=True,
    )
    try:
        me = client.get_me()
        log.info(f"✅ Authenticated as @{me.data.username}")
        return client
    except tweepy.Unauthorized:
        raise RuntimeError("Twitter auth failed — check OAuth permissions (Read + Write + Direct Messages recommended)")