"""
Building Finder — reverse address -> companies (Vietnam).
Flask web app + JSON API. Deployable to Render / Railway / any WSGI host.

Search backend is chosen from environment variables:
    SERPAPI_KEY                  -> use SerpAPI (one key, no daily cap)   [preferred]
    GOOGLE_API_KEY + GOOGLE_CX   -> use Google Custom Search (free 100/day)

Run locally:
    pip install -r requirements.txt
    export SERPAPI_KEY=...            # OR  GOOGLE_API_KEY=... GOOGLE_CX=...
    python app.py
    -> http://localhost:5000
"""
import csv
import io
import os

try:
    from dotenv import load_dotenv  # loads a local .env into the environment
    load_dotenv()
except ImportError:
    pass  # dotenv optional; env vars set in the shell still work

from flask import Flask, jsonify, render_template, request, Response

from lookup import lookup, keys_set, backend_name

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html", keys_set=keys_set(), backend=backend_name())


@app.route("/api/lookup")
def api_lookup():
    address = (request.args.get("address") or "").strip()
    verify = request.args.get("verify", "1") != "0"
    if not address:
        return jsonify({"error": "Missing 'address' parameter"}), 400
    if not keys_set():
        return jsonify({"error": "Server has no search backend configured. "
                                 "Set SERPAPI_KEY, or GOOGLE_API_KEY + GOOGLE_CX."}), 503
    try:
        rows = lookup(address, verify=verify)
    except RuntimeError as e:          # quota / key / backend errors
        return jsonify({"error": str(e)}), 429
    except Exception as e:
        return jsonify({"error": f"Lookup failed: {e}"}), 502
    return jsonify({"address": address, "count": len(rows),
                    "backend": backend_name(), "results": rows})


@app.route("/api/lookup.csv")
def api_lookup_csv():
    address = (request.args.get("address") or "").strip()
    verify = request.args.get("verify", "1") != "0"
    if not address or not keys_set():
        return Response("error", status=400)
    rows = lookup(address, verify=verify)

    buf = io.StringIO()
    buf.write("﻿")  # BOM so Excel reads UTF-8
    w = csv.DictWriter(buf, fieldnames=["tax_code", "name", "address", "url"])
    w.writeheader()
    w.writerows(rows)
    fname = "companies_" + "".join(c if c.isalnum() else "_" for c in address)[:40] + ".csv"
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "keys_set": keys_set(), "backend": backend_name()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
