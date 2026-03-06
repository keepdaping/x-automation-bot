# main.py
"""
Entry point for the X Automation Bot.

Startup sequence:
  1. Validate all required environment variables.
  2. Initialise the SQLite database.
  3. Authenticate with the Twitter API.
  4. Run one post cycle immediately.
  5. Run one engagement cycle immediately.
  6. Hand off to the scheduler for all recurring cycles.

Scheduled jobs:
  post_job       — every Config.MIN_INTERVAL_MINUTES  (default 90 min)
  engagement_job — every ENGAGEMENT_INTERVAL_MINUTES  (default 30 min)
"""
from config import Config
from database import init_db
from auth import get_client
from generator import generate_post, pick_topic
from moderator import check
from poster import post_tweet
from scheduler import build_scheduler
from engagement import run_engagement_cycle
from logger_setup import log

# How often the engagement cycle fires (independent of the post cycle).
ENGAGEMENT_INTERVAL_MINUTES = 30


def run_post_cycle(client) -> None:
    """
    Single post cycle:
      pick topic → generate (AI or fallback) → moderate → post.

    Retries up to 3 times if moderation rejects the draft.
    Each retry picks a fresh topic and regenerates from scratch.
    """
    log.info("─" * 50)
    log.info("Starting post cycle")

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

    # ── 4. Run one post cycle immediately on startup ──────────────────────
    run_post_cycle(client)

    # ── 5. Run one engagement cycle immediately on startup ────────────────
    run_engagement_cycle(client)

    # ── 6. Build scheduler and register both jobs ─────────────────────────
    scheduler = build_scheduler(lambda: run_post_cycle(client))

    scheduler.add_job(
        lambda: run_engagement_cycle(client),
        trigger="interval",
        minutes=ENGAGEMENT_INTERVAL_MINUTES,
        id="engagement_job",
        max_instances=1,   # never overlap with itself
        coalesce=True,     # if a run was missed, fire once — not multiple times
    )
    log.info(f"Engagement cycle scheduled — every {ENGAGEMENT_INTERVAL_MINUTES} minutes.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot shut down cleanly.")


if __name__ == "__main__":
    main()
