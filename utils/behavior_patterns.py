import random
import time

def random_pause():
    time.sleep(random.randint(20, 90))

def random_scroll(page):
    scroll_amount = random.randint(800, 2500)
    page.mouse.wheel(0, scroll_amount)

def human_activity_pause():
    # simulate user leaving app
    time.sleep(random.randint(300, 900))