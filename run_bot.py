import time
import random

from browser.browser_manager import BrowserManager
from core.engagement import run_engagement


def main():

    browser = BrowserManager()

    page = browser.start()

    while True:

        run_engagement(page)

        sleep_time = random.randint(90, 180)

        print(f"Cycle complete. Sleeping {sleep_time}s")

        time.sleep(sleep_time)


if __name__ == "__main__":
    main()