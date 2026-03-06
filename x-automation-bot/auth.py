# auth.py
import tweepy
from config import Config
from logger_setup import log


def get_client() -> tweepy.Client:
    """
    Build and return an authenticated Tweepy v2 client.

    Config.validate() must have already been called before this function
    is invoked, so we know all keys are present.
    """
    client = tweepy.Client(
        bearer_token=Config.X_BEARER_TOKEN,
        consumer_key=Config.X_API_KEY,
        consumer_secret=Config.X_API_SECRET,
        access_token=Config.X_ACCESS_TOKEN,
        access_token_secret=Config.X_ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=True,
    )

    # Verify credentials with a lightweight API call.
    try:
        me = client.get_me()
        log.info(f"Authenticated as @{me.data.username}")
    except tweepy.errors.Unauthorized:
        raise RuntimeError(
            "Twitter authentication failed (401). "
            "Check that your OAuth tokens have Read & Write permissions."
        )
    except tweepy.TweepyException as exc:
        raise RuntimeError(f"Twitter authentication error: {exc}") from exc

    return client
