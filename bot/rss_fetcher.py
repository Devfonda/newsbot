import os
import time
import hashlib
import logging
import feedparser
import requests
import sqlite3
import re
from datetime import datetime, timedelta
from .scraper import fetch_url

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

BOT_TOKEN = "8249944565:AAH3gLQ9E_UvsJ9rVGmWEC3syNOV9Jmha4U"
CHAT_ID = "-1003398047018"

KEYWORDS = [
    "right issue",
    "aksi korporasi",
    "rups",
    "akuisisi",
    "backdoor",
    "expansi",
    "ekspansi",
    "stock split",
    "stock-split",
    "ipo",
]

FEEDS = {
    "cnbc_market": "https://www.cnbcindonesia.com/market/rss/",
    "kontan_keuangan": "https://www.kontan.co.id/feed",
}

MAX_SENDS_PER_POLL = 9  # Maksimal 3 batch (3×3)
PER_FEED_COOLDOWN_SECONDS = 45
BATCH_SIZE = 3

# SQLite database setup
DB_PATH = "seen_news.db"

def _get_conn():
    return sqlite3.connect(DB_PATH)

# Initialize database dengan schema yang lebih robust
def init_db():
    conn = _get_conn()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title_hash TEXT,
                content_hash TEXT,
                title TEXT,
                published_date TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Create indexes untuk performa
        conn.execute("CREATE INDEX IF NOT EXISTS idx_url ON seen_articles(url)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_title_hash ON seen_articles(title_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_content_hash ON seen_articles(content_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON seen_articles(created_at)")
    conn.close()

init_db()

def _normalize_text(text):
    """Normalisasi teks untuk perbandingan yang lebih akurat"""
    if not text:
        return ""
    # Convert ke lowercase, hapus whitespace berlebih, hapus karakter spesial
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', ' ', text)  # Hapus punctuation
    text = re.sub(r'\s+', ' ', text)  # Normalisasi whitespace
    return text

def _is_seen(url: str, title: str, content: str) -> bool:
    """Cek apakah artikel sudah pernah dilihat dengan multiple methods"""
    if not url:
        return True
        
    conn = _get_conn()
    cursor = conn.cursor()
    
    try:
        # 1. Cek berdasarkan URL (paling akurat)
        cursor.execute("SELECT 1 FROM seen_articles WHERE url = ? LIMIT 1", (url,))
        if cursor.fetchone():
            logger.info(f"Duplicate detected by URL: {url}")
            return True
        
        # 2. Cek berdasarkan hash judul yang dinormalisasi
        normalized_title = _normalize_text(title)
        title_hash = hashlib.sha256(normalized_title.encode()).hexdigest()
        
        cursor.execute("SELECT 1 FROM seen_articles WHERE title_hash = ? LIMIT 1", (title_hash,))
        if cursor.fetchone():
            logger.info(f"Duplicate detected by title hash: {title}")
            return True
        
        # 3. Cek berdasarkan hash konten (jika ada konten)
        if content:
            # Ambil hanya 500 karakter pertama untuk efisiensi
            content_sample = _normalize_text(content[:500])
            content_hash = hashlib.sha256(content_sample.encode()).hexdigest()
            
            cursor.execute("SELECT 1 FROM seen_articles WHERE content_hash = ? LIMIT 1", (content_hash,))
            if cursor.fetchone():
                logger.info(f"Duplicate detected by content hash: {title}")
                return True
        
        return False
        
    finally:
        conn.close()

def _mark_seen(url: str, title: str, content: str = ""):
    """Tandai artikel sebagai sudah dilihat"""
    if not url:
        return
        
    conn = _get_conn()
    try:
        normalized_title = _normalize_text(title)
        title_hash = hashlib.sha256(normalized_title.encode()).hexdigest()
        
        content_hash = ""
        if content:
            content_sample = _normalize_text(content[:500])
            content_hash = hashlib.sha256(content_sample.encode()).hexdigest()
        
        with conn:
            conn.execute(
                """INSERT INTO seen_articles 
                   (url, title_hash, content_hash, title, published_date) 
                   VALUES (?, ?, ?, ?, datetime('now'))""",
                (url, title_hash, content_hash, title[:200]),  # Simpan hanya 200 char judul
            )
    except sqlite3.IntegrityError:
        # URL sudah ada, skip
        pass
    except Exception as e:
        logger.error(f"Error marking article as seen: {e}")
    finally:
        conn.close()

def _cleanup_old_entries(days=30):
    """Bersihkan entri yang sudah lama untuk menjaga database tetap kecil"""
    conn = _get_conn()
    try:
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        with conn:
            conn.execute("DELETE FROM seen_articles WHERE created_at < ?", (cutoff_date,))
            deleted_count = conn.total_changes
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old entries")
    except Exception as e:
        logger.error(f"Error cleaning up old entries: {e}")
    finally:
        conn.close()

def send_telegram_batch(messages):
    """Mengirim batch berita dalam satu pesan"""
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("Telegram credentials missing.")
        return

    if not messages:
        return

    # Format pesan dengan multiple berita
    message_text = "📰 **Berita Terkini**\n\n"
    
    for i, msg in enumerate(messages, 1):
        # Escape karakter Markdown yang problematic
        title = msg['title'].replace('*', '×').replace('_', ' ').replace('`', "'")
        message_text += f"**{i}. {title}**\n{msg['url']}\n\n"
    
    message_text += f"_📊 Total: {len(messages)} berita_"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID, 
        "text": message_text, 
        "disable_web_page_preview": False,
        "parse_mode": "Markdown"
    }
    
    try:
        r = requests.post(url, data=data, timeout=10)
        if r.status_code == 200:
            logger.info(f"✅ Batch message sent with {len(messages)} news items")
        else:
            logger.error(f"❌ Failed to send message: {r.text}")
        return r.text
    except Exception as e:
        logger.error(f"❌ Error sending batch message: {e}")
        return None

def _match_keyword(title: str, content: str) -> bool:
    """Cek apakah mengandung keyword yang diinginkan"""
    if not title:
        return False
        
    t = _normalize_text(title)
    c = _normalize_text(content)
    
    for kw in KEYWORDS:
        if kw in t or kw in c:
            return True
    return False

def _extract_content_summary(html: str) -> str:
    """Ekstrak summary dari konten HTML"""
    if not html:
        return ""
    
    # Hapus tag HTML dan ambil teks saja
    clean_text = re.sub(r'<[^>]+>', ' ', html)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
    # Ambil maksimal 1000 karakter
    return clean_text.strip()[:1000]

def process_entry(feed_name: str, entry):
    """Process satu entry RSS"""
    url = entry.get("link", "").strip()
    title = entry.get("title", "").strip()

    if not url or not title:
        logger.info(f"[{feed_name}] SKIP invalid entry: {title}")
        return {"sent": False, "reason": "invalid"}

    # Cek duplikasi sebelum fetch content untuk menghemat bandwidth
    if _is_seen(url, title, ""):
        logger.info(f"[{feed_name}] SKIP seen: {title}")
        return {"sent": False, "reason": "seen"}

    try:
        html = fetch_url(url, prefer_uc=False, timeout=10, retries=1)
        content_summary = _extract_content_summary(html)
        
        # Cek keyword setelah mendapatkan konten
        if not _match_keyword(title, content_summary):
            logger.info(f"[{feed_name}] FILTERED not matched: {title}")
            _mark_seen(url, title, content_summary)
            return {"sent": False, "reason": "filtered"}

        # Final duplicate check dengan konten lengkap
        if _is_seen(url, title, content_summary):
            logger.info(f"[{feed_name}] SKIP duplicate content: {title}")
            return {"sent": False, "reason": "duplicate_content"}

        # Kembalikan data berita tanpa langsung mengirim
        return {
            "sent": True, 
            "title": title, 
            "url": url, 
            "feed_name": feed_name,
            "content": content_summary
        }
        
    except Exception as e:
        logger.error(f"[{feed_name}] ERROR processing {url}: {e}")
        return {"sent": False, "reason": f"error: {str(e)}"}

def poll_once():
    """Satu kali polling semua feeds"""
    # Bersihkan entri lama secara periodic
    if int(time.time()) % 3600 == 0:  # Setiap jam sekali
        _cleanup_old_entries()
    
    pending_messages = []
    total_sent = 0
    
    for feed_name, feed_url in FEEDS.items():
        logger.info(f"🔍 Fetching {feed_name} -> {feed_url}")
        
        try:
            parsed = feedparser.parse(feed_url)
            
            if hasattr(parsed, 'bozo_exception') and parsed.bozo_exception:
                logger.warning(f"⚠️ RSS parsing warning for {feed_name}: {parsed.bozo_exception}")

            for entry in parsed.entries:
                if total_sent >= MAX_SENDS_PER_POLL:
                    logger.info(f"ℹ️ Reached max sends per poll ({MAX_SENDS_PER_POLL})")
                    break
                
                result = process_entry(feed_name, entry)
                
                if result.get("sent"):
                    pending_messages.append({
                        "title": result["title"],
                        "url": result["url"]
                    })
                    total_sent += 1
                    
                    # Mark as seen immediately after successful processing
                    _mark_seen(result["url"], result["title"], result.get("content", ""))
                    
                    # Kirim batch jika sudah terkumpul
                    if len(pending_messages) >= BATCH_SIZE:
                        send_telegram_batch(pending_messages)
                        pending_messages = []
                        time.sleep(1)  # Jeda antar batch

        except Exception as e:
            logger.error(f"❌ Error processing feed {feed_name}: {e}")
        
        logger.info(f"⏳ [{feed_name}] cooldown {PER_FEED_COOLDOWN_SECONDS}s")
        time.sleep(PER_FEED_COOLDOWN_SECONDS)
    
    # Kirim sisa berita yang belum mencapai BATCH_SIZE
    if pending_messages:
        send_telegram_batch(pending_messages)
    
    logger.info(f"✅ Poll completed. Total sent: {total_sent}")

def run_loop(interval_seconds=300):
    """Main loop"""
    logger.info("🚀 Starting RSS bot loop...")
    while True:
        try:
            poll_once()
        except Exception as e:
            logger.error(f"💥 Error in main loop: {e}")
        logger.info(f"⏰ Waiting {interval_seconds} seconds until next poll...")
        time.sleep(interval_seconds)