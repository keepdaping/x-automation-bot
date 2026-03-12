from playwright.sync_api import sync_playwright

CHROME_PROFILE = r"C:\Users\MAI-WAY\AppData\Local\Google\Chrome\User Data"

class BrowserManager:

    def start(self):

        self.p = sync_playwright().start()

        context = self.p.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE,
            channel="chrome",
            headless=False,
            args=["--start-maximized"]
        )

        page = context.pages[0] if context.pages else context.new_page()

        page.goto("https://x.com")

        return page