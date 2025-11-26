# bot/bot_main.py
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from .scraper import get_news_from_sources
from .storage import add_sent_hash, load_sent_hashes
from .sender import send_news
from .config import BOT_TOKEN, CHECK_INTERVAL, SENT_FILE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s:%(lineno)d - %(message)s")
logger = logging.getLogger("newsbot")

# load sent cache
sent = load_sent_hashes(SENT_FILE)

# --- command handlers ---
async def cmd_status(update, context):
    await update.message.reply_text(
        f"Status:\nCached sent: {len(sent)}\nCheck interval: {CHECK_INTERVAL}s"
    )

async def cmd_test(update, context):
    # announce and run scraper
    try:
        await update.message.reply_text("Running test scrape...")
    except Exception:
        # fallback safe print if reply fails
        logger.exception("Failed to send initial reply in /test")

    items = get_news_from_sources()
    n = 0
    for it in items[:10]:
        try:
            await update.message.reply_text(f"{it.get('title')}\n{it.get('link')}")
            n += 1
        except Exception:
            logger.exception("Failed to reply with item in /test")
    try:
        await update.message.reply_text(f"Found {len(items)} items, displayed {n}")
    except Exception:
        logger.exception("Failed to send final summary in /test")

# --- temporary logging handler for debugging incoming updates ---
async def log_all(update, context):
    try:
        msg = getattr(update, "message", None)
        if msg:
            chat = getattr(msg, "chat", None)
            # print a compact summary to terminal
            print("=== incoming update ===")
            print("from:", getattr(msg, "from_user", getattr(msg, "from", None)))
            print("chat:", getattr(chat, "id", None), getattr(chat, "type", None))
            print("text:", getattr(msg, "text", None))
        else:
            print("=== incoming update (no message) ===", repr(update)[:200])
    except Exception as e:
        print("log_all error:", e)

# --- job that runs periodically to fetch and send news ---
def job():
    items = get_news_from_sources()
    for it in items:
        key = (it.get('title') or it.get('link') or "")[:500]
        # use a stable hash mechanism in storage; here we compare raw keys
        if key and key not in sent:
            ok = send_news(it)
            if ok:
                sent.add(key)
                add_sent_hash(SENT_FILE, key)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # register command handlers
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("test", cmd_test))

    # register logger for all incoming updates (temporary; remove later)
    app.add_handler(MessageHandler(filters.ALL, log_all))

    # scheduler for periodic job
    sched = BackgroundScheduler()
    sched.add_job(job, "interval", seconds=CHECK_INTERVAL, id="news_checker")
    sched.start()
    logger.info("Scheduler started")

    # start polling (this call is blocking)
    app.run_polling()

if __name__ == "__main__":
    main()
