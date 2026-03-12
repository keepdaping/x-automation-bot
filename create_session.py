from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    
    browser = p.chromium.launch(headless=False)

    context = browser.new_context()

    page = context.new_page()

    # open homepage instead of /login
    page.goto("https://x.com", timeout=60000, wait_until="domcontentloaded")

    print("Browser opened. Login manually.")

    input("After logging in, press ENTER here to save session...")

    context.storage_state(path="session.json")

    print("Session saved to session.json")

    browser.close()
from playwright.sync_api import sync_playwright

CHROME_PROFILE_PATH = r"C:\Users\MAI-WAY\AppData\Local\Google\Chrome\User Data"

with sync_playwright() as p:
    


    context = p.chromium.launch_persistent_context(
        user_data_dir=CHROME_PROFILE_PATH,
        channel="chrome",
        headless=False
    )

    page = context.pages[0] if context.pages else context.new_page()

    page.goto("https://x.com")

    print("Login using your normal Chrome session.")

    input("Press ENTER to save cookies...")

    context.storage_state(path="session.json")

    print("Session saved to session.json")
