import time
from config import X_USERNAME, X_PASSWORD

def login(page):

    page.goto("https://x.com/login")

    page.wait_for_selector('input[name="text"]')

    page.fill('input[name="text"]', X_USERNAME)

    page.keyboard.press("Enter")

    time.sleep(2)

    page.fill('input[name="password"]', X_PASSWORD)

    page.keyboard.press("Enter")

    time.sleep(5)