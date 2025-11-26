import logging
from bot.rss_fetcher import poll_once

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

print("Running poll_once()...")
poll_once()
print("Done.")
