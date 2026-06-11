import asyncio
import random
from abc import ABC, abstractmethod

import structlog
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from app.scrapers.models import RawListing

logger = structlog.get_logger()

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]


class BaseScraper(ABC):
    def __init__(self, min_delay: float = 2.0, max_delay: float = 5.0, max_retries: int = 3):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self._playwright = None
        self._browser: Browser | None = None

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...

    @abstractmethod
    async def scrape(self, criteria: dict) -> list[RawListing]:
        ...

    async def start_browser(self) -> Browser:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-software-rasterizer",
                "--js-flags=--max-old-space-size=256",
            ],
        )
        return self._browser

    async def new_context(self) -> BrowserContext:
        if not self._browser:
            await self.start_browser()

        viewport = {
            "width": random.randint(1280, 1920),
            "height": random.randint(720, 1080),
        }
        context = await self._browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport=viewport,
            locale="en-US",
            timezone_id="America/New_York",
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            window.chrome = {runtime: {}};
        """)
        return context

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def random_delay(self):
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)

    async def safe_goto(self, page: Page, url: str, wait_until: str = "domcontentloaded") -> bool:
        for attempt in range(self.max_retries):
            try:
                await page.goto(url, wait_until=wait_until, timeout=30000)
                await self.random_delay()
                return True
            except Exception as e:
                logger.warning(
                    "Navigation failed, retrying",
                    url=url, attempt=attempt + 1, error=str(e),
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))
        return False
