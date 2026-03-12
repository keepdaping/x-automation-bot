import time
import random
import signal
import sys

from browser.browser_manager import BrowserManager
from core.engagement import run_engagement
from logger_setup import log
from utils.performance_tracker import PerformanceTracker


class BotController:
    def __init__(self):
        self.browser = None
        self.page = None
        self.tracker = PerformanceTracker()
        self.running = True
        
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
            log.info("X AUTOMATION BOT STARTING")
            log.info("="*70)
            
            # Initialize browser
            self.browser = BrowserManager()
            self.page = self.browser.start()
            
            # Verify authentication
            if not self.browser.check_authenticated():
                log.error("❌ Not authenticated to X. Please run: python create_session.py")
                return False
            
            log.info("✓ Bot authenticated and ready")
            log.info("\nStarting engagement loop (Press Ctrl+C to stop)\n")
            
            # Main loop
            cycle_count = 0
            while self.running:
                cycle_count += 1
                log.info(f"\n--- CYCLE {cycle_count} ---")
                
                try:
                    # Run engagement actions
                    run_engagement(self.page)
                    self.tracker.record_cycle(success=True)
                except Exception as e:
                    log.error(f"Cycle error: {e}")
                    self.tracker.record_cycle(success=False)
                    # Try to recover
                    try:
                        self.page = self.browser.restart()
                    except:
                        log.error("Failed to restart browser, exiting")
                        return False
                
                # Sleep between cycles
                sleep_time = self.tracker.get_recommended_sleep()
                log.info(f"✓ Cycle complete. Sleeping {sleep_time}s")
                
                # Sleep in small intervals to allow Ctrl+C
                remaining = sleep_time
                while remaining > 0 and self.running:
                    time.sleep(min(1, remaining))
                    remaining -= 1
            
            return True
        
        except KeyboardInterrupt:
            log.info("\n\nKeyboard interrupt received")
            return True
        except Exception as e:
            log.error(f"Fatal error: {e}", exc_info=True)
            return False
        finally:
            if self.browser:
                self.browser.close()
            self.tracker.print_summary()
            log.info("Bot exited")


def main():
    controller = BotController()
    success = controller.start()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()