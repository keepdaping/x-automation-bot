from playwright.sync_api import sync_playwright

class BrowserManager:

    def start(self):

        self.p = sync_playwright().start()

        browser = self.p.chromium.launch(headless=True)

        context = browser.new_context(
            storage_state="session.json"
        )

        page = context.new_page()

        return page