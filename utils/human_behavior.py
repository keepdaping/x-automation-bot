import random
import time
from logger_setup import log


def random_delay(min_seconds=1.5, max_seconds=4):
    """
    Add random delay between actions (human-like)
    Default: 1.5-4 seconds
    """
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def random_delay_range(min_ms=500, max_ms=2000):
    """
    Return random delay in milliseconds
    Useful for typing speed simulation
    """
    return random.uniform(min_ms, max_ms) / 1000


def natural_scroll(page, pixels=1500, delay_between_scrolls=300):
    """
    Scroll page in natural, human-like manner
    
    Args:
        page: Playwright page object
        pixels: Total pixels to scroll
        delay_between_scrolls: Delay between scroll steps (ms)
    """
    try:
        scroll_steps = random.randint(3, 6)  # Random number of scroll increments
        pixels_per_step = pixels // scroll_steps
        
        for i in range(scroll_steps):
            # Add randomness to each scroll
            scroll_amount = pixels_per_step + random.randint(-100, 100)
            page.mouse.wheel(0, scroll_amount)
            time.sleep(delay_between_scrolls / 1000)
            
            # Random pause midway through scrolling
            if i == scroll_steps // 2:
                time.sleep(random.uniform(0.5, 1.5))
    except Exception as e:
        log.warning(f"Scroll failed: {e}")


def random_scroll(page):
    """Legacy function - use natural_scroll instead"""
    page.mouse.wheel(0, random.randint(300, 1000))


def random_position(element=None):
    """
    Get random position on element for clicking
    Simulates human clicking at slightly different positions
    """
    if element:
        try:
            box = element.bounding_box()
            if box:
                x = box["x"] + random.uniform(box["width"] * 0.1, box["width"] * 0.9)
                y = box["y"] + random.uniform(box["height"] * 0.1, box["height"] * 0.9)
                return {"x": x, "y": y}
        except:
            pass
    return None


def random_pause(min_sec=2, max_sec=8):
    """
    Random pause - simulates human reading/thinking
    Useful when navigating between pages
    """
    pause_time = random.uniform(min_sec, max_sec)
    log.debug(f"Pausing for {pause_time:.1f}s...")
    time.sleep(pause_time)


def human_typing(element, text, wpm: int = 60):
    """
    Type text at realistic human speed (WPM-based).
    
    Args:
        element: Playwright element
        text: Text to type
        wpm: Words per minute (default 60 = average typing speed)
        
    How it works:
    - 60 WPM = ~300 words/min ≈ 1500 chars/min
    - = ~25 chars/second ≈ 40ms per character
    - With pauses after punctuation and randomness
    
    This prevents detection as bot (was 10x too fast before!)
    """
    try:
        # Convert WPM to character delay in milliseconds
        # 5 characters per word average
        base_delay_ms = (60000 / wpm) / 5
        
        # Click to focus and prepare for typing
        element.click()
        time.sleep(0.2)
        
        for i, char in enumerate(text):
            # Variable delay based on character type
            if char in [" ", ".", ",", "!", "?", ";", ":"]:
                # Longer pause after punctuation (humans look up)
                char_delay_ms = base_delay_ms * 1.5
            elif i > 0 and text[i-1] in [".", "!", "?"]:
                # Pause after sentence-ending punctuation is longer
                char_delay_ms = base_delay_ms * 1.3
            elif char.isupper():
                # Shift key takes slightly longer
                char_delay_ms = base_delay_ms * 1.1
            else:
                # Regular character
                char_delay_ms = base_delay_ms
            
            # Add randomness (±25%) to avoid pattern detection
            randomization = random.uniform(0.75, 1.25)
            final_delay_ms = char_delay_ms * randomization
            
            # Type the character
            element.type(char)
            time.sleep(final_delay_ms / 1000)
        
        log.debug(f"✓ Typed {len(text)} characters at {wpm} WPM")
        return True
        
    except Exception as e:
        log.error(f"Human typing failed: {e}")
        return False


def random_action_probability(probability):
    """
    Randomly decide whether to perform an action
    
    Args:
        probability: Float between 0-1 (e.g., 0.6 = 60% chance)
    
    Returns:
        bool: True if action should be performed
    """
    return random.random() < probability


def simulate_user_reading(page, duration_seconds=3):
    """
    Simulate user reading by staying on page
    Useful between actions
    """
    start = time.time()
    while time.time() - start < duration_seconds:
        # Occasional small scrolls (simulating reading)
        if random.random() < 0.3:
            page.mouse.wheel(0, random.randint(50, 200))
        time.sleep(random.uniform(0.5, 1))
