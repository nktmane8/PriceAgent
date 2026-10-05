# Price Comparison Agent (region-aware, OAuth, async)

![CI](https://github.com/nktmane8/PriceAgent/actions/workflows/ci.yml/badge.svg)

Type a product and your region. The agent supports Gemini Google Search, Groq browser search, OpenAI web search, and automatic fallback through Hugging Face and Ollama, with configurable provider routing to find the stores that serve you (online marketplaces, brand stores, chains, local shops) and ranks them by effective price. Works as a web page, a REST API and an OAuth-protected MCP server for other AI apps.

## Features
- **Region-aware discovery**, not a fixed store list; country auto-filled from browser locale, **Use my location** (GPS, rounded to ~1 km) or typed manually; local currency.
- **Why buy this?** On request: sourced reviews from publications, video reviewers and users, pros/cons, rating summary, and similar products reviewers rate better (links required; unsourced reviews are dropped).
- **Effective price** = listed price minus verified instant discounts only; offers listed per store; best-deal card.
- **Durable async jobs:** production target uses PostgreSQL for job state and Redis/Valkey + a dedicated RQ worker; SQLite/in-process threads remain the local/test fallback.
- **Durable storage:** PostgreSQL is the production target; SQLite remains the local/test backend. Cache, locks, rate limits and queue state use Redis/Valkey in the distributed target.
- **Google-only OAuth 2.1** (Authorization Code + PKCE, Google identity verification, refresh rotation and resource binding) protects browser comparisons and the **remote MCP server** at `/mcp`. PriceAgent issues its own signed JWT access token; protected REST APIs require that bearer token.
- **Security:** model output validated, `textContent` rendering, input validation, per-IP/user limits, Origin/Host checks, Google-only identity, signed JWT validation and secrets from env only.
- **Price history:** every fresh run is recorded; the page shows a 90-day sparkline and the lowest price seen.
- **Account deletion** (`POST /api/v1/account/delete`), richer admin metrics, offline tests (16), CI, weekly evals harness.
- **Ops:** `/healthz`, admin stats, Render Blueprint, dedicated worker and release-readiness gate.

## Run locally
Settings come from `env/.env.<APP_ENV>` (default `development`); secrets go in a git-ignored `.env` or your shell. See `docs/CONFIGURATION.md`.
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export GROQ_API_KEY="..."                            # PowerShell: $env:GROQ_API_KEY="..."
# Optional fallbacks:
# export GEMINI_API_KEY="..."
# export HF_TOKEN="..."
# export OPENAI_API_KEY="sk-..."
# Install Ollama locally and run: ollama pull gpt-oss:20b
# Development defaults to automatic fallback: Groq -> Gemini -> Hugging Face -> Ollama -> OpenAI
uvicorn main:app --reload
```
Open http://127.0.0.1:8000, click **Sign in**, continue with Google, then enter a product and click **Compare**. Local/test mode uses SQLite; production-like mode uses PostgreSQL + Redis/Valkey.
Tests (no API key needed): `pip install -r requirements-dev.txt && python -m pytest -q tests`.
After deploying, check the live app and the MCP endpoint with the OAuth smoke tests documented in `docs/RELEASE_READINESS.md`.

## Deploy on Render
1. Push to GitHub. In Render: **New > Blueprint**, choose the repo (`render.yaml`).
2. Configure `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `JWT_SECRET`, `PUBLIC_URL` (exact https URL), `NOMINATIM_CONTACT`, and the selected AI/provider secrets. `JWT_SECRET` must be a strong random secret and must never be committed.
3. Provision the PostgreSQL, Valkey/Key Value and dedicated worker defined by the production Blueprint. Keep `FREE_RENDER=false` for the distributed runtime.
4. Set a monthly spend limit in the OpenAI API platform.

## Use from AI apps
- **Claude:** Settings > Connectors > add custom connector `https://your-app/mcp`, then sign in.
- **REST:** `POST /api/v1/compare` with `Authorization: Bearer <PriceAgent JWT access token>`.
- **Custom GPT:** import `https://your-app/openapi.json` and use OAuth bearer authentication.
- Directory submissions: `docs/PUBLISHING.md`.

## Configuration (summary; full table in `docs/CONFIGURATION.md`)
| Variable | Default | Meaning |
|---|---|---|
| `APP_ENV` | development | development, test, staging or production; loads `env/.env.<APP_ENV>` |
| `LOG_LEVEL` | INFO | DEBUG, INFO, WARNING |
| `AI_PROVIDER` | auto | `auto` or comma-separated priority such as `groq,gemini,huggingface,ollama,openai` |
| `GEMINI_API_KEY` | optional | Gemini secret; required when Gemini is selected |
| `GEMINI_MODEL` | gemini-flash-latest | Gemini model |
| `GROQ_API_KEY` | optional | Groq secret; required when Groq is selected |
| `GROQ_MODEL` | openai/gpt-oss-120b | Groq model with browser search |
| `HF_TOKEN` | optional | Hugging Face token; required when HF is selected |
| `HF_MODEL` | openai/gpt-oss-120b:fastest | HF Inference Providers model |
| `HF_BASE_URL` | https://router.huggingface.co/v1 | HF OpenAI-compatible endpoint |
| `OLLAMA_API_KEY` | optional | Required only for remote Ollama; local Ollama ignores it |
| `OLLAMA_BASE_URL` | http://localhost:11434/v1 | Local or remote Ollama OpenAI-compatible endpoint |
| `OLLAMA_MODEL` | gpt-oss:20b | Ollama model |
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
| `RATE_LIMIT` / `USER_RATE_LIMIT` / `LOCATE_LIMIT` | 5 / 30 / 20 | Per hour: web IP / OAuth user / location lookups |
| `API_KEYS` | empty | Comma-separated partner keys |
| `ADMIN_KEY` | empty | Enables `/api/admin/stats` |
| `NOMINATIM_CONTACT` | - | Your email/site for OpenStreetMap |
| `EXTRA_ORIGINS` | empty | Extra allowed browser origins for `/mcp` |

## Stability before Java\n\nThe Python application is deliberately being stabilized before the Java 21 migration. See `docs/RELEASE_READINESS.md` for the release gate. The Java version should reproduce the frozen Python REST, OAuth, MCP, job and provider behavior before introducing new architecture.\n\n## Docs
`docs/CODE_GUIDE.md` (**read first: architecture and flows**) · `docs/STUDY_GUIDE.md` · `docs/CONFIGURATION.md` · `docs/CODE_REFERENCE.md` · `docs/ROADMAP.md` (status and Java handoff gate) · `docs/RELEASE_READINESS.md` (release checklist) · `docs/ENGINEERING.md` (**process**) · `docs/DESIGN.md` (DDD, HLD, LLD, flows) · `docs/ARCHITECTURE.md` (tables, threads, OAuth) · `API.md` · `SECURITY.md` · `PRIVACY.md` (draft) · `RUNBOOK.md` (backups, cost, troubleshooting) · `PUBLISHING.md` · `BUSINESS.md` · `EVALS.md` · `STORE_COVERAGE.md` · `TERMS.md` (draft) · `adr/` · `CONTRIBUTING.md` · `CHANGELOG.md`

## What cannot be guaranteed
- Store discovery depends on web search; small local shops can be missed; coverage varies by country.
- Some stores block bots or hide prices; they are skipped and listed in `notes`.
- Prices, stock and offers change within minutes. The model can misread a page or match the wrong variant. Verify before paying.
- Review summaries come from pages the agent could read; it cannot prove a review is genuine, may only see a title for videos, and "better quality" is partly subjective. Every item links to its source.
- Effective price counts only verified instant discounts, so real offers may be missed.
- Country is what the user enters or allows; it is not exact location.
- Price history only has data for products people searched on this deployment.
- Authentication is Google-only. Google verifies the user's identity; PriceAgent then issues its own signed JWT access token for API authorization. The hand-written OAuth server still requires external security review before public launch (`docs/SECURITY.md`).
- The distributed Postgres/Valkey/worker runtime is implemented but must be provisioned and validated before it is considered production-stable.

## Apps in this repository
`apps/price-agent-rag` (AI + RAG, no paid key), `apps/price-agent-plain` (React, Node.js, Python and Spring Boot collectors, no AI). See `docs/VARIANTS.md` for how they differ from the app at the repository root. CI for them is in `.github/workflows/apps-ci.yml`.
