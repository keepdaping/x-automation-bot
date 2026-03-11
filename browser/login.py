import time
from config import X_USERNAME, X_PASSWORD

def login(page):

    # Go directly to the login flow
    page.goto(
        "https://x.com/i/flow/login",
        timeout=60000,
        wait_until="domcontentloaded"
    )

    # Wait for username input
    page.wait_for_selector('input[name="text"]', timeout=60000)

    # Enter username
    page.fill('input[name="text"]', X_USERNAME)
    page.keyboard.press("Enter")

    time.sleep(3)

    # Wait for password field
    page.wait_for_selector('input[name="password"]', timeout=60000)

    page.fill('input[name="password"]', X_PASSWORD)
    page.keyboard.press("Enter")

    time.sleep(6)

    print("Logged into X successfully")