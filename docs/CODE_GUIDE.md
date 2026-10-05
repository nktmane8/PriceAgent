# Code guide: what each part does and how the flow works
Read this first, then `CODE_REFERENCE.md` (auto-generated list of every function with its docstring and line number), then the code. For design rationale see `DESIGN.md`; for learning exercises see `STUDY_GUIDE.md`.

## 1. What the program does
A shopper enters a product and a region. The app finds stores that serve that region, compares prices, and (on request) shows sourced reviews and similar products. The slow work (30-60 s of web search by the OpenAI model) runs in background threads; the page starts a job and polls it. AI apps use the same engine through REST and an OAuth-protected MCP server.

## 2. Architecture we follow
**A layered modular monolith**: one deployable, one process, clear layers, dependencies pointing downward.

| Layer | Files | Responsibility |
|---|---|---|
| Presentation | `static/index.html` | UI, polling, safe rendering (`textContent`) |
| Interface | `main.py` (REST), `mcp_app.py` (MCP), `oauth.py` (OAuth routes) | HTTP/MCP contracts, auth, validation, status codes |
| Application | `jobs.py` | Orchestration: cache, dedupe, rate limit, queue, worker, wait |
| Domain + anti-corruption | `agent.py`, `util.py`, `constants.py` | Prompts, calling OpenAI, `clean()` / `clean_insights()` turn untrusted output into trusted data |
| Infrastructure | `db.py`, `config.py`, OpenAI API, OpenStreetMap | Storage, settings, external services |

Patterns used (named so you can discuss them): **asynchronous request-reply (job pattern with polling)**, **producer-consumer** (thread pool), **cache-aside with in-flight de-duplication**, **anti-corruption layer** (DDD), **repository-style data access** (`db.py`), **authorization server + resource servers** (OAuth 2.1 code + PKCE), **gateway/adapter** to external services, **12-factor configuration** with per-environment files, **fail-fast start-up validation**.
Not used: microservices, event sourcing, CQRS, message broker, ORM. Not strictly hexagonal either: there are no formal ports/interfaces; add one if you introduce a second AI provider (ROADMAP #10 or #11).
Dependency rule: `db.py` and `config.py` import nothing from upper layers; `main.py` imports everything.

## 3. Folder map
```
main.py        app wiring + REST endpoints          oauth.py     OAuth 2.1 server
mcp_app.py     MCP tools + token verifier           jobs.py      thread pool, job service, purge thread
agent.py       prompts, OpenAI calls, cleaning      db.py        SQLite schema + helpers
config.py      env-driven settings + validation     constants.py fixed global values
util.py        validation, client IP                mcp_server.py optional local stdio wrapper
static/        web page                             env/         per-environment defaults (no secrets)
tests/         16 offline tests                     evals/       real-world accuracy checks (paid)
tools/         gen_code_map.py                      docs/        all documentation
```

## 4. Settings and global values (where does a value live?)
| Kind | Lives in | Example |
|---|---|---|
| Fixed for all environments | `constants.py` | job statuses, OAuth TTLs, validation limits, output caps |
| Changes per environment | `config.py`, defaults in `env/.env.<APP_ENV>` | `PUBLIC_URL`, `WORKERS`, `MAX_SEARCHES`, rate limits |
| Secret | Real environment variable only | `OPENAI_API_KEY`, `API_KEYS`, `ADMIN_KEY` |

Precedence: real environment variable > `.env` (git-ignored) > `env/.env.<APP_ENV>`. `APP_ENV` is `development` (default), `test`, `staging` or `production`. In staging/production, `config.assert_ready()` stops the app at start-up if `PUBLIC_URL` is not https, the database path is not absolute, the contact is unset, or keys are weak. Full table: `CONFIGURATION.md`.
Add a setting: (1) add it to `config.py` with a default, (2) add to each `env/` file where it differs, (3) document it in `CONFIGURATION.md` and `.env.example`, (4) use `config.X` (never `os.environ` elsewhere).

## 4b. Start-up sequence
`uvicorn main:app` -> `config` loads env files -> `main` calls `config.assert_ready()` -> logs `config.summary()` -> `db.init()` (create tables, fail stranded jobs) -> `jobs.start_purger()` (daemon thread) -> `mcp.streamable_http_app()` becomes the outer ASGI app and `Mount("/", api)` serves everything else.

## 5. Flows (function call chains)
**A. Price comparison from the web page**
`index.html submit` -> `POST /api/jobs` -> `main.create_job` -> `params_of` -> `util.validate` -> `main.start` -> `jobs.submit`:
1. `db.cache_get(key)`: hit -> `db.job_create(status=done)` + `db.job_update(source=cache)` -> returns at once.
2. `db.job_active(key)`: same query already running -> return that job id.
3. `db.rate_check(principal, limit)`: over limit -> `RateLimited` -> HTTP 429.
4. `db.job_create(queued)` -> `_pool.submit(_work)` -> returns 202 + job id.
Worker thread: `_work` -> `agent.run_agent` -> `_converse` (OpenAI Responses + web search, sums usage) -> `_parse` -> `extract_json` -> `clean` -> `db.cache_set` -> `db.record_history` -> `db.job_update(done)`.
Page: `GET /api/jobs/{id}` every 3 s -> `main.read_job` -> `db.job_get` -> `respond`. When done it renders the best deal and store cards, then calls `GET /api/history` for the "lowest in 90 days" line.

**B. Reviews and similar products**: same as A with `kind=insights` (`agent.run_insights` -> `clean_insights`, reviews without links dropped). Own cache key and hourly allowance (`principal + ":insights"`). No history is recorded.

**C. AI app or partner**: `POST /api/v1/compare` -> `main.partner` (OAuth bearer or `X-API-Key`) -> `start` -> `jobs.submit` -> `jobs.wait(JOB_WAIT)` -> 200 with result, or 202 + job id to poll at `/api/v1/jobs/{id}`.

**D. OAuth sign-in**: client discovers `/.well-known/*` -> `oauth.register` -> browser `GET /oauth/authorize` (`oauth.authorize` validates client, redirect URI, PKCE; stores a pending request) -> user submits the form -> `oauth.authorize_post` (rate limits, sign-up or sign-in, one-time code stored hashed) -> redirect back -> client `POST /oauth/token` -> `oauth.token` (single-use code, PKCE check) -> `oauth.issue` (access + refresh tokens, same family). Refresh: old refresh token marked used; replay revokes the family.

**E. MCP tool call**: client `POST /mcp` -> SDK auth middleware -> `DbTokenVerifier.verify_token` -> tool `compare_prices` or `get_reviews_and_alternatives` -> `jobs.submit` + `jobs.wait` in a thread (`anyio.to_thread`) -> JSON text with result or job id; `get_comparison_result` fetches later.

**F. Others**: `GET /api/locate` (rate limit -> OpenStreetMap -> country, city); `POST /api/v1/account/delete` (`oauth.delete_user`, one transaction); `GET /api/admin/stats` (`db.stats`); background `jobs.start_purger` -> `db.purge` every 10 minutes.

## 6. Modules in brief
- **main.py**: defines request models, the `partner` auth dependency, endpoints, security-headers middleware; builds the final app (`mcp` app + mounted FastAPI app).
- **jobs.py**: the only place that decides *whether to run the agent*. `_submit_lock` makes check-then-create atomic. `wait` polls the DB every 0.5 s. `view` is the whitelist of fields clients may see.
- **agent.py**: `SYSTEM_PROMPT` and `INSIGHTS_PROMPT` are the product's behaviour. `_converse` is the shared OpenAI call. `clean*` enforce types, sizes, http(s) links, enums.
- **db.py**: tables, `tx()` write transactions (`BEGIN IMMEDIATE`), sliding-window `rate_check`, job/cache/history helpers, `stats`, `purge`.
- **oauth.py**: all OAuth routes and helpers; secrets hashed; exact redirect matching; brute-force limits; audience-bound tokens.
- **mcp_app.py**: MCP server with Host/Origin validation and three tools.
- **config.py / constants.py**: see section 4.
- **evals/**: `checks.py` (pure checks, unit-tested) and `run_evals.py` (paid, real searches).

## 7. State
| Table | Written by | Read by |
|---|---|---|
| `jobs`, `cache`, `usage` | `jobs`, `db` | `main`, `jobs`, `db.stats` |
| `price_history` | `jobs._work` | `main.history` |
| `users`, `oauth_*` | `oauth` | `oauth`, `main.partner`, `mcp_app` |

## 8. Errors and safety touchpoints
Bad input -> 422 (`util.validate`). Over limit -> 429. Bad auth -> 401 with `WWW-Authenticate`. Agent failure -> job `error` with a safe message, nothing cached. Restart -> stranded jobs marked error. Untrusted model output -> `clean*`. Untrusted HTML -> `textContent` and `html.escape`. Secrets -> hashed or from env.

## 9. How to extend
- **New endpoint**: add a function in `main.py` (validate with `util.validate`, rate-limit via `db.rate_check`), add a test, run `python tools/gen_code_map.py`.
- **New field in results**: add to the prompt, to `clean()`, to the UI render, to a test.
- **New job kind**: add a constant, a prompt + `run_*` + cleaner in `agent.py`, route it in `jobs._work`, include it in `make_key`.
- **New AI/search provider**: introduce a small interface (`run_prices`, `run_insights`) used by `jobs._work`; keep `clean*` in front of every provider.

## 10. Run, test, debug
`pytest -q tests` (offline). `curl localhost:8000/healthz`. Admin metrics: `curl -H "X-Admin-Key: $KEY" localhost:8000/api/admin/stats`. Inspect data: `sqlite3 data/dev.db "select status,count(*) from jobs group by 1"`. Logs: set `LOG_LEVEL=DEBUG`.
