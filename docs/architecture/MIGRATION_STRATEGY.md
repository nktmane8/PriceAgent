# Python V1 → Java V2 Migration Strategy

## Overview

This document explains the evolutionary journey from the Python prototype to the production Java platform.

**Timeline:**
- **V1 (Current):** Python + FastAPI + SQLite
- **V2 (6-8 weeks):** Java 21 + Spring Boot + PostgreSQL + basic resilience
- **V3 (8-10 weeks):** Add Redis caching + Kafka async jobs
- **V4 (4-6 weeks):** Cloud + Docker + CI/CD
- **V5 (4-6 weeks):** Observability + advanced resilience
- **V6 (8-12 weeks):** Spring AI + MCP integration
- **V7 (Ongoing):** Selective service extraction only where justified

## Phase 1: Java Foundation (Weeks 1-2)

### Goal
Get a working Java 21 Spring Boot project that matches V1 functionality exactly.

### Deliverables
1. Spring Boot skeleton with PostgreSQL
2. Job and User entities (JPA)
3. OpenAI client wrapper
4. REST API endpoints (`/api/v1/compare`, `/api/v1/job/{id}`)
5. Basic tests

### Success Criteria
- All 14 existing tests pass in Java equivalent
- Smoke test returns the same results as Python
- PostgreSQL runs in docker-compose locally
- Code compiles and tests pass on every commit

## Phase 2: OAuth2 + Security (Weeks 3-4)

### Goal
Implement a standard OAuth2 server (not the custom single-endpoint version).

### Deliverables
1. Spring Security configuration
2. OAuth2 Authorization Server (Spring Authorization Server)
3. JWT token provider
4. PKCE support
5. Refresh token logic
6. `/oauth/authorize`, `/oauth/token`, `/oauth/userinfo`

### Success Criteria
- OAuth flow works end-to-end
- Tokens are verified on protected endpoints
- PKCE is enforced
- Tests cover auth failures (invalid PKCE, expired token, etc.)

## Phase 3: Product Identity + Deterministic Pricing (Weeks 5-6)

### Goal
Build a strong domain model that prevents comparing different product variants.

### Deliverables
1. Product entity with identity hashing
2. ProductVariant entity (size, color, storage)
3. Product matching logic (deterministic)
4. PricingEngine (for calculating effective price)
5. Validation rules

### Success Criteria
- Product matching is 100% deterministic (same input → same output)
- Tests prove that "iPhone 15 256GB" ≠ "iPhone 15 512GB"
- Pricing calculations are all in code, never in LLM

## Phase 4: OpenAI Integration + Resilience (Weeks 7-8)

### Goal
Implement OpenAI calls with retry, circuit breaker, and clear error handling.

### Deliverables
1. OpenAI client using Spring WebClient
2. Resilience4j decorators (retry, circuit breaker, timeout)
3. Provider-specific error handling (429 → retry with backoff, 404 → invalid model)
4. Clear error messages in job results
5. Cost estimation per request

### Success Criteria
- OpenAI 429 (quota) triggers exponential backoff (max 3 retries)
- OpenAI timeout (> 30s) short-circuits after 5 failures in 60s
- Job error message is user-readable, not a stack trace
- Smoke test with `--key` returns records
- Cost is logged per job

### Code Example (Resilience)

```java
@Service
public class OpenAIService {
    private final Retry retry = Retry.of("openai", RetryConfig.custom()
        .maxAttempts(3)
        .waitDuration(Duration.ofSeconds(1))
        .intervalFunction(IntervalFunction.ofExponentialBackoff(1000, 2))
        .build());
    
    private final CircuitBreaker circuitBreaker = CircuitBreaker.of("openai", 
        CircuitBreakerConfig.custom()
        .failureRateThreshold(50.0f)
        .slowCallRateThreshold(50.0f)
        .slowCallDurationThreshold(Duration.ofSeconds(30))
        .slidingWindowSize(10)
        .build());
    
    public ComparisonResult search(String productQuery, String country) {
        return Decorators.ofSupplier(() -> callOpenAI(productQuery, country))
            .withRetry(retry)
            .withCircuitBreaker(circuitBreaker)
            .withTimeout(Duration.ofSeconds(45))
            .get();
    }
}
```

## Phase 5: Caching + Distributed Coordination (Weeks 9-10)

### Goal
Introduce Redis for caching, locks, and rate limiting.

### Deliverables
1. Redis connection (Lettuce)
2. Comparison result caching (24h TTL)
3. Rate limit middleware (X requests per day per API key)
4. Distributed job lock (prevent duplicate processing)
5. Integration tests with Testcontainers

### Success Criteria
- Identical requests return cached results within 10ms
- Cache hit rate > 40% in production
- Rate limit is enforced per API key, per day
- Tests verify cache invalidation and TTL

## Phase 6: Async Jobs with Kafka (Weeks 11-12)

### Goal
Decouple REST API from long-running OpenAI calls.

### Deliverables
1. Kafka producer (publish comparison request)
2. Kafka consumer (process comparison)
3. Job status transitions (pending → running → completed)
4. Idempotency checks
5. Dead-letter queue for failed jobs

### Success Criteria
- REST API returns in < 50ms (even if OpenAI would take 30s)
- Kafka consumer processes jobs in parallel (3 replicas)
- Failed jobs are retried with backoff
- Tests prove idempotency (same job processed twice → same result)

## Phase 7: Cloud + CI/CD (Weeks 13-14)

### Goal
Deploy to Render (or equivalent) with automated testing and rollback.

### Deliverables
1. Dockerfile for Java application
2. docker-compose.yml for local development
3. GitHub Actions CI/CD pipeline
4. Smoke test in post-deploy hook
5. Monitoring alerts (Uptime Robot or similar)

### Success Criteria
- `git push` triggers CI → tests → build → deploy
- Smoke test runs after deploy and fails the deploy if it fails
- Environment variables are correctly set on Render
- Rollback is easy (previous version tag)

## Phase 8: Observability (Weeks 15-16)

### Goal
Add structured logging, metrics, and distributed tracing.

### Deliverables
1. Micrometer metrics (latency, error rate, cache hit ratio)
2. Structured logging (JSON, correlation IDs)
3. OpenTelemetry tracing (request paths across components)
4. Prometheus scraping
5. Health checks (`/actuator/health`)

### Success Criteria
- Every request has a correlation ID
- Slow queries (> 1s) are logged with execution plan
- Prometheus shows latency percentiles (p50, p95, p99)
- Grafana dashboards show system health

## Phase 9: Spring AI + Agents (Weeks 17-20)

### Goal
Integrate Spring AI framework and design an agent orchestration layer.

### Deliverables
1. Spring AI OpenAI integration
2. Tool calling (Search, ProductMatch, Pricing, Store lookup)
3. Prompt versioning
4. Structured output validation
5. Agent orchestrator (routes to correct tool)

### Success Criteria
- Agent framework eliminates raw OpenAI client calls
- Tool results are validated before use
- Prompts are versioned and can be A/B tested
- Tests prove that agents don't hallucinate product matches

## Phase 10: MCP Server in Java (Weeks 21-22)

### Goal
Expose PriceAgent as an MCP server so other apps can call it.

### Deliverables
1. MCP server implementation (JSON-RPC 2.0 over HTTP)
2. Tool definitions (search, compare, get_stores)
3. Authentication (OAuth tokens or API keys)
4. Rate limiting per client

### Success Criteria
- External client can call `/mcp` with tool requests
- Responses match the MCP JSON-RPC schema
- Tests verify authentication is enforced

## Phase 11: Scaling + Kubernetes (Weeks 23-26)

### Goal
Move from Render to Kubernetes (or equivalent) for horizontal scaling.

### Deliverables
1. Kubernetes manifests (Deployment, Service, ConfigMap, Secret)
2. Readiness/liveness probes
3. Horizontal Pod Autoscaler (scale on CPU/memory)
4. StatefulSet for Kafka brokers
5. PersistentVolume for PostgreSQL

### Success Criteria
- App scales from 1 to 10 replicas based on load
- Database can handle 1000 concurrent connections (via pooling)
- Kafka consumer group scales across multiple pods
- Zero-downtime rolling deployments

## Milestones & Go/No-Go Criteria

| Phase | Duration | Go/No-Go | Criteria |
|-------|----------|----------|----------|
| 1: Java Foundation | 2w | Must ship | Feature parity with V1, tests pass, smoke test works |
| 2: OAuth2 | 2w | Must ship | Auth flow end-to-end, refresh tokens, PKCE verified |
| 3: Domain Model | 2w | Must ship | Product matching deterministic, pricing calculated, tests prove correctness |
| 4: Resilience | 2w | Must ship | Retry + circuit breaker work, errors are user-readable |
| 5: Redis | 2w | Should ship | Cache hit rate > 40%, no data consistency issues |
| 6: Kafka | 2w | Should ship | Async jobs work, consumer lag < 1m, tests prove idempotency |
| 7: Cloud | 2w | Should ship | CI/CD automated, smoke test in post-deploy hook |
| 8: Observability | 2w | Nice-to-have | Metrics, logging, tracing integrated; dashboards in Grafana |
| 9: Spring AI | 4w | Nice-to-have | Agent orchestration, tool calling, prompt versioning |
| 10: MCP | 2w | Nice-to-have | MCP server works, authenticated, external clients can call |
| 11: Kubernetes | 4w | Nice-to-have | Scales horizontally, zero-downtime deployments |

## Estimated Timeline

- **Must-ship phases (1-4):** 8 weeks
- **Should-ship phases (5-7):** 6 weeks
- **Nice-to-have phases (8-11):** 12 weeks

**Total:** 26 weeks (~6 months) for a production-grade system.

## Success Metrics

### Performance
- **Latency:** p95 < 1s (for /api/v1/job/{id}), p95 < 100ms (with cache)
- **Throughput:** 100 requests/s sustained
- **Error rate:** < 0.5%

### Reliability
- **Uptime:** 99.5%+
- **MTTR (Mean Time To Recovery):** < 5 minutes
- **Retry success rate:** 90%+ (of failed requests eventually succeed)

### Cost
- **AWS/Render:** < $100/month
- **OpenAI:** Track per-user, warn if > $1/day

### User Experience
- **Sign-in:** < 2s (OAuth flow)
- **Comparison:** < 200ms (cache hit), < 30s (cache miss, OpenAI call)
- **Error clarity:** User understands why a job failed

## Decision Gates

After each phase, we decide:
1. **Continue as planned** (go to next phase)
2. **Adjust and continue** (found issues, fix them, then continue)
3. **Rethink** (fundamental problem, need architecture change)

Example: If Phase 1 (Java Foundation) shows that Spring Boot + JPA is too verbose, we might switch to Quarkus. If Phase 4 (Resilience) shows OpenAI calls still fail too often, we might add a fallback to a cheaper LLM.

