from playwright.sync_api import sync_playwright
from config import HEADLESS

class BrowserManager:

    def start(self):

        self.p = sync_playwright().start()

        browser = self.p.chromium.launch(
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled"]
        )

        context = browser.new_context()

        page = context.new_page()

        return page