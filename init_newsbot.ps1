Write-Host "=== Initializing NewsBot Project ==="

$proj = (Get-Location).ProviderPath
Write-Host "Project Path: $proj"

# --- Create folders ---
Write-Host "Creating folders (bot, tests)..."
New-Item -ItemType Directory -Path "$proj\bot" -Force | Out-Null
New-Item -ItemType Directory -Path "$proj\tests" -Force | Out-Null

# --- Write requirements.txt ---
Write-Host "Generating requirements.txt..."
@"
python-dotenv>=1.0.0
requests>=2.31.0
beautifulsoup4>=4.12.2
python-telegram-bot>=20.5
APScheduler>=3.10.1
lxml>=4.9.3
selenium>=5.13.0
gunicorn>=20.1.0
"@ | Out-File -FilePath "$proj\requirements.txt" -Encoding utf8 -Force

# --- .env.example ---
Write-Host "Generating .env.example..."
@"
BOT_TOKEN=your_bot_token_here
CHANNEL_ID=@your_channel_or_-100xxxxxxxxxx
CHECK_INTERVAL=300
DEBUG_MODE=False
USER_AGENT=NewsBot/1.0 (+https://example.com)
"@ | Out-File "$proj\.env.example" -Encoding utf8 -Force

# --- bot/__init__.py ---
"__all__ = ['bot_main', 'config', 'scraper', 'sender', 'storage']" | Out-File "$proj\bot\__init__.py" -Encoding utf8 -Force

# --- bot/config.py ---
Write-Host "Writing bot/config.py..."
@"
from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / '.env')

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 300))
DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() in ('1','true','yes')
USER_AGENT = os.getenv('USER_AGENT', 'NewsBot/1.0')

SENT_FILE = str(BASE_DIR / 'sent_news.txt')
SAMPLE_FILE = str(BASE_DIR / 'sample_news.json')
"@ | Out-File "$proj\bot\config.py" -Encoding utf8 -Force

# --- bot/storage.py ---
Write-Host "Writing bot/storage.py..."
@"
from pathlib import Path
import hashlib

def load_sent_hashes(path: str):
    p = Path(path)
    if not p.exists():
        return set()
    with p.open('r', encoding='utf-8') as f:
        return {line.strip() for line in f if line.strip()}

def add_sent_hash(path: str, text: str):
    h = hashlib.sha256(text.encode('utf-8')).hexdigest()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('a', encoding='utf-8') as f:
        f.write(h + '\n')
    return h
"@ | Out-File "$proj\bot\storage.py" -Encoding utf8 -Force

# --- bot/scraper.py ---
Write-Host "Writing bot/scraper.py..."
@"
import requests
from bs4 import BeautifulSoup
from typing import List, Dict
from .config import USER_AGENT, DEBUG_MODE
import logging
logger = logging.getLogger(__name__)

HEADERS = {'User-Agent': USER_AGENT}

def fetch_url(url: str, timeout=15) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        logger.info(f'Fetched {url} -> {r.status_code}')
        return r.text
    except Exception:
        logger.exception('fetch_url error')
        return ''

def parse_kontan(html: str) -> List[Dict]:
    items = []
    if not html: return items
    soup = BeautifulSoup(html, 'lxml')
    cards = soup.select('article, .article, .news-item, .post')
    for c in cards:
        a = c.find('a')
        if not a: continue
        title = a.get_text(strip=True)
        link = a.get('href')
        if link and link.startswith('/'):
            link = 'https://www.kontan.co.id' + link
        if title and link:
            items.append({'source': 'kontan', 'title': title, 'link': link})
    return items

def get_news_from_sources() -> List[Dict]:
    html = fetch_url('https://www.kontan.co.id/search/saham')
    return parse_kontan(html)
"@ | Out-File "$proj\bot\scraper.py" -Encoding utf8 -Force

# --- bot/sender.py ---
Write-Host "Writing bot/sender.py..."
@"
import logging
from telegram import Bot
from .config import BOT_TOKEN, CHANNEL_ID

bot = Bot(BOT_TOKEN)
logger = logging.getLogger(__name__)

def send_news(item: dict):
    text = f"{item['title']}\n{item['link']}"
    try:
        bot.send_message(chat_id=CHANNEL_ID, text=text)
        return True
    except Exception:
        logger.exception('Send error')
        return False
"@ | Out-File "$proj\bot\sender.py" -Encoding utf8 -Force

# --- bot/bot_main.py ---
Write-Host "Writing bot/bot_main.py..."
@"
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from telegram.ext import ApplicationBuilder, CommandHandler
from .scraper import get_news_from_sources
from .storage import add_sent_hash, load_sent_hashes
from .sender import send_news
from .config import BOT_TOKEN, CHECK_INTERVAL, SENT_FILE

logging.basicConfig(level=logging.INFO)
sent = load_sent_hashes(SENT_FILE)

async def cmd_test(update, context):
    items = get_news_from_sources()
    for it in items[:5]:
        await update.message.reply_text(f"{it['title']}\n{it['link']}")

def job():
    items = get_news_from_sources()
    for it in items:
        h = it['title'][:40]
        if h not in sent:
            if send_news(it):
                sent.add(h)
                add_sent_hash(SENT_FILE, h)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('test', cmd_test))

    sched = BackgroundScheduler()
    sched.add_job(job, 'interval', seconds=CHECK_INTERVAL)
    sched.start()

    app.run_polling()

if __name__ == '__main__':
    main()
"@ | Out-File "$proj\bot\bot_main.py" -Encoding utf8 -Force

Write-Host "=== DONE ==="
Write-Host "Now edit .env and install venv + requirements:"
Write-Host "  python -m venv .venv"
Write-Host "  .\\.venv\\Scripts\\Activate.ps1"
Write-Host "  pip install -r requirements.txt"
Write-Host "  python -m bot.bot_main"
