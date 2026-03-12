from playwright.sync_api import sync_playwright
import os
import json
import time
from browser.stealth import (
    inject_stealth_script,
    dismiss_cookie_modal,
    LAUNCH_ARGS,
    BROWSER_CONTEXT_OPTIONS,
    CONTEXT_EXTRA_OPTIONS,
)
from logger_setup import log

# Use a dedicated automation profile instead of main Chrome profile to avoid slowdowns
CHROME_PROFILE = os.path.expanduser(
    "~/.config/x-bot-automation/chrome"  # Linux/Mac compatible path
)
SESSION_FILE = "session.json"


class BrowserManager:
    def __init__(self):
        self.p = None
        self.context = None
        self.page = None
        self.retry_count = 0
        self.max_retries = 3

    def start(self):
        """Launch browser and load authenticated session"""
        try:
            log.info("Starting browser...")
            self.p = sync_playwright().start()

            # Merge all context options
            context_opts = {**BROWSER_CONTEXT_OPTIONS, **CONTEXT_EXTRA_OPTIONS}

            # Launch persistent context
            self.context = self.p.chromium.launch_persistent_context(
                user_data_dir=CHROME_PROFILE,
                channel="chrome",
                headless=True,
                timeout=30000,  # 30 second timeout
                args=LAUNCH_ARGS,
                **context_opts,
            )

            log.info("✓ Browser launched successfully")

            # Load cookies from session.json if available
            if os.path.exists(SESSION_FILE):
                try:
                    with open(SESSION_FILE, "r") as f:
                        session_data = json.load(f)
                        cookies = session_data.get("cookies", [])
                        
                        if cookies:
                            self.context.add_cookies(cookies)
                            log.info(f"✓ Loaded {len(cookies)} cookies from session.json")
                        else:
                            log.warning("⚠ session.json found but no cookies present")
                except Exception as e:
                    log.error(f"Error loading session: {e}")

            # Get or create page
            self.page = (
                self.context.pages[0] if self.context.pages else self.context.new_page()
            )

            # Inject stealth scripts
            inject_stealth_script(self.page)

            # Navigate to X home
            log.info("Loading X.com...")
            try:
                self.page.goto(
                    "https://x.com/home",
                    wait_until="domcontentloaded",
                    timeout=15000,
                )
            except:
                # Fallback if /home doesn't work
                self.page.goto(
                    "https://x.com",
                    wait_until="domcontentloaded",
                    timeout=15000,
                )

            time.sleep(2)

            # Dismiss overlays
            log.info("Dismissing modals...")
            dismiss_cookie_modal(self.page)
            time.sleep(1)

            log.info("✓ Browser ready for automation")
            return self.page

        except Exception as e:
            log.error(f"Failed to start browser: {e}")
            if self.retry_count < self.max_retries:
                self.retry_count += 1
                log.info(f"Retrying... ({self.retry_count}/{self.max_retries})")
                time.sleep(5)
                return self.start()
            else:
                raise

    def close(self):
        """Gracefully close browser"""
        try:
            if self.context:
                self.context.close()
            if self.p:
                self.p.stop()
            log.info("Browser closed")
        except Exception as e:
            log.error(f"Error closing browser: {e}")

    def restart(self):
        """Restart browser if needed"""
        log.warning("Restarting browser...")
        self.close()
        time.sleep(2)
        return self.start()

    def check_authenticated(self):
        """Check if currently authenticated to X"""
        try:
            # If we can access home feed, we're authenticated
            self.page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=10000)
            # Check for home timeline
            self.page.wait_for_selector("[data-testid='primaryColumn']", timeout=5000)
            return True
        except:
            return False
