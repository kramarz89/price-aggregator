import asyncio
import sys
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from models import Product
from scrapers.amazon import AmazonScraper
from scrapers.ceneo import CeneoScraper
from scrapers.olx import OlxScraper
from scrapers.sprzedajemy import SprzedajemyScraper
from scrapers.vinted import VintedScraper

# Re-created once at import time — both entry points render on every request
_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=True,
)


async def search_all(query: str) -> list[Product]:
    scrapers = [
        CeneoScraper(),
        OlxScraper(fetch_images=True),
        SprzedajemyScraper(),
        VintedScraper(),
        AmazonScraper(),
    ]
    try:
        results = await asyncio.gather(
            *(s.search(query, limit=30) for s in scrapers),
            return_exceptions=True,
        )
    finally:
        for s in scrapers:
            try:
                await s.close()
            except Exception as e:
                print(f"[close error] {type(e).__name__}: {e}", file=sys.stderr)

    products: list[Product] = []
    for outcome in results:
        if isinstance(outcome, Exception):
            print(f"[scraper error] {outcome}", file=sys.stderr)
        else:
            products.extend(outcome)

    return sorted(products, key=lambda p: p.price)


def render_results(query: str, products: list[Product]) -> str:
    template = _env.get_template("results.html")
    sources = sorted({p.source for p in products})
    return template.render(query=query, products=products, sources=sources)


def export_to_excel(query: str, products: list[Product], path: Path) -> None:
    rows = [
        {
            "Nazwa": p.name,
            "Cena (zł)": float(p.price),
            "Dostawa (zł)": float(p.shipping_price) if p.shipping_price is not None else "",
            "Łącznie (zł)": float(p.total_price),
            "Źródło": p.source,
            "Stan": p.condition_display or "",
            "Lokalizacja": p.location or "",
            "Sprzedawca": p.seller or "",
            "URL": p.url,
        }
        for p in products
    ]
    df = pd.DataFrame(rows)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=query[:31])
        ws = writer.sheets[query[:31]]
        ws.column_dimensions["A"].width = 55
        ws.column_dimensions["I"].width = 60
    print(f"Exported: {path}")
