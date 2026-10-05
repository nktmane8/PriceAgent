# Status and TODO

Last reviewed: 2026-10-05. Update this file in the same PR that changes any status.

## 1. What is developed
| Area | Status | Where |
|---|---|---|
| Region-aware price comparison, effective price, best deal | Done | `agent.py`, UI |
| Reviews, pros/cons, similar products (sourced, links required) | Done | `agent.clean_insights`, UI, MCP tool |
| Async jobs, in-flight dedupe and restart recovery | Done locally; distributed runtime pending | `jobs.py`, `worker.py` |
| SQLite backend | Done for local/test | `db_sqlite.py` |\n| PostgreSQL backend | Implemented; not production-proven | `db_postgres.py` |\n| Redis/Valkey + RQ worker | Implemented; not production-proven | `jobs.py`, `worker.py` |
| OAuth 2.1 server (PKCE, DCR, refresh rotation, audience binding) | Done | `oauth.py` |
| Remote MCP server + OpenAPI + partner API keys | Done | `mcp_app.py`, `main.py` |
| Location fallback (locale, GPS, typed) | Done | UI, `/api/locate` |
| **Account deletion** | Done (new) | `POST /api/v1/account/delete` |
| **Price history** (recorded per fresh run, 90-day lowest + sparkline shown) | Done | `price_history`, `/api/history`, UI |
| **Metrics**: latency, cache hit rate, top errors, cost by caller type | Done (new, JSON) | `/api/admin/stats` |
| **Evals harness** (invariant checks, optional price ranges, coverage report) | Done (new); dataset still needed | `evals/` |
| **OpenAI provider** (Responses API + `web_search`; Anthropic removed from code, env, CI, docs) | Done (v2.6.0) | `agent._converse`, `config.py` |
| **Post-deploy smoke test** (health, OAuth discovery, `/mcp` 401 challenge, optional real comparison) | Done (v2.6.0) | `tools/smoke.py` |
| Tests (16, offline) and CI; weekly evals workflow | Done | `tests/`, `.github/workflows/` |
| Environments (`env/`), global constants, start-up config validation | Done (new) | `config.py`, `constants.py` |
| Code guide, generated code reference, configuration doc, study guide | Done (new) | `docs/CODE_GUIDE.md` etc. |
| Docs: DESIGN, ARCHITECTURE, API, SECURITY, PRIVACY (draft), RUNBOOK, PUBLISHING, BUSINESS, EVALS, STORE_COVERAGE (template), CONTRIBUTING, ENGINEERING, ADRs | Done / drafts flagged | `docs/` |

## 2. Partial
| Item | What exists | What is missing |
|---|---|---|
| EVALS dataset | Runner and checks | 30-50 real cases with prices **you** verified (I cannot know today's prices) |
| STORE_COVERAGE | Template + auto report from evals | Real data after the first eval run |
| TERMS.md | Draft template | Lawyer review |
| Metrics | JSON endpoint | Dashboard UI or Prometheus/Grafana |
| Price alerts | Price history exists | Target-price rules, notifications, unsubscribe |
| Account lifecycle | Deletion | Email verification, password reset |
| Login | OAuth browser login + logout + `/api/v1/me` | Standalone account/profile UX, email verification and password reset |

## 3. Release blockers before Java migration
| # | Item | Size | Blocker / dependency | Done when |
|---|---|---|---|---|
| 1 | Fill the eval dataset, run weekly, record results in STORE_COVERAGE | S | Needs your verified prices + OpenAI key | `evals/products.json` has 30+ enabled cases; pass rate tracked in `evals/report.json` |
| 2 | Email verification + password reset | M | Choose an email provider (SMTP/API key) | New accounts must verify; reset link expires in 30 min; tests with a fake mailer |
| 3 | Security review of OAuth | S-M | External reviewer | Findings fixed; SECURITY.md gaps closed |
| 4 | Price alerts | M | Notification channel (email) + #2 | User sets target price; one notification per drop; unsubscribe link |
| 5 | Postgres + Redis/Valkey + worker production validation | L | Render resources | API and worker share durable state; restart/multi-instance tests pass |
| 6 | Metrics dashboard | M | Choose stack | Latency, hit rate, errors, cost per caller type visible without curl |
| 7 | OAuth Client ID Metadata Documents | M | Careful SSRF handling when fetching client URLs | Client IDs that are https URLs accepted; fetch limited and cached |
| 8 | Map picker (Leaflet + OSM) | S | None | User can pick a place on a map; same `country/city` fields filled |
| 9 | Lawyer-reviewed TERMS + final PRIVACY | S | Legal advice | Published URLs linked from the sign-in page |
| 10 | No-AI provider mode (shopping-search API) | M | Free API key | `PROVIDER=serper` passes the offline tests; cost per comparison below one cent |
| 11 | **Verify production end to end**: run `python tools/smoke.py https://priceagent.onrender.com --key <API_KEY>`; if the real comparison returns no records, read the job `error` and the Render logs | S | `OPENAI_API_KEY`, `PUBLIC_URL` and `MODEL` set on Render; model name valid for your account | Smoke test exits 0 with store results; one real Claude/ChatGPT connector sign-in works |
| 12 | Standalone account/profile UX | M | Product decision | Account page, logout and lifecycle UX complete |
| 13 | Retry/backoff and a clearer error for OpenAI failures (invalid model, quota, timeout); surface `AgentError` text in the job | S | None | Offline test with a faked 429/404; user sees an actionable message |
| 14 | Remove dead config `MAX_PAUSE_LOOPS` (left over from the Anthropic loop) and its CONFIGURATION row | S | None | Setting gone from `config.py` and docs; tests pass |
| 15 | Smoke test in CI after deploy (health + `/mcp` challenge only, no key) | S | Render deploy hook or scheduled run | Failing deploy raises an alert |
\n## 4. Java handoff gate\n\n**Do not begin the production Java migration until `docs/RELEASE_READINESS.md` is green.** The Python application is the behavioral reference. Freeze REST/OpenAPI, OAuth, MCP tools, job lifecycle, provider error taxonomy, security invariants and regression fixtures before Java implementation.\n

## Reference implementation hardening — 2026-10-05

The ten hardening tracks have now been applied to the Python reference implementation:

1. REST job ownership is principal-scoped.
2. OAuth resources are explicit and strict.
3. Public HTTP redirect exceptions are limited to loopback.
4. PostgreSQL rate checks use a per-principal transaction advisory lock.
5. Stale running jobs are recovered after worker/process loss.
6. Job failures persist stable machine-readable error codes.
7. Security/OAuth/job boundary tests were expanded and CI was added.
8. A black-box external MCP OAuth smoke test is available at scripts/mcp_external_smoke.py.
9. Thirty source-verified India product evaluation cases are committed.
10. Release-readiness/API/security documentation now records the hardened invariants.

These are code-level completions. Infrastructure-dependent proof remains a release gate: deployed Render web/worker wiring, distributed restart tests, external MCP run, backup/restore, load baseline, security review, and live evaluation execution.
