"""
X Automation Bot - Main Entry Point

FIXED: 
- Engagement loop no longer nested under DAILY_TWEET_ENABLED check
- Daily tweet and engagement are independent code paths
- Proper timezone handling throughout

ADDED:
- FeedbackTracker initialization
- Scheduler for periodic outcome checking (follows, replies back, DMs)
"""



import time
import random
import signal
import sys
from datetime import datetime, date, timezone

from browser.browser_manager import BrowserManager
from core.engagement import run_engagement
from core.rate_limiter import init_rate_limiter
from core.error_handler import init_error_handler
from core.session_manager import init_session_manager
from core.scheduler import start_scheduler  # NEW: import scheduler
from config import Config
from database import init_db, count_posts_today, count_daily_posts_today, get_last_daily_post_date, has_posted_today, is_duplicate, save_post
from logger_setup import log
from actions.tweet import post_tweet
from content.engine import get_content_engine
from feedback import FeedbackTracker  # NEW: for manual stats if needed


class BotController:
    def __init__(self):
        self.browser = None
        self.page = None
        self.running = True
        self.daily_posted_today = False
        self.last_daily_post_date = None
        self.daily_posting_time = None
        self.last_generated_day = None

        self._session_search_topics = []
        self._session_search_index = 0

        # Initialize database
        init_db()

        # Validate config
        try:
            Config.validate()
        except ValueError as e:
            log.error(f"Configuration validation failed: {e}")
            sys.exit(1)

        # Initialize safety systems
        self.rate_limiter = init_rate_limiter(Config)
        self.session_manager = init_session_manager(Config)

        # NEW: Initialize feedback tracker (used in engagement)
        self.feedback_tracker = FeedbackTracker()

        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def shutdown(self, signum, frame):
        log.info("\nShutdown signal received...")
        self.running = False
        if self.browser:
            self.browser.close()
        if hasattr(self, 'feedback_tracker'):
            self.feedback_tracker.close()
        log.info("Bot stopped cleanly")
        sys.exit(0)

    def _refresh_search_topics(self):
        self._session_search_topics = list(getattr(Config, "SEARCH_PHRASES", Config.SEARCH_KEYWORDS))
        random.shuffle(self._session_search_topics)
        self._session_search_index = 0

    def _get_next_search_topic(self) -> str:
        if not self._session_search_topics:
            self._refresh_search_topics()
        if not self._session_search_topics:
            return "AI"
        topic = self._session_search_topics[self._session_search_index % len(self._session_search_topics)]
        self._session_search_index += 1
        return topic

    def _post_daily_tweet(self):
        """Post one original tweet per day.

        Guard order (must ALL pass before the browser is touched):
          1. Hard DB COUNT — authoritative, restart-proof, timezone-proof.
          2. In-memory flag  — fast short-circuit within a running session.
          3. Soft has_posted_today() — date-level sanity check.
        The in-memory flag is set BEFORE save_post() so a save failure never
        allows a second post.
        """
        try:
            # ── Guard 1: hard DB gate (COUNT) ─────────────────────────────────
            if count_daily_posts_today() >= 1:
                log.info("Daily tweet already posted today (DB confirmed) - skipping")
                self.daily_posted_today = True
                return

            # ── Guard 2: in-memory flag ───────────────────────────────────────
            if self.daily_posted_today:
                log.info("Daily tweet already posted today (in-memory) - skipping")
                return

            # ── Guard 3: soft date check ──────────────────────────────────────
            if has_posted_today():
                log.info("Daily tweet already posted today (date check) - skipping")
                self.daily_posted_today = True
                return

            content_engine = get_content_engine()
            topic = self._get_next_search_topic()
            tweet_text = content_engine.generate_daily_tweet(topic)

            if not tweet_text or not tweet_text.strip():
                log.warning("Daily tweet generation returned empty")
                return

            if is_duplicate(tweet_text):
                log.warning("Daily tweet is duplicate - skipping")
                return

            log.info("Posting daily tweet...")
            success = post_tweet(self.page, tweet_text)

            if success:
                # Set the in-memory lock BEFORE save_post so that even if save
                # raises, this session will not attempt another post today.
                self.daily_posted_today = True

                # Resolve pillar name in its own scope so a failure here cannot
                # skip the save_post() call below.
                try:
                    now = datetime.now(timezone.utc)
                    pillar_name = Config.get_content_pillar(now.timetuple().tm_yday)["name"]
                except Exception as pillar_err:
                    log.warning(f"Could not resolve content pillar: {pillar_err} — using 'general'")
                    pillar_name = "general"

                # DB logging is isolated: a save failure is reported but the
                # function still returns cleanly (tweet is already on X).
                try:
                    save_post(tweet_text, None, topic or "daily", "daily", 0.0, pillar=pillar_name)
                    log.info("TWEET SAVED TO DB")
                except Exception as save_err:
                    log.error(f"Daily tweet posted on X but DB save failed: {save_err}")

                log.info(f"✅ Daily tweet posted [{pillar_name}]: {tweet_text}")
            else:
                log.error("Daily tweet posting failed")

        except Exception as e:
            log.error(f"Failed to post daily tweet: {e}")

    def _generate_daily_posting_time(self, current_day):
        """Generate a random posting time within the configured window."""
        start_hour = Config.DAILY_TWEET_START_HOUR_UTC
        end_hour = Config.DAILY_TWEET_END_HOUR_UTC
        random_hour = random.uniform(start_hour, end_hour)
        hour = int(random_hour)
        minute = int((random_hour % 1) * 60)
        second = int(((random_hour % 1) * 60 % 1) * 60)
        self.daily_posting_time = datetime(
            current_day.year, current_day.month, current_day.day,
            hour, minute, second, tzinfo=timezone.utc
        )
        self.last_generated_day = current_day
        log.info(f"Daily posting scheduled for {self.daily_posting_time.strftime('%H:%M:%S')} UTC")

    def _check_and_post_daily(self, current_time, current_day):
        """Check if it's time to post the daily tweet. Independent of engagement."""
        if not Config.DAILY_TWEET_ENABLED:
            return

        # ── New day: reset in-memory state ───────────────────────────────────
        if self.last_daily_post_date != current_day:
            self.daily_posted_today = False
            self.last_daily_post_date = current_day
            self._missed_window_today = False  # reset missed-window flag too

        # ── Fast path: already confirmed posted this session ─────────────────
        if self.daily_posted_today:
            return

        # ── Hard DB gate (catches restarts where in-memory flag was lost) ────
        if count_daily_posts_today() >= 1:
            self.daily_posted_today = True   # sync memory with DB truth
            return

        # ── Soft date check (extra safety layer) ─────────────────────────────
        if has_posted_today():
            self.daily_posted_today = True
            return

        # ── Window already missed this day → do nothing until tomorrow ───────
        if getattr(self, "_missed_window_today", False):
            return

        # ── Generate a posting time for today (once per calendar day) ────────
        if self.last_generated_day != current_day:
            self._generate_daily_posting_time(current_day)

        if self.daily_posting_time is None:
            return

        posting_time = self.daily_posting_time
        if posting_time.tzinfo is None:
            posting_time = posting_time.replace(tzinfo=timezone.utc)

        inside_window = Config.DAILY_TWEET_START_HOUR_UTC <= current_time.hour < Config.DAILY_TWEET_END_HOUR_UTC

        if current_time >= posting_time and inside_window:
            # Time reached and window open — attempt exactly once.
            # _post_daily_tweet() sets self.daily_posted_today = True on success.
            log.info(f"📝 Time to post daily tweet ({current_time.strftime('%H:%M')} UTC)")
            self._post_daily_tweet()

        elif current_time.hour >= Config.DAILY_TWEET_END_HOUR_UTC:
            # Window closed without a post — record the miss and stop retrying
            # for today.  DO NOT reset last_generated_day here; that caused an
            # infinite regeneration loop every cycle.
            log.warning(
                f"[Daily] Posting window closed without a tweet today "
                f"(target was {posting_time.strftime('%H:%M')} UTC). "
                "Will retry tomorrow."
            )
            self._missed_window_today = True

    def start(self):
        """Start the automation bot."""
        try:
            log.info("=" * 70)
            log.info("X AUTOMATION BOT v2 STARTING")
            log.info("=" * 70)

            # Initialize browser
            self.browser = BrowserManager()
            self.page = self.browser.start()

            # Initialize error handler
            self.error_handler = init_error_handler(Config, self.browser)

            # Verify auth
            if not self.browser.check_authenticated():
                log.error("❌ Not authenticated. Run session setup first.")
                return False

            log.info("✓ Authenticated and ready")
            log.info("✓ Engagement mode: AgentController (ReAct — Reason + Act)")

            # Load daily post state
            self.last_daily_post_date = get_last_daily_post_date()
            self.daily_posted_today = has_posted_today()
            if self.daily_posted_today:
                log.info(f"✓ Daily tweet already posted today")

            # NEW: Start background scheduler for outcome checking
            start_scheduler()

            log.info("\nStarting engagement loop (Ctrl+C to stop)\n")

            cycle_count = 0

            while self.running:
                cycle_count += 1
                current_time = datetime.now(timezone.utc)
                current_day = current_time.date()

                # Check if should be active
                if not self.session_manager.should_be_active():
                    self.session_manager.print_status()
                    wait_sec = self.session_manager.get_time_until_active()
                    if wait_sec > 0:
                        log.info(f"⏰ Sleeping {wait_sec/3600:.1f}h until next active window")
                        remaining = wait_sec
                        while remaining > 0 and self.running:
                            time.sleep(min(300, remaining))
                            remaining -= 300
                    continue

                # Start session if needed
                if self.session_manager.current_state.value != "active":
                    self.session_manager.start_session()
                    self._refresh_search_topics()

                # ===== DAILY TWEET (independent of engagement) =====
                self._check_and_post_daily(current_time, current_day)

                # ===== ENGAGEMENT (independent of daily tweet) =====
                if not self.session_manager.should_take_action():
                    self.session_manager.print_status()
                    time.sleep(random.uniform(5, 15))
                    continue

                # Run engagement cycle
                cycle_start_time = time.time()
                info = self.session_manager.get_session_info()
                progress = ""
                if info.get("actions") is not None:
                    progress = f" (Session {info['percentage']}%: {info['actions']}/{info['target_actions']} actions)"

                log.info(f"\n{'#'*50}")
                log.info(f"# CYCLE {cycle_count}{progress}")
                log.info(f"{'#'*50}\n")

                try:
                    run_engagement(
                        self.page,
                        Config,
                        keyword=None,  # engagement.py drives intelligent phrase selection
                        feedback_tracker=self.feedback_tracker
                    )
                    self.session_manager.record_action()
                except Exception as e:
                    log.error(f"Cycle error: {e}")
                    try:
                        self.page = self.browser.restart()
                    except Exception:
                        log.error("Failed to restart browser")
                        return False

                # Check session completion
                if self.session_manager.is_session_complete():
                    self.session_manager.end_session()
                    continue

                # Natural pacing
                cycle_elapsed = time.time() - cycle_start_time
                min_wait = random.uniform(
                    self.session_manager.min_action_interval_sec,
                    self.session_manager.max_action_interval_sec
                )
                wait_time = max(0, min_wait - cycle_elapsed)
                if wait_time > 0:
                    log.info(f"✓ Pausing {wait_time:.0f}s (natural pacing)")
                    time.sleep(wait_time)

            return True

        except KeyboardInterrupt:
            log.info("Bot interrupted by user")
            return True


if __name__ == "__main__":
    controller = BotController()
    success = controller.start()
    sys.exit(0 if success else 1)