# main.py
"""
Entry point for the X Automation Bot.
Designed for GitHub Actions — runs once and exits.

Startup sequence:
  1. Validate all required environment variables.
  2. Initialise the SQLite database.
  3. Authenticate with the Twitter API.
  4. Decide: post a thread OR a single tweet (every 3rd run = thread).
  5. Run one engagement cycle.
  6. Run one quote tweet cycle.
  7. Exit cleanly.

GitHub Actions cron handles all scheduling.
"""
import os
from config import Config
from database import init_db
from auth import get_client
from generator import generate_post, pick_topic
from moderator import check
from poster import post_tweet
from thread_generator import generate_thread
from thread_poster import post_thread
from quoter import run_quote_tweet_cycle
from engagement import run_engagement_cycle
from logger_setup import log


# ── Run counter helpers ───────────────────────────────────────────────────────

_COUNTER_FILE = "data/run_counter.txt"


def _get_run_count() -> int:
    try:
        with open(_COUNTER_FILE, "r") as f:
            return int(f.read().strip())
    except Exception:
        return 0


def _save_run_count(count: int) -> None:
    try:
        os.makedirs("data", exist_ok=True)
        with open(_COUNTER_FILE, "w") as f:
            f.write(str(count))
    except Exception as exc:
        log.warning(f"Could not save run counter: {exc}")


# ── Post cycles ───────────────────────────────────────────────────────────────

def run_post_cycle(client) -> None:
    """
    Every 3rd run posts a thread for higher reach.
    Other runs post a single tweet.
    """
    count = _get_run_count() + 1
    _save_run_count(count)

    log.info(f"Run #{count} — {'THREAD' if count % 3 == 0 else 'SINGLE TWEET'} cycle")

    if count % 3 == 0:
        _run_thread_cycle(client)
    else:
        _run_single_tweet_cycle(client)


def _run_thread_cycle(client) -> None:
    """Generate and post a multi-tweet thread."""
    log.info("─" * 50)
    log.info("Starting THREAD cycle")

    topic = pick_topic()
    log.info(f"Thread topic: '{topic}'")

    tweets, source = generate_thread(topic)
    if tweets:
        success = post_thread(client, tweets, source, topic)
        if not success:
            log.warning("[Thread] Thread failed — falling back to single tweet.")
            _run_single_tweet_cycle(client)
    else:
        log.error("Thread generation returned empty — falling back to single tweet.")
        _run_single_tweet_cycle(client)


def _run_single_tweet_cycle(client) -> None:
    """Post a single tweet with moderation retries."""
    log.info("─" * 50)
    log.info("Starting SINGLE TWEET cycle")

    for attempt in range(1, 4):
        topic = pick_topic()
        log.info(f"[{attempt}/3] Topic: '{topic}'")

        text, source = generate_post(topic)
        safe, reason = check(text)

        if safe:
            post_tweet(client, text, source, topic)
            return

        log.warning(f"[{attempt}/3] Moderation failed — reason: {reason} — retrying…")

    log.error("All 3 moderation attempts failed. Skipping this cycle.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 50)
    log.info("X Automation Bot starting…")

    # ── 1. Validate environment ───────────────────────────────────────────
    try:
        Config.validate()
    except ValueError as exc:
        log.critical(str(exc))
        raise SystemExit(1)

    # ── 2. Initialise database ────────────────────────────────────────────
    init_db()

    # ── 3. Authenticate ───────────────────────────────────────────────────
    try:
        client = get_client()
    except RuntimeError as exc:
        log.critical(str(exc))
        raise SystemExit(1)

    # ── 4. Post tweet or thread ───────────────────────────────────────────
    run_post_cycle(client)

    # ── 5. Engagement cycle ───────────────────────────────────────────────
    run_engagement_cycle(client)

    # ── 6. Quote tweet cycle ──────────────────────────────────────────────
    run_quote_tweet_cycle(client)

    # ── 7. Exit cleanly ───────────────────────────────────────────────────
    log.info("Cycle complete. Exiting cleanly.")


if __name__ == "__main__":
    main()
