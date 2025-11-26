import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import bot.rss_fetcher as r

print("Calling poll_once()...")
r.poll_once()
print("poll_once() returned")
