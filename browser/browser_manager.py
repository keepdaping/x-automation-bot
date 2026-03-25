"""Browser lifecycle management."""

from playwright.sync_api import sync_playwright
import os
import json
import time
import platform
from browser.stealth import inject_stealth_script, dismiss_cookie_modal, LAUNCH_ARGS, BROWSER_CONTEXT_OPTIONS, CONTEXT_EXTRA_OPTIONS
from logger_setup import log

if platform.system() == "Windows":
    CHROME_PROFILE = os.path.expanduser(r"~\AppData\Local\x-bot-automation\chrome")
else:
    CHROME_PROFILE = os.path.expanduser("~/.config/x-bot-automation/chrome")

SESSION_FILE = "session.json"


class BrowserManager:
    def __init__(self):
        self.p = None
        self.context = None
        self.page = None

    def start(self):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                log.info("Starting browser...")
                os.makedirs(CHROME_PROFILE, exist_ok=True)
                self.p = sync_playwright().start()
                context_opts = {**BROWSER_CONTEXT_OPTIONS, **CONTEXT_EXTRA_OPTIONS}
                self.context = self.p.chromium.launch_persistent_context(
                    user_data_dir=CHROME_PROFILE, channel="chrome", headless=True,
                    timeout=120000, args=LAUNCH_ARGS, **context_opts,
                )
                log.info("✓ Browser launched")

                if os.path.exists(SESSION_FILE):
                    try:
                        with open(SESSION_FILE, "r") as f:
                            cookies = json.load(f).get("cookies", [])
                            if cookies:
                                self.context.add_cookies(cookies)
                                log.info(f"✓ Loaded {len(cookies)} cookies")
                    except Exception as e:
                        log.error(f"Session load error: {e}")

                self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
                inject_stealth_script(self.page)

                try:
                    self.page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=15000)
                except Exception:
                    self.page.goto("https://x.com", wait_until="load", timeout=60000)
                time.sleep(2)
                dismiss_cookie_modal(self.page)
                time.sleep(1)
                log.info("✓ Browser ready")
                return self.page
            except Exception as e:
                log.error(f"Browser start failed: {e}")
                try:
                    if self.context: self.context.close()
                    if self.p: self.p.stop()
                except Exception:
                    pass
                if attempt < max_retries - 1:
                    log.info(f"Retrying... ({attempt + 1}/{max_retries})")
                    time.sleep(5)
                else:
                    raise

    def close(self):
        try:
            if self.context: self.context.close()
            if self.p: self.p.stop()
        except Exception:
            pass

    def restart(self):
        log.warning("Restarting browser...")
        self.close()
        time.sleep(2)
        return self.start()

    def check_authenticated(self):
        try:
            self.page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=15000)
            time.sleep(1)
            for selector in ["[data-testid='tweetButton']", "[data-testid='primaryColumn']"]:
                try:
                    self.page.wait_for_selector(selector, timeout=3000)
                    log.info("✓ Authenticated")
                    return True
                except Exception:
                    continue
            try:
                self.page.wait_for_selector("[data-testid='loginButton']", timeout=2000)
                log.warning("Not authenticated - login page detected")
                return False
            except Exception:
                return True
        except Exception as e:
            log.error(f"Auth check failed: {e}")
            return False

    # =====================================================================
    # NEW: Outcome checking methods for feedback loop
    # =====================================================================

    def check_is_following(self, user_handle: str) -> bool:
        """Check if we are currently following this user (safe, used by feedback)."""
        try:
            self.page.goto(f"https://x.com/{user_handle}", wait_until="domcontentloaded", timeout=8000)
            time.sleep(1.5)
            following_btn = self.page.locator("div[role='button']:has-text('Following')").first
            if following_btn and following_btn.is_visible(timeout=3000):
                return True
            return False
        except Exception:
            return False

    def check_user_replied(self, reply_id: str, user_handle: str) -> bool:
        """Check if the user replied to our reply (basic implementation)."""
        try:
            if not reply_id:
                return False
            self.page.goto(f"https://x.com/i/status/{reply_id}", wait_until="domcontentloaded", timeout=8000)
            time.sleep(2)
            # Look for any reply from the user in the thread
            user_reply = self.page.locator(f"article:has-text('@{user_handle}')").first
            return user_reply.is_visible(timeout=3000)
        except Exception:
            return False

    def check_for_dm(self, user_handle: str) -> bool:
        """Placeholder for DM detection (harder - high detection risk)."""
        # TODO: Implement safely later (e.g. notifications page scan)
        return False