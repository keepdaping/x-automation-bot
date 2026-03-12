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


def human_typing(element, text, delay_per_char_ms=50):
    """
    Type text slowly to simulate human typing
    
    Args:
        element: Playwright element
        text: Text to type
        delay_per_char_ms: Base delay between characters
    """
    try:
        element.click()
        time.sleep(0.2)
        
        for char in text:
            # Variable typing speed (humans don't type at constant speed)
            if char in [" ", ".", ",", "!", "?"]:
                # Slightly longer pause after punctuation
                char_delay = delay_per_char_ms + random.randint(50, 150)
            else:
                char_delay = delay_per_char_ms + random.randint(-20, 50)
            
            element.type(char)
            time.sleep(char_delay / 1000)
        
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
