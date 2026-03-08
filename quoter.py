# quoter.py
"""
Quote Tweet System — finds trending tweets in your niche and quote tweets
them with your own opinion. Free exposure to other people's audiences.

Upgraded Strategy (Viral Radar):
  1. Search MULTIPLE keywords per run (not just one random one)
  2. Score every tweet using ViralScore formula
  3. Filter by tweet age for velocity detection (fast-rising tweets)
  4. Filter out low-follower spam accounts
  5. Pick the highest-scoring tweet not already processed
  6. Generate a short opinionated response
  7. Post as a quote tweet — retry automatically on restricted tweets

ViralScore = likes + (retweets * 2) + (replies * 1.5) + velocity_bonus
velocity_bonus = extra points if tweet is < 2 hours old and already engaging
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timezone, timedelta

import anthropic
import tweepy

from config import Config
from database import is_tweet_liked, record_like
from logger_setup import log


# ── Configuration ─────────────────────────────────────────────────────────────

# All keywords — bot searches KEYWORDS_PER_RUN of these each run
SEARCH_KEYWORDS = [
    "freelancing tips",
    "making money online",
    "learn to code",
    "AI tools 2025",
    "building in public",
    "side hustle",
    "self taught developer",
    "solopreneur",
    "indie hacker",
    "work from anywhere",
    "coding journey",
    "freelance developer",
]

# How many keywords to search per run (more = bigger pool = more chances)
KEYWORDS_PER_RUN = 3

# Minimum raw likes before even scoring a tweet
# Lower than before — ViralScore handles quality filtering now
MIN_LIKES_TO_QUALIFY = 5

# Minimum ViralScore to be considered (filters low-quality tweets)
MIN_VIRAL_SCORE = 10

# Minimum author followers (filters spam/bot accounts)
MIN_AUTHOR_FOLLOWERS = 100

# Tweet age window — only consider tweets posted in the last N hours
# Catches fast-rising tweets before everyone else quotes them
MAX_TWEET_AGE_HOURS = 6

# Velocity bonus — extra score if tweet is young AND already engaging
VELOCITY_BONUS = 15          # bonus points added for fast-rising tweets
VELOCITY_AGE_THRESHOLD = 2  # hours — tweet must be younger than this to get bonus
VELOCITY_MIN_LIKES = 10     # must have this many likes to get velocity bonus


# ── Quote tweet prompt ────────────────────────────────────────────────────────

_QUOTE_SYSTEM_PROMPT = """\
You are a young person building in public — learning to code, freelancing, \
and growing an audience online.

Someone posted a tweet in your niche. You want to quote tweet it with your \
own honest opinion or experience that adds value to the conversation.

Rules:
- 1-2 sentences maximum. Under 220 characters.
- Sound like a real person, not a bot. Casual and direct.
- Add your own experience, a contrasting view, or a useful addition.
- Say something that makes people curious about YOU.
- No emojis. No hashtags. No "follow me" phrases.
- Never start with "I" as the first word.
- Output ONLY the quote tweet text. Nothing else.
"""


# ── ViralScore formula ────────────────────────────────────────────────────────

def _viral_score(tweet, created_at: datetime | None) -> float:
    """
    Score a tweet by engagement quality and velocity.

    Formula:
      base  = likes * 1.0  +  retweets * 2.0  +  replies * 1.5
      bonus = VELOCITY_BONUS if tweet is young and already getting likes
      final = base + bonus
    """
    metrics = tweet.public_metrics or {}
    likes    = metrics.get("like_count", 0)
    retweets = metrics.get("retweet_count", 0)
    replies  = metrics.get("reply_count", 0)

    base = (likes * 1.0) + (retweets * 2.0) + (replies * 1.5)

    bonus = 0.0
    if created_at is not None:
        now = datetime.now(timezone.utc)
        age_hours = (now - created_at).total_seconds() / 3600
        if age_hours < VELOCITY_AGE_THRESHOLD and likes >= VELOCITY_MIN_LIKES:
            bonus = VELOCITY_BONUS
            log.debug(
                f"[Quoter] Velocity bonus applied — age={age_hours:.1f}h "
                f"likes={likes}"
            )

    return base + bonus


# ── Tweet age parser ──────────────────────────────────────────────────────────

def _parse_created_at(tweet) -> datetime | None:
    try:
        if hasattr(tweet, "created_at") and tweet.created_at:
            dt = tweet.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
    except Exception:
        pass
    return None


# ── AI quote generation ───────────────────────────────────────────────────────

def _generate_quote_text(original_tweet: str) -> str | None:
    try:
        ai = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        message = ai.messages.create(
            model=Config.AI_MODEL,
            max_tokens=120,
            system=_QUOTE_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f'Someone tweeted:\n\n"{original_tweet}"\n\n'
                        "Write a short quote tweet response that adds your perspective."
                    ),
                }
            ],
        )
        text = message.content[0].text.strip().strip('"').strip("'").strip()
        return text[:220] if text else None

    except KeyboardInterrupt:
        raise
    except Exception as exc:
        log.error(f"[Quoter] AI generation failed: {type(exc).__name__}: {exc}")
        return None


# ── Multi-keyword search ──────────────────────────────────────────────────────

def _search_keyword(
    client: tweepy.Client,
    keyword: str,
) -> tuple[list, dict]:
    """
    Search one keyword and return raw tweet objects + includes.
    Returns empty list on any error so the caller can continue.
    """
    try:
        results = client.search_recent_tweets(
            query=f"{keyword} -is:retweet -is:reply lang:en",
            tweet_fields=["public_metrics", "author_id", "text", "created_at"],
            expansions=["author_id"],
            user_fields=["public_metrics"],
            max_results=20,
        )
        if results.data:
            log.debug(
                f"[Quoter] '{keyword}' → {len(results.data)} tweets returned"
            )
            return results.data, results.includes or {}
        else:
            log.debug(f"[Quoter] '{keyword}' → no results")
            return [], {}

    except tweepy.errors.TooManyRequests:
        log.warning(f"[Quoter] Rate limited searching '{keyword}' — skipping.")
        return [], {}
    except Exception as exc:
        log.warning(f"[Quoter] Search failed for '{keyword}': {exc}")
        return [], {}


# ── Build follower lookup from API response ───────────────────────────────────

def _build_follower_map(includes: dict) -> dict[str, int]:
    """Map author_id → follower_count from the expansions response."""
    follower_map = {}
    users = includes.get("users", [])
    for user in users:
        try:
            fcount = (
                user.public_metrics.get("followers_count", 0)
                if user.public_metrics else 0
            )
            follower_map[str(user.id)] = fcount
        except Exception:
            pass
    return follower_map


# ── Core cycle ────────────────────────────────────────────────────────────────

def run_quote_tweet_cycle(client: tweepy.Client) -> None:
    """
    Multi-keyword viral radar search. Scores all candidates and picks the best.
    Called once per GitHub Actions run.
    """
    log.info("─" * 50)
    log.info("[Quoter] Starting quote tweet cycle (Viral Radar)…")

    # ── Search multiple keywords ──────────────────────────────────────────
    keywords_this_run = random.sample(
        SEARCH_KEYWORDS,
        min(KEYWORDS_PER_RUN, len(SEARCH_KEYWORDS))
    )
    log.info(
        f"[Quoter] Searching {len(keywords_this_run)} keywords: "
        f"{keywords_this_run}"
    )

    all_candidates = []
    now = datetime.now(timezone.utc)
    age_cutoff = now - timedelta(hours=MAX_TWEET_AGE_HOURS)

    for keyword in keywords_this_run:
        tweets, includes = _search_keyword(client, keyword)
        if not tweets:
            continue

        follower_map = _build_follower_map(includes)

        for tweet in tweets:
            tweet_id = str(tweet.id)

            # Skip already processed
            if is_tweet_liked(f"quoted_{tweet_id}"):
                continue

            # Skip low-like tweets before scoring
            likes = (tweet.public_metrics or {}).get("like_count", 0)
            if likes < MIN_LIKES_TO_QUALIFY:
                continue

            # Parse age and skip tweets outside age window
            created_at = _parse_created_at(tweet)
            if created_at and created_at < age_cutoff:
                continue

            # Skip low-follower authors (spam/bot filter)
            author_id = str(tweet.author_id)
            followers = follower_map.get(author_id, 0)
            if followers < MIN_AUTHOR_FOLLOWERS:
                log.debug(
                    f"[Quoter] Skipped tweet {tweet_id} — "
                    f"author has only {followers} followers"
                )
                continue

            # Calculate ViralScore
            score = _viral_score(tweet, created_at)
            if score < MIN_VIRAL_SCORE:
                continue

            age_str = (
                f"{(now - created_at).total_seconds() / 3600:.1f}h old"
                if created_at else "age unknown"
            )

            all_candidates.append({
                "tweet":    tweet,
                "tweet_id": tweet_id,
                "score":    score,
                "likes":    likes,
                "followers": followers,
                "age_str":  age_str,
                "keyword":  keyword,
            })

    # ── Dedup candidates by tweet_id (same tweet can appear in multiple keywords)
    seen_ids = set()
    unique_candidates = []
    for c in all_candidates:
        if c["tweet_id"] not in seen_ids:
            seen_ids.add(c["tweet_id"])
            unique_candidates.append(c)
    all_candidates = unique_candidates

    if not all_candidates:
        log.info(
            f"[Quoter] No qualifying tweets found across "
            f"{len(keywords_this_run)} keywords. "
            f"(Thresholds: {MIN_LIKES_TO_QUALIFY}+ likes, "
            f"{MIN_VIRAL_SCORE}+ ViralScore, "
            f"{MIN_AUTHOR_FOLLOWERS}+ followers, "
            f"posted in last {MAX_TWEET_AGE_HOURS}h)"
        )
        log.info("[Quoter] Quote tweet cycle complete.")
        return

    # Sort by ViralScore descending — best tweet first
    all_candidates.sort(key=lambda c: c["score"], reverse=True)

    log.info(
        f"[Quoter] {len(all_candidates)} candidate(s) found across all keywords. "
        f"Top score: {all_candidates[0]['score']:.1f}"
    )

    # ── Try each candidate until one posts successfully ───────────────────
    for candidate in all_candidates:
        tweet    = candidate["tweet"]
        tweet_id = candidate["tweet_id"]
        score    = candidate["score"]
        likes    = candidate["likes"]
        age_str  = candidate["age_str"]
        keyword  = candidate["keyword"]

        log.info(
            f"[Quoter] Trying — score={score:.1f} likes={likes} "
            f"{age_str} keyword='{keyword}' "
            f"text='{tweet.text[:70]}…'"
        )

        quote_text = _generate_quote_text(tweet.text)
        if not quote_text:
            log.warning("[Quoter] AI returned nothing — trying next candidate.")
            continue

        try:
            delay = random.randint(5, 15)
            log.info(f"[Quoter] Waiting {delay}s before posting…")
            time.sleep(delay)

            response = client.create_tweet(
                text=quote_text,
                quote_tweet_id=tweet_id,
            )
            new_id = str(response.data["id"])

            # Mark as processed so we don't quote it again
            record_like(f"quoted_{tweet_id}")

            log.success(
                f"[Quoter] Quote tweet posted ✅ — "
                f"our_tweet={new_id} quoting={tweet_id} "
                f"score={score:.1f} "
                f"content='{quote_text[:60]}…'"
            )
            log.info("[Quoter] Quote tweet cycle complete.")
            return  # Done

        except tweepy.errors.Forbidden:
            log.warning(
                f"[Quoter] Tweet {tweet_id} cannot be quoted (restricted) — "
                "marking as skipped, trying next."
            )
            record_like(f"quoted_{tweet_id}")
            continue

        except tweepy.errors.TooManyRequests as exc:
            log.warning(f"[Quoter] Rate limited by X (429): {exc}")
            log.info("[Quoter] Quote tweet cycle complete.")
            return

        except KeyboardInterrupt:
            raise

        except Exception as exc:
            log.error(
                f"[Quoter] Unexpected error on tweet {tweet_id}: "
                f"{type(exc).__name__}: {exc}"
            )
            continue

    log.info(
        f"[Quoter] Tried all {len(all_candidates)} candidate(s) — "
        "none could be posted (all restricted or AI failed)."
    )
    log.info("[Quoter] Quote tweet cycle complete.")
