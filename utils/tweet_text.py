"""Extract and clean text from tweet elements."""

import re


def get_tweet_text(tweet):
    try:
        return tweet.locator('[data-testid="tweetText"]').inner_text().strip()
    except Exception:
        return ""


def clean_tweet_text(text: str, max_length: int = 200) -> str:
    """
    Clean raw tweet text before passing to the LLM.

    Steps (in order):
    1. Remove URLs
    2. Remove @mentions and #hashtags
    3. Normalize whitespace
    4. Extract the most signal-rich sentence
    5. Cap at max_length

    Returns the cleaned core text, or empty string if nothing meaningful remains.
    """
    if not text:
        return ""

    # 1. Remove URLs
    text = re.sub(r"https?://\S+|www\.\S+", "", text)

    # 2. Remove @mentions and #hashtags
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"#\w+", "", text)

    # 3. Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", " ", text)
    text = text.strip()

    # 4. Extract core sentence — pick the longest sentence as it usually
    #    carries the most signal (problem statement, opinion, context)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if sentences:
        core = max(sentences, key=len)
    else:
        core = text

    # 5. Cap length without splitting mid-word
    if len(core) > max_length:
        core = core[:max_length].rsplit(" ", 1)[0]

    return core
