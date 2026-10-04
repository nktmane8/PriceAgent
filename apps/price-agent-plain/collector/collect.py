"""Collector: reads product pages (or a CSV), extracts prices, and sends them to the Node API.
  python collect.py sources.json            # fetch pages listed in sources.json
  python collect.py --csv prices.csv        # import prices from a CSV file
  add --dry-run to print instead of sending. Env: API_URL (default http://localhost:3000), INGEST_KEY (secret)."""
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

import jsonld
import safefetch

DELAY_SECONDS = 2   # be polite: one request every couple of seconds


def item_from_page(src: dict, html: str):
    """Build one API item from a source entry and its page, or None if no price was found."""
    offers = jsonld.extract_offers(html)
    if not offers:
        return None
    o = offers[0]
    if not o["currency"]:
        return None
    return {"product": src["product"], "store": src["store"], "storeType": src.get("store_type", "marketplace"),
            "country": src["country"], "city": src.get("city"), "price": o["price"], "currency": o["currency"],
            "inStock": o["in_stock"], "url": src["url"]}


def collect(sources, fetch=safefetch.fetch, allowed=safefetch.allowed, sleep=time.sleep):
    items, report = [], []
    for s in sources:
        try:
            if not allowed(s["url"]):
                report.append((s["url"], "skipped: robots.txt disallows")); continue
            item = item_from_page(s, fetch(s["url"]))
            if item:
                items.append(item); report.append((s["url"], f"ok {item['currency']} {item['price']}"))
            else:
                report.append((s["url"], "skipped: no structured price on the page"))
        except safefetch.FetchError as e:
            report.append((s["url"], f"skipped: {e}"))
        sleep(DELAY_SECONDS)
    return items, report


def items_from_csv(path):
    """Columns: product,store,store_type,country,city,price,currency,instant_discount,discount_note,in_stock,url"""
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            it = {"product": row["product"].strip(), "store": row["store"].strip(), "storeType": (row.get("store_type") or "marketplace").strip(),
                  "country": row["country"].strip(), "city": (row.get("city") or "").strip() or None,
                  "price": float(row["price"]), "currency": row["currency"].strip().upper()}
            if row.get("instant_discount"):
                it["instantDiscount"] = float(row["instant_discount"]); it["discountNote"] = (row.get("discount_note") or "").strip()
            if row.get("in_stock"):
                it["inStock"] = row["in_stock"].strip().lower() in ("1", "true", "yes")
            if row.get("url"):
                it["url"] = row["url"].strip()
            out.append(it)
    return out


def post(items, api_url, key):
    for i in range(0, len(items), 500):  # API accepts at most 500 per call
        req = urllib.request.Request(api_url.rstrip("/") + "/api/ingest", method="POST", data=json.dumps({"items": items[i:i + 500]}).encode(),
                                     headers={"Content-Type": "application/json", "x-ingest-key": key})
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="?")
    ap.add_argument("--csv")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if bool(a.sources) == bool(a.csv):
        ap.error("give either a sources.json file or --csv FILE")
    if a.csv:
        items, report = items_from_csv(a.csv), []
    else:
        items, report = collect(json.load(open(a.sources, encoding="utf-8")))
    for url, status in report:
        print(f"{status:60.60}  {url}")
    print(f"{len(items)} item(s) ready")
    if a.dry_run or not items:
        print(json.dumps(items, indent=2)) if a.dry_run else None
        return 0 if (items or a.dry_run) else 1
    key = os.environ.get("INGEST_KEY")
    if not key:
        print("INGEST_KEY is not set", file=sys.stderr); return 2
    try:
        post(items, os.environ.get("API_URL", "http://localhost:3000"), key)
    except (urllib.error.URLError, OSError) as e:
        print(f"could not send to the API: {e}", file=sys.stderr); return 2
    print("sent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
