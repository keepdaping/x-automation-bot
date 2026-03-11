import json
from pathlib import Path

LOG_FILE = Path("data/engagement_log.json")

def log_result(tweet_text, action, metrics):

    if LOG_FILE.exists():
        data = json.loads(LOG_FILE.read_text())
    else:
        data = []

    data.append({
        "tweet": tweet_text,
        "action": action,
        "metrics": metrics
    })

    LOG_FILE.write_text(json.dumps(data, indent=2))