"""
Session creator - opens a stealth browser for you to log in to X.
Saves cookies to session.json when done.
"""

from playwright.sync_api import sync_playwright
import json
import os

bot_profile = os.path.expanduser(r"~\AppData\Local\x-bot-automation\chrome")
os.makedirs(bot_profile, exist_ok=True)

print("=" * 50)
print("X BOT - SESSION CREATOR")
print("=" * 50)
print()
print("A browser window will open.")
print("Log into @KeepdapingB manually.")
print("After you see your timeline, come back here and press Enter.")
print()

p = sync_playwright().start()
context = p.chromium.launch_persistent_context(
    bot_profile,
    headless=False,
    timeout=120000,
    args=[
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
    ],
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    viewport={"width": 1280, "height": 720},
    locale="en-US",
)

page = context.pages[0] if context.pages else context.new_page()

stealth_js = 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
page.add_init_script(stealth_js)

page.goto("https://x.com/i/flow/login", timeout=120000, wait_until="domcontentloaded")

input("Press Enter AFTER you are logged in and see your timeline...")

cookies = context.cookies()
with open("session.json", "w") as f:
    json.dump({"cookies": cookies}, f, indent=2)

print(f"Saved {len(cookies)} cookies to session.json")
context.close()
p.stop()
print("Done! session.json is ready.")
