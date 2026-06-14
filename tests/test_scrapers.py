from decimal import Decimal
from pathlib import Path

import pytest

from scrapers.amazon import AmazonScraper
from scrapers.base import parse_polish_price
from scrapers.ceneo import CeneoScraper
from scrapers.olx import OlxScraper
from scrapers.sprzedajemy import SprzedajemyScraper
from scrapers.vinted import VintedScraper

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestCeneoParser:
    def setup_method(self):
        self.scraper = CeneoScraper()
        self.html = load("ceneo_laptop_lenovo.html")

    def test_returns_results(self):
        products = self.scraper._parse(self.html, limit=20)
        assert len(products) > 0

    def test_respects_limit(self):
        products = self.scraper._parse(self.html, limit=5)
        assert len(products) <= 5

    def test_product_fields(self):
        product = self.scraper._parse(self.html, limit=1)[0]
        assert product.name
        assert product.price > 0
        assert product.url.startswith("https://www.ceneo.pl/")
        assert product.source == "Ceneo"

    def test_price_is_decimal(self):
        products = self.scraper._parse(self.html, limit=5)
        for product in products:
            assert isinstance(product.price, Decimal)

    def test_image_url_is_absolute(self):
        products = self.scraper._parse(self.html, limit=5)
        for product in products:
            if product.image_url:
                assert product.image_url.startswith("https://")

    def test_free_shipping_parsed(self):
        products = self.scraper._parse(self.html, limit=20)
        free = [product for product in products if product.shipping_price == Decimal("0")]
        assert len(free) > 0, "Expected at least one offer with free shipping"


class TestOlxParser:
    def setup_method(self):
        self.scraper = OlxScraper()
        self.html = load("olx_laptop_lenovo.html")

    def test_returns_results(self):
        products = self.scraper._parse(self.html, limit=20)
        assert len(products) > 0

    def test_respects_limit(self):
        products = self.scraper._parse(self.html, limit=3)
        assert len(products) <= 3

    def test_product_fields(self):
        products = self.scraper._parse(self.html, limit=20)
        product = products[0]
        assert product.name
        assert product.price > 0
        assert product.url.startswith("https://www.olx.pl/")
        assert product.source == "OLX"

    def test_location_stripped_of_date(self):
        products = self.scraper._parse(self.html, limit=20)
        located = [product for product in products if product.location]
        assert located, "Expected at least one product with location"
        for product in located:
            assert "Odświeżono" not in product.location
            assert "dnia" not in product.location

    def test_skips_non_numeric_prices(self):
        products = self.scraper._parse(self.html, limit=20)
        for product in products:
            assert isinstance(product.price, Decimal)


class TestSprzedajemyParser:
    def setup_method(self):
        self.scraper = SprzedajemyScraper()
        self.html = load("sprzedajemy_laptop_lenovo.html")

    def test_returns_results(self):
        products = self.scraper._parse(self.html, limit=20)
        assert len(products) > 0

    def test_respects_limit(self):
        products = self.scraper._parse(self.html, limit=4)
        assert len(products) <= 4

    def test_product_fields(self):
        product = self.scraper._parse(self.html, limit=1)[0]
        assert product.name
        assert product.price > 0
        assert product.url.startswith("https://sprzedajemy.pl/")
        assert product.source == "Sprzedajemy"

    def test_location_present(self):
        products = self.scraper._parse(self.html, limit=10)
        located = [product for product in products if product.location]
        assert len(located) > 0

    def test_image_url_present(self):
        products = self.scraper._parse(self.html, limit=10)
        with_img = [product for product in products if product.image_url]
        assert len(with_img) > 0


class TestAmazonParser:
    def setup_method(self):
        self.scraper = AmazonScraper()
        self.html = load("amazon_laptop_lenovo.html")

    def test_returns_results(self):
        products = self.scraper._parse(self.html, limit=20)
        assert len(products) > 0

    def test_respects_limit(self):
        products = self.scraper._parse(self.html, limit=5)
        assert len(products) <= 5

    def test_product_fields(self):
        product = self.scraper._parse(self.html, limit=1)[0]
        assert product.name
        assert product.price > 0
        assert product.url.startswith("https://www.amazon.pl/dp/")
        assert product.source == "Amazon"

    def test_url_uses_asin(self):
        products = self.scraper._parse(self.html, limit=10)
        for product in products:
            assert "/dp/" in product.url

    def test_free_shipping_detected(self):
        products = self.scraper._parse(self.html, limit=20)
        free = [product for product in products if product.shipping_price == Decimal("0")]
        assert len(free) > 0

    def test_image_url_present(self):
        products = self.scraper._parse(self.html, limit=10)
        with_img = [product for product in products if product.image_url]
        assert len(with_img) > 0

    def test_empty_html_returns_empty_list(self):
        products = self.scraper._parse("<html><body></body></html>", limit=20)
        assert products == []


class TestVintedParser:
    def setup_method(self):
        self.scraper = VintedScraper()
        self.html = load("vinted_laptop_lenovo.html")

    def test_returns_results(self):
        products = self.scraper._parse(self.html, limit=20)
        assert len(products) > 0

    def test_respects_limit(self):
        products = self.scraper._parse(self.html, limit=5)
        assert len(products) <= 5

    def test_product_fields(self):
        product = self.scraper._parse(self.html, limit=1)[0]
        assert product.name
        assert product.price > 0
        assert product.url.startswith("https://www.vinted.pl/items/")
        assert product.source == "Vinted"

    def test_url_has_no_referrer_param(self):
        products = self.scraper._parse(self.html, limit=10)
        for product in products:
            assert "referrer" not in product.url

    def test_condition_mapped(self):
        products = self.scraper._parse(self.html, limit=20)
        mapped = [product for product in products if product.condition is not None]
        assert len(mapped) > 0
        for product in mapped:
            assert product.condition in ("NEW", "USED")

    def test_image_url_present(self):
        products = self.scraper._parse(self.html, limit=10)
        with_img = [product for product in products if product.image_url]
        assert len(with_img) > 0


class TestPolishPriceParser:
    @pytest.mark.parametrize("raw,expected", [
        ("999 zł",        Decimal("999")),
        ("1 234 zł",      Decimal("1234")),
        ("14\xa0999 zł",  Decimal("14999")),
        ("1 234,99 zł",   Decimal("1234.99")),
        ("1.234,99 zł",   Decimal("1234.99")),
        ("14,99 zł",      Decimal("14.99")),
        ("0 zł",          Decimal("0")),
    ])
    def test_valid_prices(self, raw, expected):
        assert parse_polish_price(raw) == expected

    @pytest.mark.parametrize("raw", ["Zamień", "Negocjuj", "Za darmo", ""])
    def test_non_numeric_returns_none(self, raw):
        assert parse_polish_price(raw) is None
