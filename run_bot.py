from bot.rss_fetcher import run_loop

if __name__ == "__main__":
    # cek setiap 5 menit, aman untuk Railway worker
    run_loop(interval_seconds=300)
