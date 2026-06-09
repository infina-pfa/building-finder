"""Tests with mocked search responses — no real API key needed.

Covers both backends (Google CSE and SerpAPI), address filtering, dedupe,
and the Flask endpoints.
    python test_app.py
"""
import os

import lookup as L
import app as A

# --- shared fixtures ---------------------------------------------------------

# Google CSE shape: items have title/snippet/link
CSE_ITEMS = [
    {"title": "0302648340 - CÔNG TY CỔ PHẦN ĐẦU TƯ RÔBỐT - MaSoThue",
     "snippet": "Robot Tower, 308-308C Điện Biên Phủ, Phường 04, Quận 3, TP Hồ Chí Minh",
     "link": "https://masothue.com/0302648340-x"},
    {"title": "0201805597-001 - CHI NHÁNH CÔNG TY TNHH VIETNAM UNISHIPPING",
     "snippet": "Robot Tower, 308-308C Điện Biên Phủ, Phường 04, Quận 3, Thành phố Hồ Chí Minh",
     "link": "https://thuvienphapluat.vn/cn-unishipping.html"},
    {"title": "0316520238 - CÔNG TY TNHH QUANG MINH MOBILE - MaSoThue",   # NOISE
     "snippet": "96 Cao Thắng, Phường 04, Quận 3, TP Hồ Chí Minh",
     "link": "https://masothue.com/0316520238-x"},
]

# SerpAPI raw shape: organic_results -> serpapi_search normalizes it
SERP_RAW = {"organic_results": [
    {"position": 1, "title": "0313756193 - CÔNG TY TNHH AEON TOPVALU VIỆT NAM - MaSoThue",
     "snippet": "Tầng 10, Robot Tower, 308, 308C Điện Biên Phủ, Phường 04, Quận 3",
     "link": "https://masothue.com/0313756193-x"},
    {"position": 2, "title": "0304765787-001 - CHI NHÁNH CÔNG TY TNHH RADIANT GLOBAL ADC VIỆT NAM",
     "snippet": "Robot Tower, 308,308C Điện Biên Phủ, Phường 04, Quận 3, TP Hồ Chí Minh",
     "link": "https://masothue.com/0304765787-x"},
]}

ADDR = "308 Điện Biên Phủ, Quận 3, HCM"


def _clear_keys():
    for k in ("SERPAPI_KEY", "GOOGLE_API_KEY", "GOOGLE_CX"):
        os.environ.pop(k, None)


# --- backend selection + parsing --------------------------------------------

def test_google_backend():
    _clear_keys()
    os.environ["GOOGLE_API_KEY"] = "k"; os.environ["GOOGLE_CX"] = "c"
    L.google_search = lambda q, api_key, cx, num=10: CSE_ITEMS
    assert L.backend_name() == "google_cse"
    rows = L.lookup(ADDR, verify=True)
    names = " | ".join(r["name"] for r in rows)
    assert len(rows) == 2, names               # 2 real, noise dropped, deduped
    assert "QUANG MINH" not in names
    assert any(r["tax_code"] == "0201805597-001" for r in rows)
    print("OK google_cse backend ->", len(rows))


def test_serpapi_backend():
    _clear_keys()
    os.environ["SERPAPI_KEY"] = "serp-test"
    # mock the HTTP layer of serpapi_search
    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return SERP_RAW
    L.requests.get = lambda url, params=None, timeout=30: FakeResp()
    assert L.backend_name() == "serpapi"       # SerpAPI preferred
    # verify normalization produces title/snippet/link
    norm = L.serpapi_search("q", "serp-test")
    assert norm and set(norm[0]) >= {"title", "snippet", "link"}
    rows = L.lookup(ADDR, verify=True)
    names = " | ".join(r["name"] for r in rows)
    assert any("AEON TOPVALU" in n for n in [r["name"] for r in rows]), names
    assert any(r["tax_code"] == "0304765787-001" for r in rows)
    print("OK serpapi backend ->", len(rows))


def test_serpapi_preferred_over_google():
    _clear_keys()
    os.environ["SERPAPI_KEY"] = "s"
    os.environ["GOOGLE_API_KEY"] = "k"; os.environ["GOOGLE_CX"] = "c"
    assert L.backend_name() == "serpapi"
    print("OK serpapi takes priority when both set")


# --- Flask endpoints ---------------------------------------------------------

def test_endpoints():
    _clear_keys()
    os.environ["SERPAPI_KEY"] = "s"
    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return SERP_RAW
    L.requests.get = lambda url, params=None, timeout=30: FakeResp()

    A.app.config["TESTING"] = True
    c = A.app.test_client()

    r = c.get("/api/lookup?address=" + ADDR)
    assert r.status_code == 200, r.data
    j = r.get_json()
    assert j["count"] >= 1 and j["backend"] == "serpapi"
    assert c.get("/api/lookup").status_code == 400           # missing address
    assert c.get("/healthz").get_json()["backend"] == "serpapi"
    cr = c.get("/api/lookup.csv?address=" + ADDR)
    assert cr.status_code == 200 and "0313756193" in cr.data.decode("utf-8")
    assert c.get("/").status_code == 200
    print("OK endpoints (/api/lookup, /healthz, .csv, /) ->", j["count"])


def test_no_keys_503():
    _clear_keys()
    c = A.app.test_client()
    assert c.get("/api/lookup?address=test").status_code == 503
    print("OK no-keys -> 503")


if __name__ == "__main__":
    test_google_backend()
    test_serpapi_backend()
    test_serpapi_preferred_over_google()
    test_endpoints()
    test_no_keys_503()
    print("\nALL TESTS PASS ✓")
