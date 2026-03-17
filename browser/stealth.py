"""Stealth techniques to hide Playwright automation."""

import random

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'permissions', { get: () => ({ query: async () => ({ state: 'granted' }) }) });
if (navigator.userAgentData) {
    Object.defineProperty(navigator.userAgentData, 'brands', {
        get: () => [{ brand: 'Google Chrome', version: '120' }, { brand: 'Chromium', version: '120' }]
    });
}
delete window.__HEADLESS__;
delete window.__AUTOMATION__;
delete window.__CONTROL__;
"""

BROWSER_CONTEXT_OPTIONS = {
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "viewport": {"width": 1920 + random.randint(-100, 100), "height": 1080 + random.randint(-50, 50)},
    "locale": "en-US",
    "timezone_id": "America/Los_Angeles",
}

LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--disable-extensions",
    "--disable-sync",
    "--disable-popup-blocking",
    "--disable-background-networking",
    "--no-first-run",
    "--no-default-browser-check",
    "--no-pings",
]

CONTEXT_EXTRA_OPTIONS = {
    "ignore_https_errors": True,
    "extra_http_headers": {
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    },
}


def inject_stealth_script(page):
    try:
        page.add_init_script(STEALTH_SCRIPT)
        return True
    except Exception as e:
        print(f"⚠ Stealth script injection failed: {e}")
        return False


def dismiss_cookie_modal(page, timeout=3000):
    for action in [
        lambda: page.press("body", "Escape"),
        lambda: page.click("[aria-label='Close']", timeout=timeout),
        lambda: page.click("button:has-text('Accept all')", timeout=timeout),
    ]:
        try:
            action()
            page.wait_for_timeout(500)
            return True
        except Exception:
            continue
    return False
