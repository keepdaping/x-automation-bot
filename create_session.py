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
