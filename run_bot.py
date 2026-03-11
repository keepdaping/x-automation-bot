from browser.browser_manager import BrowserManager
from browser.login import login
from core.engagement import run_engagement

def main():

    browser = BrowserManager()

    page = browser.start()

    #login(page)

    run_engagement(page)

if __name__ == "__main__":
    main()