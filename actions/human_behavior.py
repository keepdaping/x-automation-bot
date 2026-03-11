import random
import time

def random_delay(a=2, b=5):
    time.sleep(random.uniform(a, b))

def random_scroll(page):
    page.mouse.wheel(0, random.randint(300, 1000))