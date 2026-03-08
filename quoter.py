# quoter.py
"""
Quote Tweet System — finds trending tweets in your niche and quote tweets
them with your own opinion. Free exposure to other people's audiences.

Strategy (Viral Radar v2):
  1. Search MULTIPLE keywords per run using strengthened X API filters
  2. Filter spam accounts (too few OR too many followers)
  3. Score every tweet using ViralScore v2 formula:
       base          = likes*1.0 + retweets*2.0 + replies*1.5
       velocity_bonus = +15 if tweet < 2h old and likes >= 10
       ratio_bonus    = min(likes/followers * 500, 25)
       final          = base + velocity_bonus + ratio_bonus
  4. Sort by ViralScore — best tweet first
  5. Try each candidate until one posts successfully
  6. Retry automatically on restricted tweets

Why ViralScore v2 is better:
  - Raw likes alone are misleading.
    8 likes on a 150-follower account = 5.3% engagement (genuinely viral)
    8 likes on a 50k-follower account = 0.016% engagement (invisible)
  - Engagement ratio catches early viral tweets that raw counts miss.
  - Velocity bonus detects fast-rising tweets before the conversation is crowded.
  - MAX_AUTHOR_FOLLOWERS cap ensures your quote is visible, not buried.
  - -has:links in search query removes promotional/spam content early.
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

# All keywords — bot samples KEYWORDS_PER_RUN of these each run
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

# How many keywords to search per run
KEYWORDS_PER_RUN = 3

# ── Author follower band ───────────────────────────────────────────────────────
# Too few = spam/bot account
# Too many = your quote gets buried under thousands of others
MIN_AUTHOR_FOLLOWERS = 100
MAX_AUTHOR_FOLLOWERS = 150_000

# ── Tweet quality thresholds ───────────────────────────────────────────────────
# Pre-filter before scoring (checked at API level via min_faves)
MIN_LIKES_TO_QUALIFY = 5

# Post-scoring minimum — tweets below this are skipped
MIN_VIRAL_SCORE = 10

# ── Tweet age window ───────────────────────────────────────────────────────────
# Only consider tweets posted in the last N hours
# Catches fast-rising tweets before the conversation is crowded
MAX_TWEET_AGE_HOURS = 6

# ── ViralScore v2 bonuses ──────────────────────────────────────────────────────
# Velocity — tweet is young AND already gaining traction
VELOCITY_BONUS           = 15   # points added
VELOCITY_AGE_THRESHOLD   = 2    # hours — tweet must be younger than this
VELOCITY_MIN_LIKES       = 10   # must already have this many likes

# Engagement ratio — likes relative to author's audience size
# Detects tweets punching above their weight
RATIO_MULTIPLIER         = 500  # scale factor
RATIO_MAX_BONUS          = 25   # cap so tiny accounts don't dominate


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


# ── ViralScore v2 ─────────────────────────────────────────────────────────────

def _viral_score(tweet, created_at: datetime | None, followers: int) -> float:
    """
    Score a tweet by engagement quality, velocity, and audience ratio.

    Formula:
      base          = likes*1.0 + retweets*2.0 + replies*1.5
      velocity_bonus = +15 if tweet age < 2h AND likes >= 10
      ratio_bonus    = min(likes/followers * 500, 25)
      final          = base + velocity_bonus + ratio_bonus
    """
    metrics  = tweet.public_metrics or {}
    likes    = metrics.get("like_count", 0)
    retweets = metrics.get("retweet_count", 0)
    replies  = metrics.get("reply_count", 0)

    base = (likes * 1.0) + (retweets * 2.0) + (replies * 1.5)

    # Velocity bonus
    velocity_bonus = 0.0
    if created_at is not None:
        age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
        if age_hours < VELOCITY_AGE_THRESHOLD and likes >= VELOCITY_MIN_LIKES:
            velocity_bonus = VELOCITY_BONUS
            log.debug(
                f"[Quoter] Velocity bonus +{VELOCITY_BONUS} — "
                f"age={age_hours:.1f}h likes={likes}"
            )

    # Engagement ratio bonus
    ratio       = likes / max(followers, 1)
    ratio_bonus = min(ratio * RATIO_MULTIPLIER, RATIO_MAX_BONUS)
    if ratio_bonus >= 5:
        log.debug(
            f"[Quoter] Ratio bonus +{ratio_bonus:.1f} — "
            f"likes={likes} followers={followers} ratio={ratio:.3f}"
        )

    return base + velocity_bonus + ratio_bonus


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _build_follower_map(includes: dict) -> dict[str, int]:
    """author_id → follower_count from the expansions response."""
    follower_map: dict[str, int] = {}
    for user in includes.get("users", []):
        try:
            fcount = (
                user.public_metrics.get("followers_count", 0)
                if user.public_metrics else 0
            )
            follower_map[str(user.id)] = fcount
        except Exception:
            pass
    return follower_map


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


def _search_keyword(client: tweepy.Client, keyword: str) -> tuple[list, dict]:
    """
    Search one keyword with strengthened filters.

    Improvements over v1:
      - min_faves:5  → X API filters weak tweets before they reach our code
      - -has:links   → removes promotional/blog/spam tweets early
    """
    try:
        query = (
            f"{keyword} -is:retweet -is:reply lang:en "
            f"min_faves:{MIN_LIKES_TO_QUALIFY} -has:links"
        )
        results = client.search_recent_tweets(
            query=query,
            tweet_fields=["public_metrics", "author_id", "text", "created_at"],
            expansions=["author_id"],
            user_fields=["public_metrics"],
            max_results=20,
        )
        if results.data:
            log.debug(f"[Quoter] '{keyword}' → {len(results.data)} tweets")
            return results.data, results.includes or {}
        log.debug(f"[Quoter] '{keyword}' → no results")
        return [], {}

    except tweepy.errors.TooManyRequests:
        log.warning(f"[Quoter] Rate limited on '{keyword}' — skipping.")
        return [], {}
    except Exception as exc:
        log.warning(f"[Quoter] Search failed for '{keyword}': {exc}")
        return [], {}


# ── Core cycle ────────────────────────────────────────────────────────────────

def run_quote_tweet_cycle(client: tweepy.Client) -> None:
    """
    Multi-keyword Viral Radar search with ViralScore v2.
    Called once per GitHub Actions run.
    """
    log.info("─" * 50)
    log.info("[Quoter] Starting quote tweet cycle (Viral Radar v2)…")

    keywords_this_run = random.sample(
        SEARCH_KEYWORDS, min(KEYWORDS_PER_RUN, len(SEARCH_KEYWORDS))
    )
    log.info(
        f"[Quoter] Searching {len(keywords_this_run)} keywords: "
        f"{keywords_this_run}"
    )

    now        = datetime.now(timezone.utc)
    age_cutoff = now - timedelta(hours=MAX_TWEET_AGE_HOURS)

    all_candidates: list[dict] = []
    seen_ids: set[str]         = set()

    for keyword in keywords_this_run:
        tweets, includes = _search_keyword(client, keyword)
        if not tweets:
            continue

        follower_map = _build_follower_map(includes)

        for tweet in tweets:
            tweet_id = str(tweet.id)

            # Dedup across keywords
            if tweet_id in seen_ids:
                continue
            seen_ids.add(tweet_id)

            # Already quoted
            if is_tweet_liked(f"quoted_{tweet_id}"):
                continue

            # Parse age — skip tweets outside window
            created_at = _parse_created_at(tweet)
            if created_at and created_at < age_cutoff:
                continue

            # Author follower band check
            author_id  = str(tweet.author_id)
            followers  = follower_map.get(author_id, 0)

            if followers < MIN_AUTHOR_FOLLOWERS:
                log.debug(
                    f"[Quoter] Skipped {tweet_id} — "
                    f"author too small ({followers} followers)"
                )
                continue

            if followers > MAX_AUTHOR_FOLLOWERS:
                log.debug(
                    f"[Quoter] Skipped {tweet_id} — "
                    f"author too large ({followers} followers, "
                    f"max {MAX_AUTHOR_FOLLOWERS})"
                )
                continue

            # Score
            score = _viral_score(tweet, created_at, followers)
            if score < MIN_VIRAL_SCORE:
                continue

            likes   = (tweet.public_metrics or {}).get("like_count", 0)
            age_str = (
                f"{(now - created_at).total_seconds() / 3600:.1f}h old"
                if created_at else "age unknown"
            )

            all_candidates.append({
                "tweet":     tweet,
                "tweet_id":  tweet_id,
                "score":     score,
                "likes":     likes,
                "followers": followers,
                "age_str":   age_str,
                "keyword":   keyword,
            })

    if not all_candidates:
        log.info(
            f"[Quoter] No qualifying tweets found across "
            f"{len(keywords_this_run)} keywords. "
            f"(Filters: {MIN_LIKES_TO_QUALIFY}+ likes via API, "
            f"ViralScore ≥ {MIN_VIRAL_SCORE}, "
            f"followers {MIN_AUTHOR_FOLLOWERS}–{MAX_AUTHOR_FOLLOWERS:,}, "
            f"last {MAX_TWEET_AGE_HOURS}h, no links)"
        )
        log.info("[Quoter] Quote tweet cycle complete.")
        return

    # Best tweet first
    all_candidates.sort(key=lambda c: c["score"], reverse=True)

    log.info(
        f"[Quoter] {len(all_candidates)} candidate(s) found. "
        f"Top ViralScore: {all_candidates[0]['score']:.1f}"
    )

    # ── Try each candidate until one posts ───────────────────────────────
    for candidate in all_candidates:
        tweet    = candidate["tweet"]
        tweet_id = candidate["tweet_id"]
        score    = candidate["score"]
        likes    = candidate["likes"]
        followers = candidate["followers"]
        age_str  = candidate["age_str"]
        keyword  = candidate["keyword"]

        log.info(
            f"[Quoter] Trying — score={score:.1f} likes={likes} "
            f"followers={followers:,} {age_str} "
            f"keyword='{keyword}' "
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
            record_like(f"quoted_{tweet_id}")

            log.success(
                f"[Quoter] Quote tweet posted ✅ — "
                f"our_tweet={new_id} quoting={tweet_id} "
                f"score={score:.1f} "
                f"content='{quote_text[:60]}…'"
            )
            log.info("[Quoter] Quote tweet cycle complete.")
            return

        except tweepy.errors.Forbidden:
            log.warning(
                f"[Quoter] Tweet {tweet_id} cannot be quoted (restricted) — "
                "marking skipped, trying next."
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
                f"[Quoter] Unexpected error on {tweet_id}: "
                f"{type(exc).__name__}: {exc}"
            )
            continue

    log.info(
        f"[Quoter] Tried all {len(all_candidates)} candidate(s) — "
        "none could be posted."
    )
    log.info("[Quoter] Quote tweet cycle complete.")
