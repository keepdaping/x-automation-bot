"""
Human behavior simulation.
IMPROVED: Burst typing pattern instead of uniform character-by-character.
"""

import random
import time
from logger_setup import log


def random_delay(min_seconds=1.5, max_seconds=4):
    time.sleep(random.uniform(min_seconds, max_seconds))


def random_delay_range(min_ms=500, max_ms=2000):
    return random.uniform(min_ms, max_ms) / 1000


def natural_scroll(page, pixels=1500, delay_between_scrolls=300):
    try:
        scroll_steps = random.randint(3, 6)
        pixels_per_step = pixels // scroll_steps
        for i in range(scroll_steps):
            scroll_amount = pixels_per_step + random.randint(-100, 100)
            page.mouse.wheel(0, scroll_amount)
            time.sleep(delay_between_scrolls / 1000)
            if i == scroll_steps // 2:
                time.sleep(random.uniform(0.5, 1.5))
    except Exception as e:
        log.warning(f"Scroll failed: {e}")


def random_position(element=None):
    if element:
        try:
            box = element.bounding_box()
            if box:
                x = box["x"] + random.uniform(box["width"] * 0.1, box["width"] * 0.9)
                y = box["y"] + random.uniform(box["height"] * 0.1, box["height"] * 0.9)
                return {"x": x, "y": y}
        except Exception:
            pass
    return None


def human_typing(element, text, wpm: int = 60):
    """
    Type text with realistic burst patterns.
    
    Instead of uniform delay per character, humans type in bursts:
    - Fast bursts of 3-7 characters
    - Brief pauses between bursts
    - Longer pauses after punctuation
    """
    try:
        base_delay_ms = (60000 / wpm) / 5
        element.click()
        time.sleep(0.2)

        i = 0
        while i < len(text):
            # Determine burst length (3-7 chars)
            burst_len = min(random.randint(3, 7), len(text) - i)
            burst = text[i:i + burst_len]

            # Type the burst quickly
            for char in burst:
                if char in [" ", ".", ",", "!", "?", ";", ":"]:
                    char_delay = base_delay_ms * random.uniform(1.2, 1.8)
                elif char.isupper():
                    char_delay = base_delay_ms * random.uniform(1.0, 1.3)
                else:
                    char_delay = base_delay_ms * random.uniform(0.6, 1.0)

                element.type(char)
                time.sleep(char_delay / 1000)

            i += burst_len

            # Pause between bursts (humans pause to think)
            if i < len(text):
                # Longer pause after punctuation
                if burst[-1] in ".!?":
                    time.sleep(random.uniform(0.3, 0.8))
                elif burst[-1] == " ":
                    time.sleep(random.uniform(0.1, 0.3))
                else:
                    time.sleep(random.uniform(0.05, 0.15))

        log.debug(f"✓ Typed {len(text)} chars at ~{wpm} WPM (burst pattern)")
        return True

    except Exception as e:
        log.error(f"Human typing failed: {e}")
        return False


def random_action_probability(probability):
    return random.random() < probability
