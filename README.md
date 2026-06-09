# Building Finder — reverse address → companies (Vietnam)

A deployable web app: type an address, get the companies registered in that building.
Solves the problem fintech/KYB providers don't (they only do tax-code → address).

## How it works

masothue.com has a page per company including its full registered address, but its
on-site search only matches company **names**, not addresses. Google has indexed those
pages, so the app queries the **Google Custom Search API** scoped to company-data sites
with the address, then parses, **verifies the address**, and dedupes the results.

Verified live on Robot Tower (308 Điện Biên Phủ, Q3) — returns the real tenants and
filters out companies that only share the ward. Logic is covered by `test_app.py`.

## 1. Pick a search backend (you only need ONE)

The app auto-selects a backend from environment variables. If `SERPAPI_KEY` is
set it's used; otherwise it falls back to the Google keys.

- **SerpAPI (recommended): one key, no daily cap.** Get it at
  https://serpapi.com/manage-api-key → that's your `SERPAPI_KEY`.
- **Google Custom Search (free 100/day): two values.**
  `GOOGLE_CX` from https://programmablesearchengine.google.com/ ("Search the entire web" ON),
  `GOOGLE_API_KEY` from https://console.cloud.google.com/apis/credentials (enable "Custom Search API").

## 2. Run locally

```bash
pip install -r requirements.txt
export SERPAPI_KEY="your-serpapi-key"      # OR the two GOOGLE_ vars
python app.py
# open http://localhost:5000
```

(Windows PowerShell: `setx SERPAPI_KEY "..."` then restart the shell, or use a `.env`.)

## 3. Deploy (so Kiet's team can use a URL)

**Render (easiest, free tier):**
1. Push this folder to a GitHub repo.
2. On https://render.com → New → Web Service → connect the repo.
3. It auto-detects `render.yaml`. In the dashboard, set `SERPAPI_KEY`
   (or `GOOGLE_API_KEY` + `GOOGLE_CX`) — they are `sync: false`, never committed.
4. Deploy. Start command is `gunicorn app:app`.

**Railway / Fly / any host:** use the `Procfile` (`web: gunicorn app:app`) and set the
same two env vars in that platform's settings.

> 🔒 Never commit your keys. `.env` is gitignored; on hosts, set keys in the dashboard.

## Files

| File | Purpose |
|---|---|
| `app.py` | Flask app: `/`, `/api/lookup`, `/api/lookup.csv`, `/healthz` |
| `lookup.py` | Core logic (query build, Google call, parse, address verify, dedupe) |
| `templates/index.html` | UI: search box, results table, CSV/copy export |
| `test_app.py` | Tests with mocked Google response (no key needed): `python test_app.py` |
| `requirements.txt`, `Procfile`, `render.yaml` | Deployment |
| `.env.example`, `.gitignore` | Config template + safety |

## API

```
GET /api/lookup?address=308 Điện Biên Phủ, Quận 3&verify=1
  -> {"address":..., "count":N, "results":[{tax_code,name,address,url}, ...]}

GET /api/lookup.csv?address=...     -> CSV download
GET /healthz                        -> {"ok":true,"keys_set":bool}
```

`verify=0` disables address filtering (more results, more noise).

## Limits / next steps

- Coverage depends on Google's index of masothue et al. — good for most buildings, not 100%.
- For guaranteed completeness: license registry-derived data (National Business
  Registration Portal via a KYB vendor) with the address field and build a normalized
  address index. That's the real "data partner" answer — paid, not a free endpoint.
- Easy upgrades: add SerpAPI fallback for quota overflow; cache results; add a map view.
