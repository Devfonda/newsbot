# debug_polling.py — simple getUpdates poller for debugging
import time, requests, os, json

# read token from .env if present, fallback to asking env var
token = None
envpath = os.path.join(os.getcwd(), '.env')
if os.path.exists(envpath):
    with open(envpath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip().startswith('BOT_TOKEN='):
                token = line.strip().split('=',1)[1]
                break

if not token:
    token = os.getenv('BOT_TOKEN')
if not token:
    print("ERROR: BOT_TOKEN not found in .env or environment")
    raise SystemExit(1)

API = f"https://api.telegram.org/bot{token}/getUpdates"
offset = None
print("Debug poller started. Polling getUpdates... (Ctrl+C to stop)")

try:
    while True:
        params = {}
        if offset:
            params['offset'] = offset
        r = requests.get(API, params=params, timeout=15)
        try:
            j = r.json()
        except Exception:
            print("Non-JSON response:", r.status_code, r.text[:200])
            time.sleep(1)
            continue
        if not j.get('ok'):
            print("API returned not ok:", j)
            time.sleep(3)
            continue
        results = j.get('result', [])
        if results:
            for u in results:
                print("=== update ===")
                print(json.dumps(u, ensure_ascii=False, indent=2))
                offset = u['update_id'] + 1
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopped by user")
