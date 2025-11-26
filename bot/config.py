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
