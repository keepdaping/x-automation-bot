"""
Advanced stealth techniques to hide Playwright automation from X.com
"""

import random

STEALTH_SCRIPT = """
// Hide webdriver flag
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
});

// Hide chrome object
window.chrome = {
    runtime: {}
};

// Remove headless indicator
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});

// Spoof languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
});

// Proper permissions
Object.defineProperty(navigator, 'permissions', {
    get: () => ({
        query: async () => ({ state: 'granted' }),
    }),
});

// Hide headless characteristics
if (navigator.userAgentData) {
    Object.defineProperty(navigator.userAgentData, 'brands', {
        get: () => [
            { brand: 'Google Chrome', version: '120' },
            { brand: 'Chromium', version: '120' },
        ],
    });
}

// Override toString methods
const originalToString = Function.prototype.toString;
Function.prototype.toString = function() {
    if (this === window.navigator.permissions.query) {
        return 'function query() { [native code] }';
    }
    return originalToString.call(this);
};

// Canvas fingerprinting protection
const canvas = document.createElement('canvas');
const ctx = canvas.getContext('2d');
const originalFillText = ctx.fillText;
ctx.fillText = function(text, x, y) {
    if (text.length > 0) {
        // Add slight randomization to canvas rendering
        return originalFillText.call(this, text + ' ', x, y);
    }
    return originalFillText.call(this, text, x, y);
};

// Remove automation-related window properties
delete window.__HEADLESS__;
delete window.__AUTOMATION__;
delete window.__CONTROL__;
"""

BROWSER_CONTEXT_OPTIONS = {
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "viewport": {
        "width": 1920 + random.randint(-100, 100),  # Add small randomization
        "height": 1080 + random.randint(-50, 50),
    },
    "locale": "en-US",
    "timezone_id": "America/Los_Angeles",
}

LAUNCH_ARGS = [
    # Core anti-detection
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    
    # Disable extensions and features that reveal automation
    "--disable-extensions",
    "--disable-sync",
    
    # Some X-specific detection avoiding
    "--disable-popup-blocking",
    "--disable-prompt-on-repost",
    
    # Memory management
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    
    # Standard flags for stability
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
    """Inject stealth script into page context"""
    try:
        page.add_init_script(STEALTH_SCRIPT)
        return True
    except Exception as e:
        print(f"⚠ Warning: Could not inject stealth script: {e}")
        return False


def dismiss_cookie_modal(page, timeout=3000):
    """Attempt to dismiss cookie consent modal"""
    try:
        # Try pressing Escape
        page.press("body", "Escape")
        page.wait_for_timeout(500)
        return True
    except:
        pass
    
    try:
        # Try clicking close button
        page.click("[aria-label='Close']", timeout=timeout)
        page.wait_for_timeout(500)
        return True
    except:
        pass
    
    try:
        # Try clicking accept all button
        page.click("button:has-text('Accept all')", timeout=timeout)
        page.wait_for_timeout(500)
        return True
    except:
        pass
    
    return False


def bypass_paywall(page):
    """Attempt to bypass any paywalls or overlays"""
    try:
        # Disable all overlays
        page.evaluate("""
            document.querySelectorAll('[role="dialog"]').forEach(el => el.remove());
            document.querySelectorAll('[data-testid="twc-cc-mask"]').forEach(el => el.remove());
        """)
        return True
    except:
        return False
