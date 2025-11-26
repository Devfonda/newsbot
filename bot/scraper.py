# bot/scraper.py
"""
Simple requests-only scraper wrapper for NewsBot.
Compatible with Railway (no playwright).
"""

import logging
import time
import os

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

try:
    from .scraper_requests import fetch_with_requests as _fetch_with_requests_impl
except Exception:
    _fetch_with_requests_impl = None

import requests

def _requests_fetch(url: str, timeout: int = 10, verify: bool = True) -> str:
    headers = {
        "User-Agent": "NewsBot/1.0 (+https://example.org)",
    }
    resp = requests.get(url, headers=headers, timeout=timeout, verify=verify)
    resp.raise_for_status()
    return resp.text

def fetch_url(url: str, prefer_uc=False, uc_timeout=30, retries=2, timeout=10):
    insecure = os.environ.get("NEWSBOT_INSECURE", "0") in ("1", "true", "True")

    attempts = max(1, retries + 1)
    last_exc = None

    for attempt in range(1, attempts + 1):
        try:
            if _fetch_with_requests_impl:
                return _fetch_with_requests_impl(url, timeout=timeout)
            else:
                return _requests_fetch(url, timeout=timeout, verify=not insecure)
        except Exception as e:
            last_exc = e
            logger.warning(f"fetch_url attempt {attempt} failed: {e}")
            time.sleep(1)

    raise last_exc
