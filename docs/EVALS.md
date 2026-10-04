# Evals: catching silent regressions
Real searches change daily, so the evals check **properties that must always hold** and, where you supply them, **price ranges you verified yourself**.

## Built-in checks (`evals/checks.py`)
No duplicate stores; every offer has price, effective price and an http(s) link; effective price never above listed price; best deal equals the lowest effective price; currency present; optional expected price range (catches wrong variant or accessory); optional expected stores.

## Add cases
Edit `evals/products.json`. For each case open the store pages yourself on the day, then set `expected_min_price` and `expected_max_price` generously (prices move), pick 1-2 stores that should appear, and set `enabled: true`. Mix categories (phones, appliances, groceries), countries and cities. Aim for 30-50 cases. **Never guess prices.**

## Run
```bash
ANTHROPIC_API_KEY=... python evals/run_evals.py     # costs real searches: cases x MAX_SEARCHES x about $0.01
```
Writes `evals/report.json` (pass rate, seconds, searches, store coverage per country). Exit code 1 if the pass rate is below `MIN_PASS_RATE` (default 0.8). `.github/workflows/evals.yml` runs it weekly when the `ANTHROPIC_API_KEY` repository secret exists.

## Reading results
A drop after a prompt, model or search-tool change means roll back or fix. A single store failing across cases means it started blocking: record it in `STORE_COVERAGE.md`.
