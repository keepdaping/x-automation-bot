import time
from config import X_USERNAME, X_PASSWORD

def login(page):

    # open X login page with longer timeout
    page.goto(
        "https://x.com/login",
        timeout=60000,
        wait_until="domcontentloaded"
    )

    # wait for username field
    page.wait_for_selector('input[name="text"]', timeout=60000)

    page.fill('input[name="text"]', X_USERNAME)
    page.keyboard.press("Enter")

    time.sleep(3)

    # password
    page.wait_for_selector('input[name="password"]', timeout=60000)

    page.fill('input[name="password"]', X_PASSWORD)
    page.keyboard.press("Enter")

    time.sleep(5)

    print("Logged into X successfully")