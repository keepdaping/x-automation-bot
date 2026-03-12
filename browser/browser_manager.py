from playwright.sync_api import sync_playwright
import os

# Use a dedicated automation profile instead of main Chrome profile to avoid slowdowns
CHROME_PROFILE = r"C:\Users\MAI-WAY\AppData\Local\Google\Chrome\AutomationBot"

class BrowserManager:

    def start(self):

        self.p = sync_playwright().start()

        context = self.p.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE,
            channel="chrome",
            headless=True,
            timeout=300000,  # Increase timeout to 5 minutes
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",  # Hide automation signals
                "--disable-component-update",
                "--disable-extensions",
                "--disable-sync",
                "--no-default-browser-check"
            ]
        )

        page = context.pages[0] if context.pages else context.new_page()

        page.goto("https://x.com")

        return page