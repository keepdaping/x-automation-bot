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
from config import Config
from database import init_db, count_posts_today, get_last_daily_post_date, has_posted_today, is_duplicate, save_post
from logger_setup import log
from utils.performance_tracker import PerformanceTracker
from actions.tweet import post_tweet
from content.engine import get_content_engine


class BotController:
    def __init__(self):
        self.browser = None
        self.page = None
        self.tracker = PerformanceTracker()
        self.running = True
        self.daily_posted_today = False
        self.last_daily_post_date = None
        self.daily_posting_time = None
        self.last_generated_day = None

        # Per-session randomized search topics (to avoid predictable ordering)
        self._session_search_topics = []
        self._session_search_index = 0

        # Initialize databases
        init_db()  # Initialize main bot database (posts, replies, etc.)
        
        # Validate configuration BEFORE starting bot
        # This must happen at startup, not import time, to allow GitHub Actions
        # to pass environment variables via secrets
        try:
            Config.validate()
        except ValueError as e:
            log.error(f"Configuration validation failed: {e}")
            sys.exit(1)
        
        # Initialize safety systems
        self.rate_limiter = init_rate_limiter(Config)
        self.session_manager = init_session_manager(Config)
        
        # Handle graceful shutdown
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
    
    def shutdown(self, signum, frame):
        log.info("\n\nShutdown signal received, closing browser...")
        self.running = False
        if self.browser:
            self.browser.close()
        log.info("Bot stopped cleanly")
        sys.exit(0)

    def _refresh_search_topics(self):
        """Shuffle search keywords each session to avoid predictable search patterns."""
        self._session_search_topics = list(Config.SEARCH_KEYWORDS)
        random.shuffle(self._session_search_topics)
        self._session_search_index = 0
        log.debug(f"Shuffled search topics for session: {self._session_search_topics}")

    def _get_next_search_topic(self) -> str:
        """Get the next search topic for this session (rotating, shuffled).

        Falls back to a random keyword if none are configured.
        """
        if not self._session_search_topics:
            self._refresh_search_topics()

        if not self._session_search_topics:
            return "AI"

        topic = self._session_search_topics[self._session_search_index % len(self._session_search_topics)]
        self._session_search_index += 1
        return topic

    def _post_daily_tweet(self):
        """Post one original tweet per day during the configured window."""
        try:
            # Generate tweet content
            content_engine = get_content_engine()
            topic = self._get_next_search_topic()
            tweet_text = content_engine.generate_daily_tweet(topic)

            if has_posted_today():
                log.info("Daily tweet already posted today (persistent guard) - skipping")
                self.daily_posted_today = True
                return

            if not tweet_text or not tweet_text.strip():
                log.warning("Daily tweet generation returned empty; skipping")
                return

            if is_duplicate(tweet_text):
                log.warning("Daily tweet is duplicate of previous post; skipping")
                return

            log.info("Posting daily tweet...")
            post_tweet(self.page, tweet_text)

            save_post(tweet_text, None, topic or "daily", "daily", 0.0)
            self.daily_posted_today = True
            log.info(f"✅ Daily tweet posted: {tweet_text}")

        except Exception as e:
            log.error(f"Failed to post daily tweet: {e}")
    
    def start(self):
        """Start the automation bot"""
        try:
            log.info("="*70)
            log.info("X AUTOMATION BOT STARTING - PRODUCTION BUILD")
            log.info("="*70)
            
            # Initialize browser
            self.browser = BrowserManager()
            self.page = self.browser.start()
            
            # Initialize error handler (needs browser for recovery)
            self.error_handler = init_error_handler(Config, self.browser)
            
            # Verify authentication
            if not self.browser.check_authenticated():
                log.error("❌ Not authenticated to X. Please run: python create_session.py")
                return False
            
            log.info("✓ Bot authenticated and ready")
            log.info("✓ Rate limiter initialized")
            log.info("✓ Error handler initialized")
            log.info("✓ Session manager initialized")

            # Persistent daily tweet guard
            self.last_daily_post_date = get_last_daily_post_date()
            self.daily_posted_today = has_posted_today()
            if self.daily_posted_today:
                log.info(f"✓ Daily tweet already posted today ({self.last_daily_post_date})")

            log.info("\nStarting engagement loop with human-like sessions (Press Ctrl+C to stop)\n")
            
            # Main loop - session-driven engagement
            cycle_count = 0
            while self.running:
                cycle_count += 1
                
                # Check if should be active (within active hours, not in break)
                if not self.session_manager.should_be_active():
                    # Outside active hours or in break - sleep until next active window
                    self.session_manager.print_status()
                    wait_sec = self.session_manager.get_time_until_active()
                    
                    if wait_sec > 0:
                        log.info(f"⏰ Sleeping until next active window ({wait_sec/3600:.1f} hours)...")
                        # Sleep in 5-minute intervals to allow Ctrl+C
                        remaining = wait_sec
                        while remaining > 0 and self.running:
                            time.sleep(min(300, remaining))
                            remaining -= 300
                    continue
                
                # Start session if not already in one
                if self.session_manager.current_state.value != "active":
                    self.session_manager.start_session()
                    self._refresh_search_topics()
                
                # Reset daily post flag if the day changed (UTC)
                current_time = datetime.now(timezone.utc)
                current_day = current_time.date()
                if self.last_daily_post_date != current_day:
                    self.daily_posted_today = False
                    self.last_daily_post_date = current_day

                # Generate daily posting time if new day
                if self.last_generated_day != current_day:
                    start_hour = Config.DAILY_TWEET_START_HOUR_UTC
                    end_hour = Config.DAILY_TWEET_END_HOUR_UTC
                    random_hour = random.uniform(start_hour, end_hour)
                    hour = int(random_hour)
                    minute = int((random_hour % 1) * 60)
                    second = int(((random_hour % 1) * 60 % 1) * 60)
                    self.daily_posting_time = datetime(current_day.year, current_day.month, current_day.day, hour, minute, second, tzinfo=timezone.utc)
                    self.last_generated_day = current_day
                    log.info(f"Generated daily posting time for {current_day}: {self.daily_posting_time}")

                # Try to post a daily tweet at the scheduled time
                if Config.DAILY_TWEET_ENABLED:
                    if (
                        not self.daily_posted_today
                        and not has_posted_today()
                        and current_time >= self.daily_posting_time
                        and Config.DAILY_TWEET_START_HOUR_UTC <= current_time.hour < Config.DAILY_TWEET_END_HOUR_UTC
                    ):
                        log.info(f"Posting daily tweet at scheduled time: {current_time}")
                        self._post_daily_tweet()
    # elif not self.daily_posted_today and current_time < self.daily_posting_time:
                        #     log.info(f"Waiting for daily posting time: {self.daily_posting_time}")

                    # Check if should take action based on natural pacing
                    if not self.session_manager.should_take_action():
                        # Too soon since last action - take a natural pause
                        self.session_manager.print_status()
                        self.tracker.record_cycle(success=True, action_count=0)
                        time.sleep(random.uniform(5, 15))  # Natural pause
                        continue
                    
                    # Run engagement cycle
                    cycle_start_time = time.time()
                    log.info(f"\n{'#'*70}")
                    log.info(f"# ENGAGEMENT CYCLE {cycle_count}")
                    
                    # Show session progress
                    info = self.session_manager.get_session_info()
                    if info.get("actions") is not None:
                        progress = f"(Session {info['percentage']}%: {info['actions']}/{info['target_actions']} actions)"
                        log.info(f"# {progress}")
                    log.info(f"{'#'*70}\n")
                    
                    try:
                        # Run engagement actions with rate limiting
                        run_engagement(self.page, Config, keyword=self._get_next_search_topic())
                        
                        # Record action in session
                        self.session_manager.record_action()
                        self.tracker.record_cycle(success=True, action_count=1)
                    
                    except Exception as e:
                        log.error(f"Cycle error: {e}")
                        self.tracker.record_cycle(success=False)
                        
                        # Try to recover
                        try:
                            log.warning("Attempting to recover...")
                            self.page = self.browser.restart()
                        except:
                            log.error("Failed to restart browser, exiting")
                            return False
                    
                    # Check if session is complete
                    if self.session_manager.is_session_complete():
                        # End session and take break
                        self.session_manager.end_session()
                        continue
                    
                    # Between-action pause for natural pacing
                    cycle_elapsed = time.time() - cycle_start_time
                    min_action_wait = random.uniform(
                        self.session_manager.min_action_interval_sec,
                        self.session_manager.max_action_interval_sec
                    )
                    
                    wait_time = max(0, min_action_wait - cycle_elapsed)
                    if wait_time > 0:
                        log.info(f"✓ Pausing for {wait_time:.0f}s before next action (natural pacing)...")
                        time.sleep(wait_time)
            return True
        
        except KeyboardInterrupt:
            log.info("Bot interrupted by user")


if __name__ == "__main__":
    controller = BotController()
    success = controller.start()
    sys.exit(0 if success else 1)