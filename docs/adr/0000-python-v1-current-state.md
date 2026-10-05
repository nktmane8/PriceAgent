# ADR-000: Python V1 Current State

**Status:** Accepted (Current implementation, baseline for Java migration)

## Context

PriceAgent started as an AI prototype using Python/FastAPI. The system compares product prices across multiple e-commerce stores using OpenAI with web search capabilities.

**Deployment:** Render (free tier) at https://priceagent.onrender.com

## Problem

1. **Not production-ready.** Single-instance SQLite, no horizontal scaling, no distributed coordination.
2. **AI-driven architecture.** Every comparison call goes through OpenAI, with no deterministic pricing layer.
3. **No resilience.** No retry logic, circuit breaker, or graceful degradation.
4. **OAuth is custom.** Implemented from scratch, non-standard (single-endpoint), no refresh tokens.
5. **Limited observability.** Minimal structured logging, no metrics, no distributed tracing.
6. **Synchronous only.** All comparisons are synchronous; background jobs are simple polling.
7. **No caching.** Every identical request hits OpenAI again.
8. **Deployment coupling.** Tightly tied to Render's SQLite; no local Docker Compose.

## Architecture (V1)

```
User (web page or API)
  ↓
FastAPI app (single instance, no load balancer)
  ↓
OAuth (custom single-endpoint server, SQLite sessions)
  ↓
OpenAI Responses API (web_search tool, pause_turn loop removed in v2.6.0)
  ↓
SQLite (single .db file, no connection pooling)
  ↓
Static pages + MCP endpoint (for external tool access)
```

## Current Capabilities

- **REST API:** `/api/v1/compare` (POST, async job), `/api/v1/job/{id}` (GET, poll)
- **OAuth:** Custom server at `/oauth/authorize`, `/oauth/token`, with PKCE
- **Web page:** Single-page app, unauthenticated price comparison
- **MCP:** `/mcp` endpoint (authenticated, tool-call format)
- **Database:** SQLite with `users`, `jobs`, `config` tables
- **Testing:** 14 unit tests, no integration tests

## Technology Stack (V1)

- **Language:** Python 3.12
- **Framework:** FastAPI, Uvicorn
- **Database:** SQLite
- **AI:** OpenAI (Responses API + web_search tool)
- **Auth:** Custom OAuth2 (PKCE)
- **Deployment:** Render (free tier)
- **Testing:** Pytest

## Known Issues (P0/P1/P2)

### P0 — Critical

- **No retry on OpenAI failure.** If OpenAI returns 429 (quota) or 500, the job fails with no backoff. Users see no actionable error.
- **MCP endpoint not working.** Path is `/mcp` but endpoint authentication/response handling may be broken.
- **Records not fetching.** Smoke test with `--key` fails to return store results. Likely causes:
  - Model name (`gpt-5.6-sol` or similar) is invalid on the OpenAI account.
  - `OPENAI_API_KEY` is not set on Render.
  - `PUBLIC_URL` is incorrect (used for OAuth redirects).

### P1 — Important

- **No distributed caching.** Identical comparisons hit OpenAI repeatedly.
- **OAuth is fragile.** Single-endpoint server, no standard refresh tokens, session state in SQLite.
- **No observability.** Logs are unstructured; no metrics, no tracing, no health probes.
- **Synchronous-only jobs.** Background workers are simple polling; no event queue.
- **No rate limiting.** Users can spam `/api/v1/compare` and drain OpenAI credits.
- **Product matching is LLM-only.** No deterministic product identity or validation.

### P2 — Improvement

- **Docker Compose not complete.** Can't run the full stack locally (Render-specific SQLite).
- **No cost estimation.** System doesn't track or warn about OpenAI spend per user.
- **Dead config.** `MAX_PAUSE_LOOPS` (left over from pause_turn loop) does nothing.
- **Standalone web login missing.** OAuth login only works inside the authorize flow; web page has no session login.
- **No CI smoke test.** Post-deploy validation happens manually.

## Why V1 Works Despite Issues

1. **Prototype goal:** Demonstrates rapid AI integration and OAuth flow.
2. **Low traffic:** Free Render tier handles ~100 requests/day.
3. **No SLA:** Users accept "it might fail."
4. **Simple domain:** Price comparison is straightforward; AI hallucination is acceptable for exploration.

## Consequences

- **Scalability ceiling:** Can't exceed Render's free instance limits (~512 MB RAM, 10 connections SQLite).
- **Reliability ceiling:** No retry, no fallback, no graceful degradation.
- **Observability ceiling:** Can't diagnose production failures.
- **Security baseline:** OAuth is custom; no standard scopes, no refresh tokens, single-endpoint.

## Next Step (V2)

Migrate to Java 21 + Spring Boot + PostgreSQL. Start with feature parity, then add:
- Resilience (retry, circuit breaker, timeout)
- Redis caching
- Kafka for background jobs
- Proper OAuth2 server
- Observability (Micrometer, OpenTelemetry)
- Deterministic pricing engine

## Interview Takeaway

> "Started with a working Python prototype that proved the business model (AI + web search + OAuth) but hit architectural limits. Identified P0 reliability issues (no retry), P1 scalability issues (no caching, no background jobs), and P2 observability gaps. Designed a Java migration strategy that preserves the working pieces while addressing each limitation."

