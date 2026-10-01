# Documentation to add as the project grows, and next features

## Docs worth writing (in priority order)
Already written: ARCHITECTURE, API, SECURITY, PRIVACY (draft), RUNBOOK (includes cost). Still to write:

1. **TERMS.md** - terms of service (needs a lawyer).
2. **EVALS.md** - a fixed list of 30-50 products with known correct prices; run weekly and track accuracy. This is how you catch silent regressions.
3. **STORE_COVERAGE.md** - which countries and cities work well, which stores block bots.
4. **CONTRIBUTING.md** - once others touch the code.

## Engineering next steps
- Postgres + Redis to run more than one instance.
- Email verification, password reset, account deletion; or delegate sign-in to an identity provider.
- Metrics dashboard: latency, cache hit rate, parse failures, cost per user.
- OAuth Client ID Metadata Documents (newer MCP spec) alongside dynamic registration.
- Price history table and alerts.
- Map picker (Leaflet + OpenStreetMap) as an alternative to GPS and typing.
- Automated tests and a CI workflow; run the evals in CI nightly.
