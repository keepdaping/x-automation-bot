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
                    self.page.goto("https://x.com", wait_until="domcontentloaded", timeout=15000)
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
