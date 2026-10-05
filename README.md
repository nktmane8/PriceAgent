# Price Comparison Agent (region-aware, OAuth, async)

![CI](https://github.com/nktmane8/PriceAgent/actions/workflows/ci.yml/badge.svg)

Type a product and your region. The agent supports both OpenAI web search and Gemini Google Search grounding, with configurable provider routing to find the stores that serve you (online marketplaces, brand stores, chains, local shops) and ranks them by effective price. Works as a web page, a REST API and an OAuth-protected MCP server for other AI apps.

## Features
- **Region-aware discovery**, not a fixed store list; country auto-filled from browser locale, **Use my location** (GPS, rounded to ~1 km) or typed manually; local currency.
- **Why buy this?** On request: sourced reviews from publications, video reviewers and users, pros/cons, rating summary, and similar products reviewers rate better (links required; unsourced reviews are dropped).
- **Effective price** = listed price minus verified instant discounts only; offers listed per store; best-deal card.
- **Background threads:** slow searches run in a thread pool; the page polls a job; identical queries share one run.
- **SQLite tables:** persistent cache (30 min), jobs with token/search cost, rate limits, users, OAuth data. Purge thread cleans up.
- **OAuth 2.1** (PKCE, dynamic client registration, refresh rotation) + **remote MCP server** at `/mcp`; partner API keys also supported.
- **Safety:** model output validated, `textContent` rendering, input validation, per-IP/user/key limits, Origin/Host checks, secrets from env only.
- **Price history:** every fresh run is recorded; the page shows a 90-day sparkline and the lowest price seen.
- **Account deletion** (`POST /api/v1/account/delete`), richer admin metrics, offline tests (16), CI, weekly evals harness.
- **Ops:** `/healthz`, admin stats, Render blueprint.

## Run locally
Settings come from `env/.env.<APP_ENV>` (default `development`); secrets go in a git-ignored `.env` or your shell. See `docs/CONFIGURATION.md`.
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export GEMINI_API_KEY="..."                         # PowerShell: $env:GEMINI_API_KEY="..."
# Development defaults to Gemini. To use both with fallback:
# export AI_PROVIDER="auto"
# export OPENAI_API_KEY="sk-..."
uvicorn main:app --reload
```
Open http://127.0.0.1:8000, enter a product, confirm the country, click **Compare** (30-60 s). The database is created at `data/price-agent.db`.
Tests (no API key needed): `pip install -r requirements-dev.txt && python -m pytest -q tests`.
After deploying, check the live app and the MCP endpoint: `python tools/smoke.py https://your-app.onrender.com [--key API_KEY]`.

## Deploy on Render
1. Push to GitHub. In Render: **New > Blueprint**, choose the repo (`render.yaml`).
2. Enter secrets: `OPENAI_API_KEY`, `PUBLIC_URL` (your exact https URL), `NOMINATIM_CONTACT` (your email); optional `API_KEYS`, `ADMIN_KEY`.
3. The blueprint uses a paid plan with a 1 GB disk so users, tokens and cache survive restarts (verify current pricing). Run exactly one instance.
4. Set a monthly spend limit in the OpenAI API platform.

## Use from AI apps
- **Claude:** Settings > Connectors > add custom connector `https://your-app/mcp`, then sign in.
- **REST:** `POST /api/v1/compare` with `Authorization: Bearer <oauth token>` or `X-API-Key`.
- **Custom GPT:** import `https://your-app/openapi.json`, use OAuth or API key auth.
- Directory submissions: `docs/PUBLISHING.md`.

## Configuration (summary; full table in `docs/CONFIGURATION.md`)
| Variable | Default | Meaning |
|---|---|---|
| `APP_ENV` | development | development, test, staging or production; loads `env/.env.<APP_ENV>` |
| `LOG_LEVEL` | INFO | DEBUG, INFO, WARNING |
| `AI_PROVIDER` | openai | `gemini`, `openai`, `auto`, or comma-separated priority such as `gemini,openai` |
| `GEMINI_API_KEY` | optional | Gemini secret; required when Gemini is selected |
| `GEMINI_MODEL` | gemini-3.8-flash | Gemini model |
| `OPENAI_API_KEY` | optional | OpenAI secret; required when OpenAI is selected |
| `OPENAI_MODEL` | gpt-6-luna | OpenAI model |
| `PUBLIC_URL` | `http://127.0.0.1:8000` | Public https URL; OAuth issuer; must be exact |
| `DATABASE_PATH` | `data/price-agent.db` | SQLite file (put on the persistent disk) |
| `MODEL` | `gemini-3.8-flash` | Legacy/common model setting; provider-specific model variables take precedence |
| `MAX_SEARCHES` | 15 | Searches per price comparison |
| `MAX_INSIGHT_SEARCHES` | 10 | Searches for reviews and alternatives |
| `WORKERS` | 4 | Background threads |
| `JOB_WAIT_SECONDS` | 50 | Sync/MCP wait before returning a job id |
| `CACHE_TTL_SECONDS` | 1800 | Cache lifetime |
| `RATE_LIMIT` / `USER_RATE_LIMIT` / `KEY_RATE_LIMIT` / `LOCATE_LIMIT` | 5 / 30 / 60 / 20 | Per hour: web IP / OAuth user / API key / location lookups |
| `API_KEYS` | empty | Comma-separated partner keys |
| `ADMIN_KEY` | empty | Enables `/api/admin/stats` |
| `NOMINATIM_CONTACT` | - | Your email/site for OpenStreetMap |
| `EXTRA_ORIGINS` | empty | Extra allowed browser origins for `/mcp` |

## Docs
`docs/CODE_GUIDE.md` (**read first: architecture and flows**) · `docs/STUDY_GUIDE.md` · `docs/CONFIGURATION.md` · `docs/CODE_REFERENCE.md` · `docs/ROADMAP.md` (status and TODO) · `docs/ENGINEERING.md` (**process**) · `docs/DESIGN.md` (DDD, HLD, LLD, flows) · `docs/ARCHITECTURE.md` (tables, threads, OAuth) · `API.md` · `SECURITY.md` · `PRIVACY.md` (draft) · `RUNBOOK.md` (backups, cost, troubleshooting) · `PUBLISHING.md` · `BUSINESS.md` · `EVALS.md` · `STORE_COVERAGE.md` · `TERMS.md` (draft) · `adr/` · `CONTRIBUTING.md` · `CHANGELOG.md`

## What cannot be guaranteed
- Store discovery depends on web search; small local shops can be missed; coverage varies by country.
- Some stores block bots or hide prices; they are skipped and listed in `notes`.
- Prices, stock and offers change within minutes. The model can misread a page or match the wrong variant. Verify before paying.
- Review summaries come from pages the agent could read; it cannot prove a review is genuine, may only see a title for videos, and "better quality" is partly subjective. Every item links to its source.
- Effective price counts only verified instant discounts, so real offers may be missed.
- Country is what the user enters or allows; it is not exact location.
- Price history only has data for products people searched on this deployment.
- The OAuth server is hand-written and has no email verification or password reset yet. Get it reviewed before a public launch (`docs/SECURITY.md`).
- One instance only; SQLite and in-process threads do not scale out.

## Apps in this repository
`apps/price-agent-rag` (AI + RAG, no paid key), `apps/price-agent-plain` (React, Node.js, Python and Spring Boot collectors, no AI). See `docs/VARIANTS.md` for how they differ from the app at the repository root. CI for them is in `.github/workflows/apps-ci.yml`.
