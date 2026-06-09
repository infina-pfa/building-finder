# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Building Finder is a reverse-lookup web app for Vietnam: given a street address, it returns
the companies registered in that building. It works around the fact that company-data sites
(masothue.com et al.) only let you search by company **name**, not address — so it queries a
Google-style search backend scoped to those sites, then parses, verifies, and dedupes the hits.

## Commands

```bash
# Setup (venv already exists in ./venv)
source venv/bin/activate
pip install -r requirements.txt

# Run tests (no API key needed — search backend is mocked)
python test_app.py
# Run a single test: python -c "import test_app; test_app.test_serpapi_backend()"

# Run locally (needs a real key in env or .env)
export SERPAPI_KEY=...            # OR GOOGLE_API_KEY=... GOOGLE_CX=...
python app.py                     # -> http://localhost:5000

# Run locally with MOCKED search (no key, real UI on :5055)
python _mockrun.py
```

Tests are plain `assert`-based functions invoked from `if __name__ == "__main__"` — there is no
pytest harness. They monkeypatch `lookup.requests.get` / `lookup.google_search` to inject fixtures.

## Architecture

Two source modules with a strict separation:

- **`lookup.py`** — all core logic, UI-agnostic and network-isolated so it's unit-testable.
  The pipeline in `lookup(address, verify)`:
  1. `build_queries()` — produces 3 Google queries scoped to `DATA_SITES` (exact address,
     house-number+street, and a fuzzy keyword query).
  2. `_run_search()` — picks the backend from env vars at call time (**SerpAPI preferred if
     `SERPAPI_KEY` set, else Google CSE via `GOOGLE_API_KEY` + `GOOGLE_CX`**). Both backends
     normalize to a common `{title, snippet, link}` shape.
  3. `address_matches()` — accent-insensitive verification (`strip_accents`); requires house
     number + street + district to all appear, so it filters companies that only share a ward.
  4. `parse_item()` — extracts tax code (`TAXCODE_RE`), company name (`COMPANY_NAME_RE` matches
     legal-entity prefixes like CÔNG TY / CHI NHÁNH), and flags aggregator/listing pages
     (`LISTING_TITLE_RE`) to drop them; recovers a real name from the snippet when the title is a listing.
  5. Dedupe by tax code (fallback URL); drop rows with no name, listing pages, and rows lacking
     both a tax code and an entity prefix.

- **`app.py`** — thin Flask layer over `lookup.py`. Routes: `/` (UI), `/api/lookup` (JSON),
  `/api/lookup.csv` (Excel-safe CSV with BOM), `/healthz`. Backend errors surface as
  `RuntimeError` from `lookup.py` → HTTP 429; missing keys → 503; `verify` query param toggles
  address filtering (`verify=0` = more results, more noise).

- **`templates/index.html`** — single-page UI (search box, results table, CSV/copy export).

Run with `python app.py` (Flask's built-in server). Licensed MIT (see `LICENSE`).

### Key conventions

- **Backend selection is dynamic, read from env on every call** — not cached at import. Tests
  rely on this (they set/clear env vars and re-call `backend_name()`).
- Vietnamese text matching is **accent-insensitive throughout** — always route comparisons
  through `strip_accents()`.
- Adding a data source = append to `DATA_SITES`. Changing what counts as a real company =
  edit `COMPANY_NAME_RE` / `LISTING_TITLE_RE` and add a fixture to `test_app.py`.

## Secrets

`.env` is gitignored — never commit keys. The app loads it via `python-dotenv` on startup;
in any hosted environment set the same vars (`SERPAPI_KEY`, or `GOOGLE_API_KEY` + `GOOGLE_CX`)
through the platform's own config, not a committed file.
