# Architecture

```
Browser ──POST /api/jobs, poll──┐
AI app ──OAuth──> /mcp ─────────┤        ┌─ thread pool (WORKERS) ─> agent.py ─> OpenAI Responses API + web_search
Partner ─OAuth/API key─> /api/v1┴─> jobs.py ─┤
                                             └─> SQLite (cache, jobs, rate limits, users, OAuth) <── purger thread
```
One process, one instance: `main.py` (wiring) -> `jobs.py` (threads) -> `agent.py` (OpenAI) -> `db.py` (SQLite). `oauth.py` is the authorization server; `mcp_app.py` is the MCP server; `util.py` has input validation.

## Data model (SQLite, WAL mode)
| Table | Purpose | Key columns |
|---|---|---|
| `users` | OAuth accounts | email (unique), scrypt `pw_hash` |
| `oauth_clients` | Dynamically registered apps | client_id, name, redirect_uris |
| `oauth_requests` | Pending sign-ins (15 min, single use) | id, client_id, PKCE challenge, state |
| `oauth_codes` | Auth codes (10 min, single use, stored hashed) | hash, user_id, challenge |
| `oauth_tokens` | Access (1 h) and refresh (30 d) tokens, stored hashed | hash, kind, family, revoked, used |
| `cache` | Finished comparisons, TTL 30 min | key, value JSON, expires_at |
| `usage` | One row per metered action: sliding-window rate limits | principal, ts |
| `jobs` | Every comparison: status, result, tokens, searches | id, key, status, result, error |

Cache key = product + country + city + preferred sites (lower-cased). Rows are purged by a daemon thread every 10 minutes (jobs kept 7 days, usage 1 day).

## Threading model
- Web/MCP requests never run the agent. `jobs.submit` checks cache, then joins an in-flight job for the same key, then checks the rate limit, then queues work on a `ThreadPoolExecutor`.
- A lock makes "look for running job, else create" atomic, so identical simultaneous queries cost one agent run.
- Sync endpoints (`/api/v1/compare`, MCP `compare_prices`) wait up to `JOB_WAIT_SECONDS`, then return a `job_id` to poll. This avoids client timeouts.
- Each SQLite call uses its own short-lived connection; writes use `BEGIN IMMEDIATE`.
- On startup, jobs left `queued/running` by a previous process are marked `error`.

## OAuth 2.1 flow
1. Client discovers metadata (`/.well-known/oauth-protected-resource[/mcp]`, `/.well-known/oauth-authorization-server`).
2. Client registers (`POST /oauth/register`, public client, https or loopback redirect URIs only).
3. Browser opens `/oauth/authorize` (PKCE S256 required). User signs in or creates an account on a server-rendered page, with brute-force limits, then the app gets a one-time code.
4. `POST /oauth/token` exchanges code + verifier for tokens; refresh tokens rotate, and replaying an old one revokes the whole family.
5. Tokens may be bound to a `resource` (`/mcp` or the API root); each endpoint rejects tokens meant for the other.

## Decisions
- **SQLite over Postgres/Redis:** zero setup, enough for one instance. Move to Postgres + Redis to scale out.
- **Own authorization server:** self-contained and testable. Alternative: delegate to an identity provider and only validate tokens.
- **Polling jobs over websockets:** simplest thing that survives proxies and mobile networks.
