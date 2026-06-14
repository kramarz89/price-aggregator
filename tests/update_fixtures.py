"""
Run this script to refresh HTML fixtures when scrapers break due to site changes:

    python tests/update_fixtures.py
"""
import asyncio
import re
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

FIXTURES = Path(__file__).parent / "fixtures"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
Object.defineProperty(navigator, 'languages', {get: () => ['pl-PL', 'pl', 'en-US', 'en']});
window.chrome = {runtime: {}};
""".strip()

HTTPX_SOURCES = [
    ("ceneo_laptop_lenovo.html",       "https://www.ceneo.pl/szukaj-laptop+lenovo"),
    ("olx_laptop_lenovo.html",         "https://www.olx.pl/oferty/q-laptop-lenovo/"),
    ("sprzedajemy_laptop_lenovo.html", "https://sprzedajemy.pl/szukaj?schm2=hp&inp_text[v]=laptop+lenovo&inp_category_id=5&catCode="),
]


async def fetch_httpx() -> None:
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20.0) as c:
        for filename, url in HTTPX_SOURCES:
            print(f"Fetching {url} ...", end=" ", flush=True)
            resp = await c.get(url)
            path = FIXTURES / filename
            path.write_text(resp.text, encoding="utf-8")
            print(f"{resp.status_code} → {path.name} ({len(resp.text):,} chars)")


async def _playwright_context(playwright):
    browser = await playwright.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = await browser.new_context(
        user_agent=HEADERS["User-Agent"],
        locale="pl-PL",
        viewport={"width": 1280, "height": 900},
        extra_http_headers={"Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"},
    )
    await context.add_init_script(_STEALTH_JS)
    return browser, context


async def fetch_vinted(playwright) -> None:
    url = "https://www.vinted.pl/catalog?search_text=laptop+lenovo"
    print(f"Fetching {url} ...", end=" ", flush=True)
    browser, context = await _playwright_context(playwright)
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_selector('[data-testid^="product-item-id-"]', timeout=15000)
        await asyncio.sleep(1.0)
        html = await page.evaluate("""() => {
            const items = [...document.querySelectorAll('[data-testid]')]
                .filter(el => /^product-item-id-\\d+$/.test(el.dataset.testid))
                .slice(0, 30);
            const grid = items.map(el => el.outerHTML).join('\\n');
            return `<!DOCTYPE html><html><body><div class="feed-grid">${grid}</div></body></html>`;
        }""")
        path = FIXTURES / "vinted_laptop_lenovo.html"
        path.write_text(html, encoding="utf-8")
        print(f"200 → {path.name} ({len(html):,} chars)")
    finally:
        await browser.close()


async def fetch_amazon(playwright) -> None:
    url = "https://www.amazon.pl/s?k=laptop+lenovo"
    print(f"Fetching {url} ...", end=" ", flush=True)
    browser, context = await _playwright_context(playwright)
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_selector('[data-component-type="s-search-result"]', timeout=10000)
        await asyncio.sleep(1.0)
        html = await page.evaluate("""() => {
            const cards = [...document.querySelectorAll('[data-component-type="s-search-result"][data-asin]')]
                .slice(0, 30);
            const grid = cards.map(el => el.outerHTML).join('\\n');
            return `<!DOCTYPE html><html><body><div class="s-result-list">${grid}</div></body></html>`;
        }""")
        path = FIXTURES / "amazon_laptop_lenovo.html"
        path.write_text(html, encoding="utf-8")
        print(f"200 → {path.name} ({len(html):,} chars)")
    finally:
        await browser.close()


async def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    await fetch_httpx()
    async with async_playwright() as playwright:
        await fetch_vinted(playwright)
        await fetch_amazon(playwright)


if __name__ == "__main__":
    asyncio.run(main())
