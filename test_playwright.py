from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:

    browser = p.chromium.launch(headless=False)

    page = browser.new_page()

    page.goto("https://x.com", timeout=60000, wait_until="domcontentloaded")

    print("Browser opened successfully")

    time.sleep(20)

    browser.close()