"""Quality checks for a price result. Pure functions, so they run offline in unit tests and in the weekly evals."""
from urllib.parse import urlsplit


def check_result(case: dict, result: dict) -> list[str]:
    """Return a list of problems (empty list = pass). `case` may contain expected_min_price,
    expected_max_price (best effective price range) and expected_stores_any (host fragments)."""
    bad = []
    rows = result.get("results") or []
    if not rows:
        return ["no results"]
    sites = [r["site"].lower() for r in rows]
    if len(set(sites)) != len(sites):
        bad.append("duplicate stores")
    for r in rows:
        p, e = r.get("price"), r.get("effective_price")
        if p is None or e is None:
            bad.append(f"{r['site']}: missing price")
        elif e > p * 1.001:
            bad.append(f"{r['site']}: effective price above listed price")
        if r.get("url") and urlsplit(r["url"]).scheme not in ("http", "https"):
            bad.append(f"{r['site']}: bad url")
        if not r.get("url"):
            bad.append(f"{r['site']}: no product link")
    effs = [r["effective_price"] for r in rows if r.get("effective_price") is not None]
    bd = result.get("best_deal") or {}
    if effs and (bd.get("effective_price") is None or abs(bd["effective_price"] - min(effs)) > 0.01 * min(effs)):
        bad.append("best_deal is not the lowest effective price")
    if not result.get("currency"):
        bad.append("missing currency")
    lo, hi = case.get("expected_min_price"), case.get("expected_max_price")
    if effs and lo is not None and min(effs) < lo:
        bad.append(f"lowest price {min(effs)} below expected {lo} (wrong variant or accessory?)")
    if effs and hi is not None and min(effs) > hi:
        bad.append(f"lowest price {min(effs)} above expected {hi}")
    want = [s.lower() for s in case.get("expected_stores_any", [])]
    if want and not any(w in s for w in want for s in sites):
        bad.append(f"none of the expected stores found: {want}")
    return bad
