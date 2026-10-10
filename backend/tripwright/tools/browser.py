"""Chromium worker pool for the scripted site tools and the agent-driven `browse_page` tool.

`browse_page` is the thin replacement for strands-agents-tools' LocalChromiumBrowser. That
tool (0.8.9) works when a session is opened and closed cleanly, but an instance that is
garbage-collected without a clean close hangs forever in its own cleanup, and get_text
returns a whole page (about 60k characters) into a 32k-token context.

One headless Chromium per process; every caller gets a private session (its own
context, cookies and page), and a semaphore caps how many run at once so parallel
subagents never block each other. Runs on Akamai compute, not AgentCore.

If a site refuses automation we stop and report it. Nothing here tries to hide the
browser or get past a block page or CAPTCHA.
"""

from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager
from datetime import datetime

from playwright.async_api import Browser, Page, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeout

from .. import config, evidence
from ..recorded import cached

PAGE_CHARS = 5000
BLOCK_STATUSES = {403, 429, 502, 503}
BLOCK_MARKERS = ("captcha", "unusual traffic", "verify you are human", "are you a robot", "access denied")

_browser: Browser | None = None
_launch_lock = asyncio.Lock()
_slots = asyncio.Semaphore(config.BROWSER_WORKERS)


class Blocked(Exception):
    """The site showed a block page or CAPTCHA. Callers fall back to another provider or cached data."""


async def _get_browser() -> Browser:
    global _browser
    async with _launch_lock:
        if _browser is None or not _browser.is_connected():
            playwright = await async_playwright().start()
            _browser = await playwright.chromium.launch(headless=True)
    return _browser


@asynccontextmanager
async def session():
    """A private browser session from the pool."""
    async with _slots:
        browser = await _get_browser()
        context = await browser.new_context(locale="en-US", viewport={"width": 1280, "height": 1600})
        try:
            yield await context.new_page()
        finally:
            await context.close()


async def open_page(page: Page, url: str, ready_selector: str | None = None) -> None:
    """Load `url` and wait for results; raise Blocked if the site refuses us."""
    response = await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    if response is not None and response.status in BLOCK_STATUSES:
        raise Blocked(f"{page.url.split('/')[2]} returned HTTP {response.status} to the automated browser")
    try:
        if ready_selector:
            await page.wait_for_selector(ready_selector, state="attached", timeout=20_000)
        await page.wait_for_timeout(1500)
    except PlaywrightTimeout:
        text = (await page.inner_text("body"))[:5000].lower()
        if any(marker in text for marker in BLOCK_MARKERS):
            raise Blocked(f"{page.url.split('/')[2]} showed a CAPTCHA or block page") from None
        raise


async def snapshot(page: Page, label: str) -> str:
    """Screenshot the page into Object Storage and return the evidence URL."""
    return await evidence.save(label, await page.screenshot(), "png")


async def read_page(url: str) -> dict:
    """Open any page headlessly: its title, visible text and a screenshot as evidence."""

    async def fetch() -> dict:
        async with session() as page:
            await open_page(page, url)
            text = re.sub(r"\n\s*\n+", "\n", await page.inner_text("body"))
            return {"url": url, "title": await page.title(), "text": text[:PAGE_CHARS],
                    "evidence_url": await snapshot(page, f"page {url}"), "fetched_at": datetime.now().isoformat()}

    # fuzzy=False: in DEMO_MODE a page that was never recorded is an error, not some other page's text.
    return await cached(f"browse:{url}".lower(), fetch, ttl_s=24 * 3600, fuzzy=False)
