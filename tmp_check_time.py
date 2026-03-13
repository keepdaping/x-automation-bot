from datetime import datetime, timedelta
import json

d = json.load(open('data/session_state.txt'))
start = datetime.fromisoformat(d['session_start'])
now = datetime.now()
print('now', now)
print('start', start)
print('delta', now - start)
print('delta hours', (now - start).total_seconds() / 3600)
print('gt12', now - start > timedelta(hours=12))
