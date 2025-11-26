# bot/sender.py
import logging
import requests
from .config import BOT_TOKEN, CHANNEL_ID

logger = logging.getLogger(__name__)

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_news(item: dict) -> bool:
    text = f"{item.get('title')}\n{item.get('link')}"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "disable_web_page_preview": False
    }
    try:
        r = requests.post(f"{API_BASE}/sendMessage", data=payload, timeout=15)
        r.raise_for_status()
        logger.info("Sent to %s: %s", CHANNEL_ID, (item.get('title') or '')[:60])
        return True
    except Exception:
        logger.exception("Failed to send message via Telegram HTTP API")
        return False
