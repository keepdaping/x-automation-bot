import time
from config import X_USERNAME, X_PASSWORD


def login(page):

    print("Opening login page...")

    page.goto(
        "https://x.com/i/flow/login",
        timeout=60000,
        wait_until="domcontentloaded"
    )

    # wait for any input field to appear
    page.wait_for_selector("input", timeout=60000)

    print("Typing username...")

    username = page.locator('input[name="text"]').first
    username.fill(X_USERNAME)

    page.keyboard.press("Enter")

    time.sleep(3)

    print("Typing password...")

    password = page.locator('input[name="password"]').first
    password.fill(X_PASSWORD)

    page.keyboard.press("Enter")

    time.sleep(6)

    print("Logged into X successfully")