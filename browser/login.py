import time
from config import X_USERNAME, X_PASSWORD

def login(page):

    # open X homepage
    page.goto("https://x.com", timeout=60000, wait_until="domcontentloaded")

    # click sign in
    page.get_by_role("link", name="Sign in").click()

    # wait for username field
    page.wait_for_selector('input[autocomplete="username"]', timeout=60000)

    # enter username
    page.fill('input[autocomplete="username"]', X_USERNAME)
    page.keyboard.press("Enter")

    time.sleep(3)

    # wait for password
    page.wait_for_selector('input[name="password"]', timeout=60000)

    page.fill('input[name="password"]', X_PASSWORD)
    page.keyboard.press("Enter")

    time.sleep(5)

    print("Logged into X successfully")