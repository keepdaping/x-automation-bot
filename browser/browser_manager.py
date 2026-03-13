from playwright.sync_api import sync_playwright
import os
import json
import time
import platform
from browser.stealth import (
    inject_stealth_script,
    dismiss_cookie_modal,
    LAUNCH_ARGS,
    BROWSER_CONTEXT_OPTIONS,
    CONTEXT_EXTRA_OPTIONS,
)
from logger_setup import log

# Use a dedicated automation profile with Windows-compatible path
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
        """Launch browser and load authenticated session"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                log.info("Starting browser...")
                
                # Ensure Chrome profile directory exists
                os.makedirs(CHROME_PROFILE, exist_ok=True)
                
                self.p = sync_playwright().start()

                # Merge all context options
                context_opts = {**BROWSER_CONTEXT_OPTIONS, **CONTEXT_EXTRA_OPTIONS}

                # Launch persistent context
                # Playwright may take longer to start in constrained CI environments.
                # Increase timeout to avoid premature failures like "Timeout 30000ms exceeded".
                self.context = self.p.chromium.launch_persistent_context(
                    user_data_dir=CHROME_PROFILE,
                    channel="chrome",
                    headless=True,
                    timeout=120000,  # 120 second timeout
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
                
                # Clean up before retry
                try:
                    if self.context:
                        self.context.close()
                    if self.p:
                        self.p.stop()
                except:
                    pass
                
                if attempt < max_retries - 1:
                    log.info(f"Retrying... ({attempt + 1}/{max_retries})")
                    time.sleep(5)
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
            # Navigate to home
            self.page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=15000)
            time.sleep(1)
            
            # Multiple indicators of authentication
            try:
                # Check 1: Look for compose button (appears only when authenticated)
                self.page.wait_for_selector("[data-testid='tweetButton'], button:has-text('Post')", timeout=3000)
                log.info("✓ Found compose button - authenticated")
                return True
            except:
                pass
            
            try:
                # Check 2: Look for the home timeline (primary column)
                self.page.wait_for_selector("[data-testid='primaryColumn'], [role='main']", timeout=3000)
                log.info("✓ Found timeline - authenticated")
                return True
            except:
                pass
            
            try:
                # Check 3: Look for the sidebar with profile
                self.page.wait_for_selector("[data-testid='SideNav'], aside", timeout=3000)
                # Make sure there's content in sidebar (user is logged in)
                sidebar = self.page.query_selector("aside")
                if sidebar and sidebar.is_visible():
                    log.info("✓ Found visible sidebar - authenticated")
                    return True
            except:
                pass
            
            # Check 4: Verify we're NOT on the login page
            try:
                self.page.wait_for_selector("[data-testid='loginButton'], [data-testid='signupButton']", timeout=2000)
                # If login/signup button is visible, we're NOT authenticated
                log.warning("⚠ Login/signup buttons visible - not authenticated")
                return False
            except:
                # Login buttons not found, which is good
                log.info("✓ No login buttons - likely authenticated")
                return True
            
        except Exception as e:
            log.error(f"Authentication check failed: {e}")
            return False
