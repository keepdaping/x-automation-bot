"""
Post a tweet with proper error handling.

Handles X's cookie-consent overlay (twc-cc-mask) which intercepts pointer
events and prevents typing — causing the submit button to remain disabled.
"""

import time
import random
from utils.human_behavior import random_delay
from logger_setup import log


_TEXTAREA_SELECTOR  = '[data-testid="tweetTextarea_0"]'
_SUBMIT_SELECTOR    = '[data-testid="tweetButton"]'
_OVERLAY_SELECTOR   = '[data-testid="twc-cc-mask"]'


def _dismiss_overlay(page, timeout_ms: int = 3000) -> bool:
    """
    Dismiss the twc-cc-mask cookie-consent overlay if present.

    The overlay sits above the compose box and intercepts pointer events.
    We try to click the "Accept all cookies" button; if that fails we
    attempt to remove the overlay from the DOM via JavaScript as a last
    resort so that subsequent clicks reach the textarea.

    Returns True if the overlay was cleared (or was never present).
    """
    try:
        overlay = page.locator(_OVERLAY_SELECTOR)
        if overlay.count() == 0 or not overlay.is_visible(timeout=timeout_ms):
            return True  # no overlay — nothing to do

        log.debug("twc-cc-mask overlay detected — attempting to dismiss")

        # Strategy 1: click the "Accept all" button inside the overlay
        for btn_text in ("Accept all cookies", "Accept all", "Accept"):
            btn = page.locator(f"button:has-text('{btn_text}')").first
            try:
                if btn.count() > 0 and btn.is_visible(timeout=1500):
                    btn.click(timeout=3000)
                    time.sleep(0.8)
                    if overlay.count() == 0 or not overlay.is_visible(timeout=1000):
                        log.debug("Overlay dismissed via accept button")
                        return True
            except Exception:
                pass

        # Strategy 2: remove overlay via JS so pointer events reach the textarea
        try:
            page.evaluate(
                "() => { "
                "  const el = document.querySelector('[data-testid=\"twc-cc-mask\"]'); "
                "  if (el) el.remove(); "
                "}"
            )
            time.sleep(0.3)
            log.debug("Overlay removed via JS")
            return True
        except Exception as e:
            log.warning(f"Overlay JS removal failed: {e}")

        return False  # overlay still present

    except Exception:
        return True   # assume clear if we can't check


def _type_into_compose(page, text: str, timeout_ms: int = 10000) -> bool:
    """
    Focus the compose textarea and type text using the keyboard.

    Uses keyboard.type() rather than element.type() so the input reaches
    the textarea even when a pointer-event overlay is still fading out.
    """
    try:
        # Make sure the textarea is visible
        page.wait_for_selector(_TEXTAREA_SELECTOR, state="visible", timeout=timeout_ms)

        textarea = page.locator(_TEXTAREA_SELECTOR).first
        if textarea.count() == 0:
            log.error("Compose textarea not found after waiting")
            return False

        # Force-click to focus (bypasses any lingering overlay)
        textarea.click(force=True, timeout=5000)
        time.sleep(0.4)

        # Use page.keyboard.type() — not element.type() — to bypass overlay
        # interception entirely.  Simulate burst-typing manually.
        base_ms = (60000 / 60) / 5   # ~200ms / char at 60 WPM, divided into bursts
        i = 0
        while i < len(text):
            burst_len = min(random.randint(3, 7), len(text) - i)
            burst = text[i: i + burst_len]
            for char in burst:
                delay = base_ms * random.uniform(0.6, 1.4)
                page.keyboard.type(char)
                time.sleep(delay / 1000)
            i += burst_len
            if i < len(text):
                pause = random.uniform(0.05, 0.25)
                if burst[-1] in ".!?":
                    pause = random.uniform(0.3, 0.7)
                time.sleep(pause)

        log.debug(f"Typed {len(text)} chars into compose box")
        return True

    except Exception as e:
        log.error(f"Failed to type into compose textarea: {e}")
        return False


def _wait_for_enabled_submit(page, timeout_ms: int = 8000) -> bool:
    """
    Wait until the tweetButton is enabled (X enables it only after text is
    detected in the compose box via React's input event).

    Returns True once enabled, False if it stays disabled past the deadline.
    """
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        btn = page.locator(_SUBMIT_SELECTOR).first
        try:
            if btn.count() > 0 and btn.is_visible() and btn.is_enabled():
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def post_tweet(page, text: str, timeout: int = 15000) -> bool:
    """
    Post a tweet.  Returns True on success, False on failure.

    Robustness improvements vs original:
    - Dismisses twc-cc-mask overlay before typing
    - Types via page.keyboard.type() to bypass pointer-event interception
    - Waits for submit button to become enabled (not just visible) before clicking
    - Falls back to Ctrl+Enter if button click times out
    - Confirms success by checking textarea disappears
    """
    try:
        # ── 1. Navigate to compose ──────────────────────────────────────────
        page.goto(
            "https://x.com/compose/post",
            wait_until="domcontentloaded",
            timeout=timeout,
        )
        time.sleep(1.5)

        # ── 2. Dismiss overlay if present ───────────────────────────────────
        overlay_clear = _dismiss_overlay(page)
        if not overlay_clear:
            log.warning("Could not fully dismiss twc-cc-mask — will attempt to type anyway")
        time.sleep(0.5)

        # ── 3. Type text into compose box ───────────────────────────────────
        typed = _type_into_compose(page, text, timeout_ms=timeout)
        if not typed:
            log.error("Tweet compose: typing failed")
            return False

        # Small pause so X's React state registers the input
        time.sleep(1.2)

        # ── 4. Wait for submit button to become enabled ─────────────────────
        btn_ready = _wait_for_enabled_submit(page, timeout_ms=6000)
        if not btn_ready:
            log.warning("Submit button did not enable — falling back to Ctrl+Enter")
            try:
                page.keyboard.press("Control+Enter")
                time.sleep(2.0)
            except Exception as ke:
                log.error(f"Ctrl+Enter fallback failed: {ke}")
                return False
        else:
            # ── 5. Click submit ─────────────────────────────────────────────
            btn = page.locator(_SUBMIT_SELECTOR).first
            try:
                btn.click(timeout=5000)
                log.info("→ Tweet submitted (tweetButton click)")
            except Exception as ce:
                log.warning(f"Submit click raised ({ce}) — falling back to Ctrl+Enter")
                try:
                    page.keyboard.press("Control+Enter")
                    log.info("→ Tweet submitted (Ctrl+Enter fallback)")
                except Exception as ke:
                    log.error(f"Ctrl+Enter fallback failed: {ke}")
                    return False

        time.sleep(2.0)

        # ── 6. Confirm success — textarea should be gone ────────────────────
        try:
            page.wait_for_selector(
                _TEXTAREA_SELECTOR,
                state="detached",
                timeout=4000,
            )
            log.info(f"✓ Tweet posted: {text[:60]}...")
            random_delay()
            return True
        except Exception:
            # Textarea still present — post may have silently failed
            log.warning("Compose textarea still present after submit — tweet may not have posted")
            return False

    except Exception as e:
        log.error(f"Failed to post tweet: {e}")
        return False
