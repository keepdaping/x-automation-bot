import random
from datetime import datetime

def should_post_now():

    hour = datetime.now().hour

    peak_hours = [9, 12, 15, 19, 21]

    if hour in peak_hours:
        return random.random() < 0.4

    return random.random() < 0.1