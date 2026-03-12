import time
import random
import signal
import sys

from browser.browser_manager import BrowserManager
from core.engagement import run_engagement
from core.rate_limiter import init_rate_limiter
from core.error_handler import init_error_handler
from core.session_manager import init_session_manager
from config import Config
from database import init_db
from logger_setup import log
from utils.performance_tracker import PerformanceTracker


class BotController:
    def __init__(self):
        self.browser = None
        self.page = None
        self.tracker = PerformanceTracker()
        self.running = True
        
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
                    run_engagement(self.page, Config)
                    
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