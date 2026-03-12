from playwright.sync_api import sync_playwright
import os
import json

# Use a dedicated automation profile instead of main Chrome profile to avoid slowdowns
CHROME_PROFILE = r"C:\Users\MAI-WAY\AppData\Local\Google\Chrome\AutomationBot"
SESSION_FILE = "session.json"

class BrowserManager:

    def start(self):

        self.p = sync_playwright().start()

        # Load existing session if available
        initial_storage_state = None
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, 'r') as f:
                    initial_storage_state = json.load(f)
                print("✓ Loaded existing session from session.json")
            except Exception as e:
                print(f"Warning: Could not load session file: {e}")

        context = self.p.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE,
            channel="chrome",
            headless=True,
            timeout=300000,  # Increase timeout to 5 minutes
            storage_state=initial_storage_state,  # Load saved session
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",  # Hide automation signals
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-component-update",
                "--disable-extensions",
                "--disable-sync",
                "--disable-default-apps",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-breakpad",
                "--disable-client-side-phishing-detection",
                "--disable-hang-monitor",
                "--disable-popup-blocking",
                "--disable-prompt-on-repost",
                "--enable-automation=false",
            ]
        )
        
        # Inject stealth script to hide automation
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            window.chrome = {
                runtime: {}
            };
        """)

        page = context.pages[0] if context.pages else context.new_page()

        page.goto("https://x.com", wait_until="networkidle")

        return page