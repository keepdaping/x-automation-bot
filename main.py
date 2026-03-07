# main.py
"""
Entry point for the X Automation Bot.
Designed for GitHub Actions — runs once and exits.

Startup sequence:
  1. Validate all required environment variables.
  2. Initialise the SQLite database.
  3. Authenticate with the Twitter API.
  4. Run one post cycle.
  5. Run one engagement cycle.
  6. Exit cleanly.

GitHub Actions cron handles all scheduling.
"""
from config import Config
from database import init_db
from auth import get_client
from generator import generate_post, pick_topic
from moderator import check
from poster import post_tweet
from engagement import run_engagement_cycle
from logger_setup import log


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

    # ── 4. Run one post cycle ─────────────────────────────────────────────
    run_post_cycle(client)

    # ── 5. Run one engagement cycle ───────────────────────────────────────
    run_engagement_cycle(client)

    # ── 6. Exit cleanly — GitHub Actions handles scheduling ───────────────
    log.info("Cycle complete. Exiting cleanly.")


if __name__ == "__main__":
    main()
