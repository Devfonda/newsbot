# bot/scraper_uc.py
import logging
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

def _block_unnecessary_requests(route):
    """
    Route handler to abort requests that are not needed (images, fonts, media, trackers).
    Signature matches Playwright's route handler: accepts single `route` argument.
    """
    try:
        request = route.request
        resource_type = request.resource_type
        url = request.url.lower()
        # abort heavy resource types
        if resource_type in ("image", "font", "media"):
            return route.abort()
        # common trackers / analytics / ad endpoints
        blocked_substrings = ("google-analytics", "googletagmanager", "doubleclick", "ads", "adsystem", "analytics")
        if any(s in url for s in blocked_substrings):
            return route.abort()
    except Exception:
        # if anything goes wrong, allow the request (fail open)
        try:
            return route.continue_()
        except Exception:
            return route.abort()
    return route.continue_()

def _normalize_timeout_ms(timeout):
    """
    Ensure timeout is in milliseconds.
    - If timeout is None -> default 30000 ms (30s)
    - If timeout < 1000 -> assume seconds -> convert to ms
    - If timeout >= 1000 -> assume already ms
    """
    if timeout is None:
        return 30_000
    try:
        t = int(timeout)
    except Exception:
        return 30_000
    if t == 0:
        return 30_000
    if t < 1000:
        # assume input given in seconds, convert to ms
        return t * 1000
    return t

def fetch_with_uc(url, timeout=30_000, headless=True, retries=2, proxy=None):
    """
    Robust synchronous fetch using Playwright.
    - timeout: can be seconds (e.g. 30) or milliseconds (30000). Normalized internally.
    - headless: bool
    - retries: number of attempts
    - proxy: string like "http://user:pass@host:port" or None
    Returns HTML text on success, raises exception on final failure.
    """
    timeout_ms = _normalize_timeout_ms(timeout)
    logger.info("fetch_with_uc: timeout normalized to %d ms (raw=%s)", timeout_ms, timeout)
    last_exc = None

    for attempt in range(1, max(1, int(retries)) + 1):
        logger.info("fetch_with_uc: attempt %d for %s (timeout=%dms)", attempt, url, timeout_ms)
        p = None
        browser = None
        context = None
        page = None
        try:
            p = sync_playwright().start()
            browser = p.chromium.launch(headless=headless, proxy={"server": proxy} if proxy else None)
            context = browser.new_context(
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
                locale="id-ID",
            )
            # attach route handler (helper defined above)
            context.route("**/*", _block_unnecessary_requests)

            page = context.new_page()
            page.set_default_navigation_timeout(timeout_ms)
            page.set_default_timeout(timeout_ms)

            # Try DOMContentLoaded first; if that times out, try load.
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            except PWTimeoutError:
                logger.warning("Navigation domcontentloaded timed out, trying 'load' wait (timeout=%dms)", timeout_ms)
                response = page.goto(url, wait_until="load", timeout=timeout_ms)

            # small pause for JS rendering if necessary
            time.sleep(0.4)

            html = page.content()

            # Heuristic: if html too small, maybe blocked or not content; treat as failure to trigger retry
            if not html or len(html) < 200:
                raise RuntimeError(f"Fetched content too small (len={len(html) if html else 0})")

            logger.info("fetch_with_uc: success (attempt %d)", attempt)
            return html

        except KeyboardInterrupt:
            logger.info("fetch_with_uc: KeyboardInterrupt received, performing safe cleanup.")
            # ensure cleanup then re-raise
            try:
                if page:
                    page.close()
            except Exception:
                pass
            try:
                if context:
                    context.close()
            except Exception:
                pass
            try:
                if browser:
                    browser.close()
            except Exception:
                pass
            try:
                if p:
                    p.stop()
            except Exception:
                pass
            raise

        except Exception as e:
            last_exc = e
            logger.warning("fetch_with_uc: attempt %d failed: %s", attempt, repr(e))
            # best-effort cleanup
            try:
                if page:
                    page.close()
            except Exception:
                pass
            try:
                if context:
                    context.close()
            except Exception:
                pass
            try:
                if browser:
                    browser.close()
            except Exception:
                pass
            try:
                if p:
                    p.stop()
            except Exception:
                pass

            if attempt < retries:
                sleep = 1.5 ** attempt
                logger.info("fetch_with_uc: retrying after %.2f seconds...", sleep)
                time.sleep(sleep)
            else:
                logger.error("fetch_with_uc: all %d attempts failed", retries)
                # raise the last exception, without chaining to keep traceback clear
                raise last_exc from None
