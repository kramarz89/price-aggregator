# CLAUDE.md

@~/.claude/coding-rules.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
source .venv/bin/activate

uvicorn app:app --reload            # web UI (text + image search) at http://127.0.0.1:8000
python main.py "laptop lenovo"      # CLI search

pytest                              # run tests
python tests/update_fixtures.py    # refresh HTML fixtures (required before first test run)
```

Image search needs `GOOGLE_VISION_API_KEY` in `.env` (see `.env.example`). Text search works without it.

## Deployment

Deployed 24/7 as a Docker container on a home TrueNAS SCALE box. Build and run with
`docker compose up`. The host-specific ship/update procedure lives in the maintainer's private
notes (`~/notes/price_aggregator.md`). The NAS keeps running the old image until it is rebuilt
and reloaded, so after changing app code, offer to redeploy: rebuild the image, load it on the
NAS, then bump the app's image tag.

## Architecture

Plugin/strategy pattern — each scraper is an independent class inheriting from `ScraperBase`.
Two front-ends (CLI `main.py`, web `app.py`) share one pipeline in `search_service.py`.

```
app.py                # FastAPI: GET / , GET /search , POST /resolve-image
main.py               # CLI entry point: search → Jinja2 render → webbrowser.open
search_service.py     # shared pipeline: search_all, render_results, export_to_excel
image_search.py       # image → query via Google Vision WEB_DETECTION (httpx REST)
config.py             # env vars via python-dotenv
models.py             # Product dataclass — shared model for all scrapers
scrapers/
  base.py             # ScraperBase ABC + shared parse_polish_price()
  ceneo.py            # httpx + BeautifulSoup
  olx.py              # httpx + BeautifulSoup, parallel image enrichment
  sprzedajemy.py      # httpx + BeautifulSoup
  allegro.py          # Playwright stub — blocked by DataDome (see ROADMAP)
templates/
  index.html          # landing: search box + image paste/drop zone
  results.html        # Jinja2 (autoescape=True) + vanilla JS filtering/sorting/carousel
tests/
  fixtures/           # real HTML snapshots (git-ignored, generate with update_fixtures.py)
  update_fixtures.py  # re-captures fixtures from live sites
```

## Adding a new scraper

1. Create `scrapers/yoursite.py` subclassing `ScraperBase`
2. Implement `search(query, limit)` returning `List[Product]`
3. Use `self.parse_polish_price(raw)` for price parsing
4. Add to the scrapers list in `search_service.py`
5. Add fixture and `TestYoursiteParser` class in `tests/test_scrapers.py`

## Test strategy

Fixture-based: parsers are tested against real captured HTML, not mocked HTTP.
This catches layout changes on live sites. When a scraper breaks, run
`update_fixtures.py` to refresh, then fix the parser to match the new structure.
