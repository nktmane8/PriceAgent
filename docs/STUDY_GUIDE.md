# Study guide: learn this project end to end
Goal: explain every part, change it safely, and defend its design in a review or interview. Plan: 12 sessions of about an hour. Each has **Read / Do / Check**.

## Python for Java developers (cheat sheet)
| Here | Java / Spring analogue |
|---|---|
| FastAPI route functions | `@RestController` + `@GetMapping` / `@PostMapping` |
| Pydantic `BaseModel`, `Field` | DTO + Bean Validation (`@NotNull`, `@Size`) |
| `Depends(...)` | Dependency injection / argument resolvers |
| `@api.middleware` | Servlet `Filter` / `HandlerInterceptor` |
| `ThreadPoolExecutor` | `ExecutorService` (`newFixedThreadPool`) |
| `threading.Lock` | `ReentrantLock` / `synchronized` |
| `with db.tx() as c:` | try-with-resources + `@Transactional` |
| `sqlite3` + `db.py` | JDBC + a Repository/DAO (no ORM) |
| `config.py`, `env/.env.<APP_ENV>`, `APP_ENV` | `@ConfigurationProperties`, `application-{profile}.yml`, `spring.profiles.active` |
| `constants.py` | `public static final` / enums |
| `pytest` fixtures + `monkeypatch` | JUnit + Mockito / `@MockBean` |
| `async def` + `anyio.to_thread` | Reactive code + `boundedElastic` for blocking calls |
| `Mount("/", api)` | Servlet context path mapping |
Python threads share a GIL, which is fine here: the work is waiting on network I/O.

## Sessions
1. **Run it.** Read: README. Do: run locally, search a product, open `/openapi.json`, `/healthz`. Check: what happens on a repeated search (cache)?
2. **Config and environments.** Read: `config.py`, `constants.py`, `env/`, `CONFIGURATION.md`. Do: run with `APP_ENV=staging` and read the failure. Check: where does a secret live? What wins, `.env` or the shell?
3. **Request flow.** Read: `main.py`, `jobs.submit`. Do: add a log line, follow a request. Check: why 202 + polling?
4. **The agent.** Read: `agent.py` prompts and `clean`. Do: feed `clean` a bad payload in a Python shell. Check: why never render raw model output?
5. **Database.** Read: `db.py`. Do: open the DB with `sqlite3`, list tables, run `select status,count(*) from jobs group by 1`. Check: why `BEGIN IMMEDIATE`?
6. **Concurrency.** Read: `jobs.py`. Do: start two identical searches at once; count agent calls in the logs. Check: what does `_submit_lock` protect? What if the server restarts mid-job?
7. **OAuth concepts.** Read: PKCE and authorization-code flow (RFC 7636, OAuth 2.1 draft). Do: draw the sequence on paper. Check: what does PKCE stop?
8. **OAuth code.** Read: `oauth.py`, `tests/test_app.py` OAuth tests. Do: break PKCE verification and watch the test fail. Check: how is refresh-token theft detected?
9. **MCP.** Read: `mcp_app.py`, the MCP spec overview. Do: add the server as a custom connector (README). Check: why `Mount("/", api)` under the MCP app?
10. **Testing.** Read: `tests/conftest.py`. Do: write a test for a new rule. Check: why is the test client session-scoped?
11. **Security and privacy.** Read: `SECURITY.md`, `PRIVACY.md`. Do: list every place user data is stored. Check: which gaps would you close first?
12. **Scale and interview.** Read: `DESIGN.md` sections 3-4. Do: rehearse the pitch below. Check: answer the scaling question without notes.

## Hands-on exercises
1. Add a setting `MAX_RESULTS_SHOWN` through all four steps in CODE_GUIDE 4.
2. Lower `CACHE_TTL_SECONDS` to 5 and watch cache hits disappear in `/api/admin/stats`.
3. Add a store-type value `"outlet"` end to end (constants, prompt, UI tag, test).
4. Make `clean()` reject prices above a configurable ceiling; add a test.
5. Add a `GET /api/v1/history` endpoint behind OAuth.
6. Change the job poll interval and measure UI latency.
7. Add a second kind of limit: per-day cap per IP.
8. Write an eval case from a real product and run `evals/run_evals.py`.
9. Simulate a crash: kill the server mid-job, restart, confirm the job is `error`.
10. Replace the Anthropic call with a fake that returns instantly; run the whole UI offline.

## Self-check questions (answers)
1. **Why 202 + polling?** The agent takes 30-60 s; proxies and clients time out. Work runs in threads; the page polls.
2. **How do identical simultaneous searches cost one run?** `_submit_lock` makes check-then-create atomic and `db.job_active` returns the running job.
3. **Why `BEGIN IMMEDIATE` in `rate_check`?** It takes the write lock before counting, so two requests cannot both see "under the limit".
4. **Why store tokens hashed?** A database leak then does not hand out usable tokens.
5. **What does PKCE prevent?** Using a stolen authorization code: the thief lacks the verifier.
6. **How is refresh reuse detected?** Each refresh token is single use (`used` flag). A replay revokes the whole token family.
7. **Why `clean()`?** Model output is untrusted (types, size, `javascript:` links, prompt injection). It is the anti-corruption layer.
8. **Why drop reviews without a URL?** No verifiable source means it could be invented.
9. **Why is `kind` in the cache key?** Prices and insights are different results for the same product.
10. **Server restarts mid-job?** `db.init()` marks queued/running jobs as `error`; the user retries.
11. **Why one process only?** In-process lock and threads plus a SQLite file: a second process would break dedupe and mark the first one's jobs as failed at start-up.
12. **Why `Mount("/", api)` inside the MCP app?** The MCP app owns `/mcp` and its auth middleware; mounting avoids the trailing-slash redirect a sub-mount would cause.
13. **Env precedence?** Real environment > `.env` > `env/.env.<APP_ENV>`.
14. **Why do production and staging refuse to start on bad config?** A wrong `PUBLIC_URL` breaks OAuth silently; failing fast is cheaper than debugging users.
15. **What breaks first at 10k requests per second?** Not CPU: spend and latency of the LLM, then SQLite writes and the single process. See the next section.

## Interview material
**60-second pitch.** "I built a region-aware price comparison agent. A request becomes a background job: cache, then in-flight de-duplication, then rate limit, then a worker thread calls Claude with web search. Model output is untrusted, so an anti-corruption layer validates it before the UI or MCP clients see it. It exposes a web page, REST and an OAuth 2.1 protected MCP server, persists state in SQLite, and tracks cost per job. Known limit: single instance; next step is Postgres and Redis."

**Scaling to 10k+ requests per second (talking points).** Separate reads from work: serve cache hits and polls from Redis/CDN; make API pods stateless; move the queue to a broker (Redis streams, SQS or Kafka) with autoscaling workers and bounded queues (backpressure); Postgres for jobs/users, Redis for rate limits and cache; idempotency keys and circuit breaker around the LLM; pre-compute popular products; per-tenant budgets; observability on queue depth and cost per request. The LLM bill, not the web tier, is the real constraint.

**Trade-offs to defend.** LLM + search vs scrapers (coverage vs cost and determinism); SQLite vs Postgres (simplicity vs scale-out); own OAuth vs identity provider (control vs security burden); polling vs push (simplicity vs latency).

**STAR template (fill in your real numbers; do not invent results).**
- Situation: shoppers waste time checking many stores; prices differ by region.
- Task: build a region-aware comparison that AI apps can also call, within a small budget.
- Action: async job pipeline, cache and dedupe, anti-corruption layer, OAuth + MCP, per-environment config, tests and evals.
- Result: __ tests passing, cache hit rate __% and cost per comparison $__ (read from `/api/admin/stats`), eval pass rate __%.

## Glossary
**ACL** anti-corruption layer. **Job** background unit of work. **Principal** caller identity (`ip:`, `key:`, `user:`). **PKCE** proof key for code exchange. **DCR** dynamic client registration. **MCP** Model Context Protocol. **WAL** write-ahead logging in SQLite. **TTL** time to live. **Effective price** listed price minus verified instant discounts. **12-factor** config in the environment.

## Further reading
RFC 6749 and 7009 (OAuth, revocation), RFC 7636 (PKCE), RFC 7591 (client registration), RFC 8414 and 9728 (metadata), the OAuth 2.1 draft, the MCP specification, Kleppmann "Designing Data-Intensive Applications" (transactions, caching, batch/stream), Evans "Domain-Driven Design", Nygard "Release It!" (stability patterns).
