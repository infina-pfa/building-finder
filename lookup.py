"""
Core reverse-lookup logic: address -> companies registered there.

Strategy: masothue.com (and similar) have a page per company INCLUDING its
full registered address, but their on-site search only matches company names.
Google has indexed those pages, so we query Google (Custom Search JSON API)
scoped to those data sites with the address, then parse + verify + dedupe.

This module is UI-agnostic and unit-testable: the network call is isolated in
`google_search` so tests can inject results.
"""
import os
import re
import unicodedata

import requests

DATA_SITES = [
    "masothue.com",
    "thuvienphapluat.vn",
    "infodoanhnghiep.com",
    "tratencongty.com",
    "trangvangvietnam.org",
]

TAXCODE_RE = re.compile(r"\b(\d{10}(?:-\d{3})?)\b")
CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
SERPAPI_ENDPOINT = "https://serpapi.com/search"


def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s or "")
        if unicodedata.category(c) != "Mn"
    ).lower()


def build_queries(address: str):
    sites = " OR ".join("site:" + s for s in DATA_SITES)
    num_street = address.split(",")[0].strip()
    return [
        f'({sites}) "{address}"',
        f'({sites}) "{num_street}"',
        f'({sites}) {address} công ty mã số thuế',
    ]


def google_search(query, api_key, cx, num=10):
    """Call Google Custom Search JSON API. Returns list of result items
    with keys: title, snippet, link."""
    r = requests.get(CSE_ENDPOINT, params={
        "key": api_key, "cx": cx, "q": query, "num": num,
    }, timeout=30)
    if r.status_code == 429:
        raise RuntimeError("Google API daily quota exceeded (100/day on free tier).")
    r.raise_for_status()
    return r.json().get("items", [])


def serpapi_search(query, serpapi_key, num=10):
    """Call SerpAPI (Google engine). Normalizes organic_results to the same
    {title, snippet, link} shape used by google_search/parse_item."""
    r = requests.get(SERPAPI_ENDPOINT, params={
        "engine": "google", "q": query, "api_key": serpapi_key,
        "num": num, "hl": "vi", "gl": "vn",
    }, timeout=30)
    if r.status_code in (401, 403):
        raise RuntimeError("SerpAPI key rejected (check SERPAPI_KEY).")
    if r.status_code == 429:
        raise RuntimeError("SerpAPI rate/credit limit reached.")
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise RuntimeError(f"SerpAPI: {data['error']}")
    out = []
    for it in data.get("organic_results", []):
        out.append({
            "title": it.get("title", ""),
            "snippet": it.get("snippet", "") or it.get("snippet_highlighted_words", ""),
            "link": it.get("link", ""),
        })
    return out


# Titles of aggregator/listing pages, not a single company
LISTING_TITLE_RE = re.compile(
    r"danh sách|doanh nghiệp tại|công ty tại|tra cứu|trang \d+", re.I)
# A real company name starts with one of these legal-entity prefixes
COMPANY_NAME_RE = re.compile(
    r"((?:CÔNG TY|CHI NHÁNH|VĂN PHÒNG ĐẠI DIỆN|VPĐD|DOANH NGHIỆP|HỘ KINH DOANH|TỔNG CÔNG TY)[^\n]*?)"
    r"(?=\s*[-–]\s*(?:Mã số thuế|MaSoThue|MST)|\s*[-–]\s*Địa chỉ|$)", re.I)


def _clean_name(s: str) -> str:
    s = re.sub(r"^\d{10}(?:-\d{3})?\s*[-–]\s*", "", s).strip()
    # cut anything from a trailing "- Mã số thuế / MST / Địa chỉ / MaSoThue" onward
    s = re.split(r"\s*[-–.]?\s*(?:Mã số thuế|MaSoThue|MST|Địa chỉ)\b", s, flags=re.I)[0]
    s = s.rstrip(" .,-–").strip()
    return s


def parse_item(item: dict) -> dict:
    title = item.get("title", "") or ""
    snippet = item.get("snippet", "") or ""
    link = item.get("link", "") or ""
    m = TAXCODE_RE.search(title) or TAXCODE_RE.search(snippet) or TAXCODE_RE.search(link)

    is_listing = bool(LISTING_TITLE_RE.search(title))
    name = _clean_name(title)

    # If the title is a listing/aggregator page (or has no entity prefix),
    # try to recover the real company name from the snippet.
    if is_listing or not COMPANY_NAME_RE.search(name):
        sm = COMPANY_NAME_RE.search(snippet)
        if sm:
            name = _clean_name(sm.group(1))
            is_listing = False  # we recovered a real company

    return {
        "tax_code": m.group(1) if m else "",
        "name": name,
        "address": snippet.strip(),
        "url": link,
        "is_listing": is_listing,
    }


def address_matches(item_blob: str, address: str) -> bool:
    """House number + street + district must all appear (accent-insensitive)."""
    b = strip_accents(item_blob)
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if not parts:
        return True
    needles = []
    first = strip_accents(parts[0])
    num_m = re.search(r"\d+[a-z]?", first)
    if num_m:
        needles.append(num_m.group(0))
    street = re.sub(r"^\s*\d+[a-z]?[\s,-]*", "", first)
    street = re.sub(r"^(duong|pho)\s+", "", street).strip()
    if street:
        needles.append(street)
    for p in parts[1:]:
        sp = strip_accents(p)
        dm = re.search(r"(?:qu[aâ]n|district)\s*(\d+)", sp)
        if dm:
            needles.append("quan " + dm.group(1))
            b = re.sub(r"district\s*(\d+)", r"quan \1", b)
    return all(n in b for n in needles if n)


def _run_search(query):
    """Pick a backend based on which keys are set. SerpAPI preferred when present
    (one key, no daily cap), else Google CSE."""
    serp = os.environ.get("SERPAPI_KEY")
    if serp:
        return serpapi_search(query, serp)
    api_key, cx = os.environ.get("GOOGLE_API_KEY"), os.environ.get("GOOGLE_CX")
    if api_key and cx:
        return google_search(query, api_key, cx)
    raise RuntimeError("No search backend configured. Set SERPAPI_KEY, "
                       "or GOOGLE_API_KEY + GOOGLE_CX.")


def lookup(address: str, verify: bool = True) -> list:
    """Main entry: return deduped list of companies at `address`.
    Backend is chosen from environment (SerpAPI or Google CSE)."""
    seen, rows = set(), []
    for q in build_queries(address):
        for it in _run_search(q):
            blob = f"{it.get('title','')} {it.get('snippet','')}"
            if verify and not address_matches(blob, address):
                continue
            parsed = parse_item(it)
            if not parsed["name"] or parsed.get("is_listing"):
                continue                       # skip aggregator/listing pages
            # require a real company (has a tax code OR a legal-entity prefix)
            if not parsed["tax_code"] and not COMPANY_NAME_RE.search(parsed["name"]):
                continue
            key = parsed["tax_code"] or parsed["url"]
            if key not in seen:
                seen.add(key)
                rows.append({k: v for k, v in parsed.items() if k != "is_listing"})
    return rows


def backend_name():
    if os.environ.get("SERPAPI_KEY"):
        return "serpapi"
    if os.environ.get("GOOGLE_API_KEY") and os.environ.get("GOOGLE_CX"):
        return "google_cse"
    return None


def keys_set() -> bool:
    return backend_name() is not None
