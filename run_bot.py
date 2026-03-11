import time

from browser.browser_manager import BrowserManager
from core.engagement import run_engagement


def main():

    browser = BrowserManager()

    page = browser.start()

    while True:

        run_engagement(page)

        print("Cycle complete. Sleeping...")

        time.sleep(120)


if __name__ == "__main__":
    main()