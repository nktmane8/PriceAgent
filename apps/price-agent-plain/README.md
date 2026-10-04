# Price Agent (plain): React + Node.js + Python + SQL, no AI, no paid services

A conventional price comparison app. No LLM and no API keys: prices come from a Python **collector** (reads the structured product data shops publish), CSV imports, admins and community reports. Ranking is plain arithmetic, so results are deterministic and free to run.

## Languages and why
| Language | Where | Why this one |
|---|---|---|
| JavaScript (React 18 + Vite) | `web/` | Interactive UI, builds to static files |
| JavaScript (Node.js 22, Express) | `api/` | REST API; uses Node's built-in SQLite, so no native modules |
| Python 3 | `collector/` | Parsing and fetching pages; runs on a schedule, talks to the API over HTTP |
| Java 21 (Spring Boot 4.1) | `collector-spring/` | The same collector for JVM teams: typed config, built-in scheduler, 22 unit tests (see its README) |
| SQL (SQLite) | `sql/schema.sql` | Shared schema, constraints enforced by the database |
| YAML / Dockerfile | `.github/`, `Dockerfile` | Free CI, scheduled collection, one-container deploy |

## Architecture
```
Shop pages --(Python collector: robots.txt, JSON-LD parser)--> POST /api/ingest --+
CSV file ----(collector --csv)--------------------------------------------------+--> Node API (Express) --> SQLite
Community reports (web form) --> POST /api/offers (rate limited, sanity checked) --+        ^
React UI <------------ GET /api/compare, /history, /products, /stores --------------------+
```
Layers: React UI -> Express routes (`app.js`) -> repository (`repo.js`, all SQL) -> SQLite. Validation in `validate.js`. The collector is a separate process that only knows the HTTP contract (`/api/ingest`).
Rules in the domain: effective price = price minus the instant discount, and a discount must say where it is shown; offers older than 7 days are flagged stale; community reports are labelled unverified and rejected if far from the median; currencies are never mixed in a ranking.

## Run locally (needs Node 22.13+ and Python 3.10+)
```bash
cd api && npm install && npm start            # API on :3000, loads DEMO data on first run
cd web && npm install && npm run dev          # UI on :5173 (proxies /api), or `npm run build` and open :3000
```
Production-style single process: `cd web && npm run build`, then `cd api && ADMIN_KEY=... INGEST_KEY=... SEED_ON_EMPTY=false npm start`.
Demo data (`api/data/seed.json`) is **invented** and named "Demo ... (sample)". Do not treat it as real.

## Collectors (Python and Java, same HTTP contract)
Use either one: `collector/` (Python, below) or `collector-spring/` (Spring Boot, see its README). Both read the same `sources.json` format and send to `/api/ingest`.
```bash
export API_URL=http://localhost:3000 INGEST_KEY=your-key
python collector/collect.py --csv collector/prices.example.csv        # import a CSV
cp collector/sources.example.json collector/sources.json              # list product pages you are allowed to read
python collector/collect.py collector/sources.json --dry-run          # preview, then run without --dry-run
```
It works only on pages that publish schema.org JSON-LD (or product meta tags). It respects robots.txt, waits 2 s between requests, refuses private addresses and does not follow redirects. Many shops block bots or hide prices behind JavaScript or login: those are skipped and reported. **Check each site's terms before collecting.**

## API
| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/products?q=` · `GET /api/stores?country=` · `GET /api/regions` | none | Browse |
| `GET /api/compare?productId&country&city` | none | Latest offer per store, region-filtered, sorted by effective price |
| `GET /api/history?productId&days` | none | Daily lowest price |
| `POST /api/offers` | none, 10/hour/IP | Community price report |
| `POST /api/stores`, `POST /api/products` | `x-admin-key` | Create |
| `POST /api/ingest` | `x-ingest-key` | Bulk upsert (max 500, all-or-nothing) |

## Tests and CI
`cd api && npm test` (8 tests) · `python -m pytest -q collector/tests` (7 tests) · `cd collector-spring && mvn -B verify` (22 core tests + 1 Spring context test) · `cd web && npm run build`. GitHub Actions run all three and a daily collection (needs `API_URL`, `INGEST_KEY` secrets).

## Cost: Rs 0, with honest caveats
Everything is open source and runs on your own computer for free. For hosting, free tiers exist (a free web service for the Node app, GitHub Actions for scheduling) but I have not verified today's limits: typically free web services **sleep when idle and may lose local files**, so the SQLite file can reset. Keep a `seed`/CSV to rebuild, or run it on your own machine. Docker files are provided but I could not build the image in my sandbox.

## Limits
Data is only as good as what you collect or users report: no data means no comparison. No accounts or sign-in. No AI means no reviews summaries or similar-product suggestions (see the RAG app for those). Prices change quickly.
