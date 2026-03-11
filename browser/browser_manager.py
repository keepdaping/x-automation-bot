from playwright.sync_api import sync_playwright
from config import HEADLESS


class BrowserManager:

    def start(self):

        self.p = sync_playwright().start()

        context = self.p.chromium.launch_persistent_context(
            user_data_dir="./user_data",
            headless=False,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        page = context.pages[0] if context.pages else context.new_page()

        return page