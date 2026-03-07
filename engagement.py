# engagement.py
"""
Engagement Monitor — scans replies on your recent tweets and:

  1. Likes every new reply (up to MAX_LIKES_PER_HOUR per rolling hour).
  2. Replies to comments that contain a question or meaningful discussion
     (up to MAX_REPLIES_PER_HOUR per rolling hour, one reply per user per tweet).

Configuration knobs (top of this file):
  MAX_LIKES_PER_HOUR      — hard cap on automated likes per rolling 60 min
  MAX_REPLIES_PER_HOUR    — hard cap on automated replies per rolling 60 min
  MAX_REPLIES_PER_CYCLE   — additional per-cycle ceiling
  REPLY_DELAY_MIN_SEC     — lower bound of the human-like pre-reply pause
  REPLY_DELAY_MAX_SEC     — upper bound of the human-like pre-reply pause
  RECENT_TWEETS_TO_CHECK  — how many of your own recent tweets to scan per cycle
  REPLY_MAX_CHARS         — hard character ceiling for generated replies
"""
from __future__ import annotations

import random
import re
import time

import anthropic
import tweepy

from config import Config
from database import (
    is_tweet_liked,
    record_like,
    has_replied_to_author,
    record_reply,
    engagement_count_last_hour,
)
from logger_setup import log


# ── Configuration ─────────────────────────────────────────────────────────────

MAX_LIKES_PER_HOUR     = 20
MAX_REPLIES_PER_HOUR   = 5
MAX_REPLIES_PER_CYCLE  = 5
REPLY_DELAY_MIN_SEC    = 10
REPLY_DELAY_MAX_SEC    = 30
RECENT_TWEETS_TO_CHECK = 5
REPLY_MAX_CHARS        = 220


# ── Reply system prompt ───────────────────────────────────────────────────────

_REPLY_SYSTEM_PROMPT = f"""\
You are a young person building in public — learning to code, freelancing, \
and sharing your journey online. You reply to comments on your X posts.

Your voice:
- Sound like a real person texting back, not a corporate account.
- Be genuine, warm and relatable — like talking to someone on the same journey.
- Casual and conversational. Short sentences. No big words.
- Honest about your own experience — share what you've actually been through.
- Encouraging without being fake or preachy.

Rules — follow every one:
- Reply in 1–2 sentences only. Absolute maximum {REPLY_MAX_CHARS} characters.
- Add real value: share a related experience, honest opinion, or useful tip.
- If the comment raises a genuine question or interesting angle, end with a
  short follow-up question that keeps the conversation going.
- Do NOT add a follow-up question if the comment is a simple reaction —
  only ask one when it genuinely extends the conversation.
- No emojis. No hashtags. No "follow me / check out / click here" phrases.
- Never open with "Great point!", "Thanks for sharing!", "Absolutely!", "Totally agree!" —
  these are filler. Start with the substance.
- Do NOT repeat or paraphrase the original tweet.
- Output ONLY the reply text. No preamble, no quotation marks, no label like "Reply:".
"""


# ── Question / discussion detector ───────────────────────────────────────────

_QUESTION_PATTERNS = re.compile(
    r"(\?)|"
    r"\b(how|why|what|when|where|which|who|"
    r"would|could|should|is it|does it|do you|"
    r"have you|can you|did you|thoughts on|"
    r"opinion on|agree|disagree|curious|wonder)\b",
    re.IGNORECASE,
)

_MIN_REPLY_WORDS = 4


def _is_worth_replying(text: str) -> bool:
    words = text.strip().split()
    if len(words) < _MIN_REPLY_WORDS:
        return False
    return bool(_QUESTION_PATTERNS.search(text))


# ── AI reply generation ───────────────────────────────────────────────────────

def _generate_reply(comment_text: str) -> str | None:
    try:
        client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=Config.AI_MODEL,
            max_tokens=120,
            system=_REPLY_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f'Someone replied to your tweet with:\n\n"{comment_text}"\n\n'
                        "Write a short, natural reply."
                    ),
                }
            ],
        )
        text = message.content[0].text.strip().strip('"').strip("'").strip()

        if len(text) > REPLY_MAX_CHARS:
            text = text[:REPLY_MAX_CHARS].rsplit(" ", 1)[0].rstrip(".,;:") + "…"

        log.info(f"[Engagement] Reply generated ({len(text)} chars)")
        return text if text else None

    except KeyboardInterrupt:
        raise
    except Exception as exc:
        log.error(f"[Engagement] AI reply generation failed: {type(exc).__name__}: {exc}")
        return None


# ── Rate-limit helpers ────────────────────────────────────────────────────────

def _likes_allowed() -> bool:
    used = engagement_count_last_hour("like")
    if used >= MAX_LIKES_PER_HOUR:
        log.warning(
            f"[Engagement] Like rate limit reached ({used}/{MAX_LIKES_PER_HOUR}/hr)."
        )
        return False
    return True


def _replies_allowed() -> bool:
    used = engagement_count_last_hour("reply")
    if used >= MAX_REPLIES_PER_HOUR:
        log.warning(
            f"[Engagement] Reply rate limit reached ({used}/{MAX_REPLIES_PER_HOUR}/hr)."
        )
        return False
    return True


# ── Core engagement cycle ─────────────────────────────────────────────────────

def run_engagement_cycle(client: tweepy.Client) -> None:
    """
    Main entry point — called once per GitHub Actions run.
    """
    log.info("─" * 50)
    log.info("[Engagement] Cycle started — scanning recent tweets for replies…")

    # ── Resolve own identity ──────────────────────────────────────────────
    try:
        me = client.get_me()
        my_user_id = str(me.data.id)
        my_username = me.data.username
    except Exception as exc:
        log.error(f"[Engagement] Could not resolve own identity: {exc}")
        return

    # ── Fetch recent tweets ───────────────────────────────────────────────
    try:
        my_tweets = client.get_users_tweets(
            id=my_user_id,
            max_results=RECENT_TWEETS_TO_CHECK,
            tweet_fields=["conversation_id", "text"],
        )
    except Exception as exc:
        log.error(f"[Engagement] Failed to fetch recent tweets: {exc}")
        return

    if not my_tweets.data:
        log.info("[Engagement] No recent tweets found.")
        return

    replies_sent_this_cycle = 0

    for tweet in my_tweets.data:
        log.info(f"[Engagement] Scanning tweet {tweet.id}: '{tweet.text[:60]}…'")

        try:
            results = client.search_recent_tweets(
                query=(
                    f"conversation_id:{tweet.id} "
                    f"is:reply "
                    f"-from:{my_username}"
                ),
                tweet_fields=["author_id", "text", "in_reply_to_user_id"],
                max_results=10,
            )
        except Exception as exc:
            log.warning(f"[Engagement] Search failed for tweet {tweet.id}: {exc}")
            continue

        if not results.data:
            log.debug(f"[Engagement] No replies found for tweet {tweet.id}.")
            continue

        for reply in results.data:
            reply_id   = str(reply.id)
            author_id  = str(reply.author_id)
            reply_text = reply.text.strip()

            # ── 1. LIKE ───────────────────────────────────────────────────
            if _likes_allowed() and not is_tweet_liked(reply_id):
                try:
                    client.like(reply_id)
                    record_like(reply_id)
                    log.success(f"[Engagement] Reply liked — tweet_id={reply_id}")
                except tweepy.errors.Forbidden:
                    log.warning(f"[Engagement] Like forbidden (already liked?) — {reply_id}")
                except tweepy.errors.TooManyRequests:
                    log.warning("[Engagement] Like rate limited by X — pausing likes this cycle.")
                except KeyboardInterrupt:
                    raise
                except Exception as exc:
                    log.error(f"[Engagement] Like failed for {reply_id}: {exc}")
            elif is_tweet_liked(reply_id):
                log.debug(f"[Engagement] Reply skipped (already liked) — {reply_id}")

            # ── 2. REPLY ──────────────────────────────────────────────────
            if replies_sent_this_cycle >= MAX_REPLIES_PER_CYCLE:
                log.info(
                    f"[Engagement] Per-cycle reply cap reached "
                    f"({MAX_REPLIES_PER_CYCLE}). Moving to next tweet."
                )
                break

            if not _replies_allowed():
                continue

            if has_replied_to_author(str(tweet.id), author_id):
                log.debug(
                    f"[Engagement] Reply skipped (already replied to author "
                    f"{author_id} on tweet {tweet.id})"
                )
                continue

            if not _is_worth_replying(reply_text):
                log.debug(
                    f"[Engagement] Reply skipped (not worth replying) — "
                    f"'{reply_text[:60]}'"
                )
                continue

            log.info(
                f"[Engagement] Generating reply for comment from "
                f"author {author_id}: '{reply_text[:80]}…'"
            )
            response_text = _generate_reply(reply_text)
            if not response_text:
                log.warning(f"[Engagement] AI returned nothing for {reply_id} — skipping.")
                continue

            delay = random.randint(REPLY_DELAY_MIN_SEC, REPLY_DELAY_MAX_SEC)
            log.info(f"[Engagement] Waiting {delay}s before posting reply…")
            time.sleep(delay)

            try:
                post_resp = client.create_tweet(
                    text=response_text,
                    in_reply_to_tweet_id=reply_id,
                )
                new_tweet_id = str(post_resp.data["id"])

                record_reply(
                    source_tweet_id=str(tweet.id),
                    reply_tweet_id=reply_id,
                    author_id=author_id,
                )
                replies_sent_this_cycle += 1

                log.success(
                    f"[Engagement] Reply posted — "
                    f"our_tweet={new_tweet_id} in_reply_to={reply_id} "
                    f"content='{response_text[:60]}…'"
                )

            except tweepy.errors.Forbidden as exc:
                log.error(f"[Engagement] Reply forbidden (403): {exc}")
            except tweepy.errors.TooManyRequests as exc:
                log.warning(f"[Engagement] Reply rate limited by X (429): {exc}")
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                log.error(f"[Engagement] Reply failed for {reply_id}: {exc}")

    likes_used   = engagement_count_last_hour("like")
    replies_used = engagement_count_last_hour("reply")
    log.info(
        f"[Engagement] Cycle complete — "
        f"{replies_sent_this_cycle} repl{'y' if replies_sent_this_cycle == 1 else 'ies'} sent | "
        f"Hourly usage: {likes_used}/{MAX_LIKES_PER_HOUR} likes, "
        f"{replies_used}/{MAX_REPLIES_PER_HOUR} replies"
    )
