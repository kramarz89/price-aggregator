import asyncio
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from models import Product
from scrapers.base import ScraperBase, parse_polish_price

_BASE = "https://www.vinted.pl"
_SEARCH_URL = f"{_BASE}/catalog"

_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
Object.defineProperty(navigator, 'languages', {get: () => ['pl-PL', 'pl', 'en-US', 'en']});
window.chrome = {runtime: {}};
""".strip()

_ITEM_RE = re.compile(r"^product-item-id-\d+$")

_CONDITION_MAP = {
    "Nowy z metką": "NEW",
    "Nowy bez metki": "NEW",
    "Bardzo dobry": "USED",
    "Dobry": "USED",
    "Dostateczny": "USED",
    "Zadowalający": "USED",
    "Do naprawy": "USED",
}


class VintedScraper(ScraperBase):
    source_name = "Vinted"

    async def search(self, query: str, limit: int = 20) -> list[Product]:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
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
            await context.add_init_script(_STEALTH_JS)
            page = await context.new_page()

            try:
                await page.goto(
                    f"{_SEARCH_URL}?search_text={quote_plus(query)}",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                await page.wait_for_selector('[data-testid^="product-item-id-"]', timeout=15000)
                await asyncio.sleep(1.0)
                html = await page.content()
            finally:
                await browser.close()

        return self._parse(html, limit)

    def _parse(self, html: str, limit: int) -> list[Product]:
        soup = BeautifulSoup(html, "lxml")
        containers = soup.find_all(attrs={"data-testid": _ITEM_RE})[:limit]
        return [product for product in (self._parse_item(container) for container in containers) if product]

    def _parse_item(self, container) -> Product | None:
        link = container.select_one("a.new-item-box__overlay")
        if not link:
            return None

        title_attr = link.get("title", "")
        name = title_attr.split(", marka:")[0].strip() if title_attr else ""
        if not name:
            return None

        url = link.get("href", "").split("?")[0]
        if not url:
            return None

        price_el = container.select_one('[data-testid$="--price-text"]')
        price = parse_polish_price(price_el.get_text(strip=True) if price_el else "")
        if price is None:
            return None

        condition_el = container.select_one('[data-testid$="--description-subtitle"]')
        condition_text = condition_el.get_text(strip=True) if condition_el else ""
        condition = _CONDITION_MAP.get(condition_text)

        image_el = container.find("img")
        image_url = image_el.get("src") if image_el else None

        return Product(
            name=name,
            price=price,
            url=url,
            source=self.source_name,
            image_url=image_url,
            condition=condition,
        )
