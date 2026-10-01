# Status and TODO

Last reviewed: 2026-10-01. Update this file in the same PR that changes any status.

## 1. What is developed
| Area | Status | Where |
|---|---|---|
| Region-aware price comparison, effective price, best deal | Done | `agent.py`, UI |
| Reviews, pros/cons, similar products (sourced, links required) | Done | `agent.clean_insights`, UI, MCP tool |
| Async jobs on threads, in-flight dedupe, restart recovery | Done | `jobs.py` |
| SQLite tables, persistent cache, persisted rate limits, purge thread | Done | `db.py` |
| OAuth 2.1 server (PKCE, DCR, refresh rotation, audience binding) | Done | `oauth.py` |
| Remote MCP server + OpenAPI + partner API keys | Done | `mcp_app.py`, `main.py` |
| Location fallback (locale, GPS, typed) | Done | UI, `/api/locate` |
| **Account deletion** | Done (new) | `POST /api/v1/account/delete` |
| **Price history** (recorded per fresh run, 90-day lowest shown) | Done (new) | `price_history`, `/api/history` |
| **Metrics**: latency, cache hit rate, top errors, cost by caller type | Done (new, JSON) | `/api/admin/stats` |
| **Evals harness** (invariant checks, optional price ranges, coverage report) | Done (new); dataset still needed | `evals/` |
| Tests (15, offline) and CI; weekly evals workflow | Done | `tests/`, `.github/workflows/` |
| Docs: DESIGN, ARCHITECTURE, API, SECURITY, PRIVACY (draft), RUNBOOK, PUBLISHING, BUSINESS, EVALS, STORE_COVERAGE (template), CONTRIBUTING, ENGINEERING, ADRs | Done / drafts flagged | `docs/` |

## 2. Partial
| Item | What exists | What is missing |
|---|---|---|
| EVALS dataset | Runner and checks | 30-50 real cases with prices **you** verified (I cannot know today's prices) |
| STORE_COVERAGE | Template + auto report from evals | Real data after the first eval run |
| TERMS.md | Draft template | Lawyer review |
| Metrics | JSON endpoint | Dashboard UI or Prometheus/Grafana |
| Price history | Recording, API, one line in UI | Chart; alerts |
| Account lifecycle | Deletion | Email verification, password reset |

## 3. Missing (prioritised TODO)
| # | Item | Size | Blocker / dependency | Done when |
|---|---|---|---|---|
| 1 | Fill the eval dataset, run weekly, record results in STORE_COVERAGE | S | Needs your verified prices + Anthropic key | `evals/products.json` has 30+ enabled cases; pass rate tracked in `evals/report.json` |
| 2 | Email verification + password reset | M | Choose an email provider (SMTP/API key) | New accounts must verify; reset link expires in 30 min; tests with a fake mailer |
| 3 | Security review of OAuth | S-M | External reviewer | Findings fixed; SECURITY.md gaps closed |
| 4 | Price alerts | M | Notification channel (email) + #2 | User sets target price; one notification per drop; unsubscribe link |
| 5 | Postgres + Redis (multi-instance) | L | Hosting budget | Two instances pass the test-suite; jobs queue and rate limits shared |
| 6 | Metrics dashboard | M | Choose stack | Latency, hit rate, errors, cost per caller type visible without curl |
| 7 | OAuth Client ID Metadata Documents | M | Careful SSRF handling when fetching client URLs | Client IDs that are https URLs accepted; fetch limited and cached |
| 8 | Map picker (Leaflet + OSM) | S | None | User can pick a place on a map; same `country/city` fields filled |
| 9 | Price-history chart | S | More data first | Sparkline per product |
| 10 | Lawyer-reviewed TERMS + final PRIVACY | S | Legal advice | Published URLs linked from the sign-in page |
| 11 | No-AI provider mode (shopping-search API) | M | Free API key | `PROVIDER=serper` passes the offline tests; cost per comparison below one cent |
