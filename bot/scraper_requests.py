import requests

def fetch_with_requests(url: str, timeout: int = 10) -> str:
    headers = {
        "User-Agent": "NewsBot/1.0 (+https://example.org)",
    }
    r = requests.get(url, timeout=timeout, headers=headers)
    r.raise_for_status()
    return r.text
