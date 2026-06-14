import asyncio
import logging
import random
from decimal import Decimal
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from models import Product
from scrapers.base import ScraperBase, parse_polish_price

logger = logging.getLogger(__name__)

_BASE = "https://www.amazon.pl"
_SEARCH_URL = f"{_BASE}/s"

_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
Object.defineProperty(navigator, 'languages', {get: () => ['pl-PL', 'pl', 'en-US', 'en']});
window.chrome = {runtime: {}};
""".strip()


class AmazonScraper(ScraperBase):
    source_name = "Amazon"

    async def search(self, query: str, limit: int = 20) -> list[Product]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            ctx = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="pl-PL",
                viewport={"width": 1280, "height": 900},
                extra_http_headers={
                    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
                },
            )
            await ctx.add_init_script(_STEALTH_JS)
            page = await ctx.new_page()

            try:
                await page.goto(
                    f"{_SEARCH_URL}?k={quote_plus(query)}",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )

                try:
                    await page.wait_for_selector(
                        '[data-component-type="s-search-result"]',
                        timeout=10000,
                    )
                except Exception:
                    # Either blocked (captcha form) or genuinely no results
                    html = await page.content()
                    if "captcha" in html.lower() or "Enter the characters" in html:
                        logger.warning("Amazon: blocked by captcha, returning empty results")
                    else:
                        logger.warning("Amazon: no results found for %r", query)
                    return []

                # jittered delay to avoid rate-limiting
                await asyncio.sleep(random.uniform(0.8, 1.5))
                html = await page.content()
            finally:
                await browser.close()

        return self._parse(html, limit)

    def _parse(self, html: str, limit: int) -> list[Product]:
        soup = BeautifulSoup(html, "lxml")
        cards = [
            c for c in soup.find_all(attrs={"data-component-type": "s-search-result"})
            if c.get("data-asin")
        ][:limit]
        return [p for p in (self._parse_card(c) for c in cards) if p]

    def _parse_card(self, card) -> Product | None:
        asin = card.get("data-asin", "")
        if not asin:
            return None

        # Fashion category: h2 has only brand name; full title is in a[class*=s-line-clamp] span
        # Electronics: both selectors return the same text — prefer the link span
        title_el = card.select_one('a[class*="s-line-clamp"] span') or card.select_one("h2 > span")
        if not title_el:
            return None
        name = title_el.get_text(strip=True)
        if not name:
            return None

        price_el = card.select_one(".a-price .a-offscreen")
        price = parse_polish_price(price_el.get_text(strip=True) if price_el else "")
        if price is None:
            return None

        delivery_el = card.select_one('[data-cy="delivery-recipe"]')
        delivery_text = delivery_el.get_text() if delivery_el else ""
        shipping = None
        if "DARMOW" in delivery_text or "darmow" in delivery_text:
            shipping = Decimal("0")

        img = card.select_one("img.s-image")
        image_url = img.get("src") if img else None

        return Product(
            name=name,
            price=price,
            url=f"{_BASE}/dp/{asin}",
            source=self.source_name,
            image_url=image_url,
            shipping_price=shipping,
        )
