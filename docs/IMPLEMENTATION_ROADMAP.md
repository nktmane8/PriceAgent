# PriceAgent Implementation Roadmap

## Executive Summary

**Goal:** Transform PriceAgent from a Python/FastAPI prototype into a production-grade Java 21/Spring Boot platform.

**Timeline:** 26 weeks (~6 months)  
**Phases:** 11 (4 must-ship, 3 should-ship, 4 nice-to-have)  
**Success Metric:** Production-ready system serving 100k daily active users with 99.5% uptime.

---

## Phase 1: Java Foundation (Weeks 1-2)

### Objectives
- [ ] Create Java 21 + Spring Boot project scaffold
- [ ] Implement PostgreSQL with JPA entities (Job, User, Config)
- [ ] Port all REST APIs (`/api/v1/compare`, `/api/v1/job/{id}`)
- [ ] Implement OpenAI client wrapper with basic error handling
- [ ] Write integration tests matching Python version

### Deliverables
- [ ] `pom.xml` with all dependencies
- [ ] Entity classes: `Job.java`, `User.java`, `Config.java`, `Product.java`
- [ ] Repository interfaces: `JobRepository`, `UserRepository`
- [ ] Service layer: `ComparisonService`, `JobService`
- [ ] REST controllers: `ComparisonController`, `JobController`, `HealthController`
- [ ] OpenAI client: `OpenAIService` with request/response handling
- [ ] Docker Compose: local PostgreSQL + app
- [ ] Tests: 14+ unit tests (mirror Python test count)

### Success Criteria
- [ ] All tests pass: `mvn test`
- [ ] Smoke test returns same results as Python version
- [ ] PostgreSQL runs locally in Docker Compose
- [ ] App builds and runs without errors

### Interview Questions
- "How would you model a Job entity in JPA with proper relationships to User?"
- "What's the difference between @Service and @Component in Spring?"
- "How would you implement a repository pattern for the Job entity?"

---

## Phase 2: OAuth2 Server (Weeks 3-4)

### Objectives
- [ ] Implement Spring Authorization Server (not the custom single-endpoint version)
- [ ] Add JWT token provider with standard claims
- [ ] Implement PKCE flow (Proof Key for Code Exchange)
- [ ] Add refresh token support
- [ ] Secure the `/api/v1` endpoints with OAuth

### Deliverables
- [ ] `AuthorizationServerConfig.java` (Spring Authorization Server)
- [ ] `OAuth2Controller.java` (`/oauth/authorize`, `/oauth/token`, `/oauth/userinfo`)
- [ ] `JwtTokenProvider.java` (generate, validate, refresh)
- [ ] `SecurityConfig.java` (PKCE validation, authorization)
- [ ] OAuth endpoints:
  - `POST /oauth/token` (authorization code → access token + refresh token)
  - `GET /oauth/authorize` (login + consent screen)
  - `GET /oauth/userinfo` (validate token, return claims)
  - `POST /oauth/revoke` (logout)

### Success Criteria
- [ ] OAuth flow works end-to-end (auth code → access token → API call)
- [ ] PKCE is enforced (code_challenge required on /authorize)
- [ ] Refresh tokens work (expired access token → new access token)
- [ ] Tests cover: valid PKCE, missing PKCE, expired token, invalid refresh token

### Interview Questions
- "Explain the OAuth2 authorization code flow with PKCE."
- "Why is PKCE necessary? What does it protect against?"
- "How would you handle token refresh in a Spring Boot application?"
- "What's the difference between access tokens and refresh tokens?"

---

## Phase 3: Product Identity & Deterministic Pricing (Weeks 5-6)

### Objectives
- [ ] Design a strong Product entity with identity hashing
- [ ] Implement ProductVariant (size, color, storage, etc.)
- [ ] Build product matching logic (deterministic, no LLM)
- [ ] Create PricingEngine (tax, discount, shipping calculations)
- [ ] Validate that price comparisons don't mix variants

### Deliverables
- [ ] `Product.java` entity with identity hash
- [ ] `ProductVariant.java` entity
- [ ] `ProductMatcher.java` (deterministic matching algorithm)
- [ ] `PricingEngine.java`:
  - Base price calculation
  - Discount application
  - Tax calculation (country-specific)
  - Shipping cost
  - Effective price (total)
- [ ] `ProductValidator.java` (guardrail to prevent mixing iPhone 256GB with 512GB)
- [ ] Unit tests for product matching (100% deterministic)

### Success Criteria
- [ ] Product matching: same input → same output, always
- [ ] Tests prove that "iPhone 15 256GB Black" ≠ "iPhone 15 512GB Black"
- [ ] Pricing calculations are all in code, not in OpenAI prompts
- [ ] All calculations are tested with real data

### Interview Questions
- "How would you design a product identity model to prevent comparing different variants?"
- "Why should pricing calculations never be done by an LLM?"
- "Design a schema for storing product variants (size, color, storage, material)."
- "How would you implement country-specific tax calculation?"

---

## Phase 4: Resilience & Error Handling (Weeks 7-8)

### Objectives
- [ ] Add Resilience4j for retry, circuit breaker, timeout
- [ ] Implement OpenAI-specific error handling (429 → retry, 404 → invalid model)
- [ ] Add provider fallback (if OpenAI fails, use cheaper model)
- [ ] Implement cost tracking per request
- [ ] Make error messages user-readable

### Deliverables
- [ ] `Resilience4jConfig.java`:
  - Retry: max 3 attempts, exponential backoff with jitter
  - CircuitBreaker: 50% failure threshold, 30-second sliding window
  - Timeout: 45 seconds max for OpenAI calls
- [ ] `OpenAIService.java` with decorators:
  ```java
  @Retry(...)
  @CircuitBreaker(...)
  @Timeout(...)
  public ComparisonResult search(String query, String country) { ... }
  ```
- [ ] `OpenAIErrorHandler.java` (map API errors to user-readable messages)
- [ ] `CostTracker.java` (log cost per request, warn if > threshold)
- [ ] Integration tests with WireMock (fake OpenAI, return 429, timeout, 500)

### Success Criteria
- [ ] OpenAI 429 triggers exponential backoff (not immediate fail)
- [ ] After 5 failures in 60 seconds, circuit breaker opens (fast fail)
- [ ] Job error message is user-readable (not stack trace)
- [ ] Tests cover: retry success, circuit breaker open, timeout, invalid model
- [ ] Smoke test `--key` flag returns records (end-to-end OpenAI works)

### Interview Questions
- "Design a retry strategy for external API calls. What's the difference between retry and circuit breaker?"
- "How would you implement exponential backoff with jitter?"
- "What happens if OpenAI returns 429 (quota exceeded)? How would you handle it?"
- "Design a circuit breaker for an external service. What are the states?"

---

## Phase 5: Redis Caching Layer (Weeks 9-10)

### Objectives
- [ ] Add Redis (Lettuce client) for comparison caching
- [ ] Implement @Cacheable for OpenAI results (24h TTL)
- [ ] Add distributed rate limiting (X requests per day per API key)
- [ ] Implement distributed job locks (prevent duplicate processing)
- [ ] Set up cache warming and invalidation

### Deliverables
- [ ] `RedisCacheConfig.java` (Lettuce, TTL policies, eviction)
- [ ] Comparison caching:
  ```java
  @Cacheable(
    value = "comparisons",
    key = "#productHash + ':' + #country",
    cacheManager = "redisCacheManager",
    unless = "#result == null"
  )
  public ComparisonResult getComparison(String productHash, String country) { ... }
  ```
- [ ] `RateLimitService.java` (token bucket, sliding window, per API key)
- [ ] `DistributedLockService.java` (Redis SETNX, prevent job duplication)
- [ ] Integration tests with Testcontainers (real Redis in test)
- [ ] Cache hit/miss metrics (Micrometer)

### Success Criteria
- [ ] Identical requests return cached results within 10ms
- [ ] Cache hit rate > 40% in production
- [ ] Rate limit is enforced per API key, per day
- [ ] Tests verify cache invalidation, TTL expiration, lock release
- [ ] Metrics show cache hit ratio, eviction count

### Interview Questions
- "How would you design a cache key for price comparisons?"
- "What's the difference between cache-aside and write-through patterns?"
- "Design a rate limiting system using Redis."
- "How would you handle cache invalidation?"
- "What happens if Redis goes down? How do you gracefully degrade?"

---

## Phase 6: Kafka Async Jobs (Weeks 11-12)

### Objectives
- [ ] Add Kafka producer (publish comparison request event)
- [ ] Implement Kafka consumer (process comparison in background)
- [ ] Design job status transitions (pending → running → completed → failed)
- [ ] Ensure idempotency (same job processed twice → same result)
- [ ] Implement dead-letter queue (failed jobs after N retries)

### Deliverables
- [ ] `KafkaProducerConfig.java` (topic, partitions, replication)
- [ ] `ComparisonRequestProducer.java`:
  ```java
  public void publishComparisonRequest(Job job) {
      kafkaTemplate.send("comparison-requests", job.getId(), event);
  }
  ```
- [ ] `ComparisonWorker.java` (Kafka consumer):
  ```java
  @KafkaListener(topics = "comparison-requests", groupId = "comparison-group")
  public void process(ComparisonEvent event) { ... }
  ```
- [ ] `ComparisonRequestValidator.java` (idempotency checks)
- [ ] `DeadLetterHandler.java` (send failed jobs to dlq after retries)
- [ ] Integration tests with embedded Kafka (Testcontainers)
- [ ] Metrics: consumer lag, throughput, error rate

### Success Criteria
- [ ] REST API returns in < 50ms (async, not waiting for OpenAI)
- [ ] Kafka consumers process jobs in parallel (3 replicas)
- [ ] Failed jobs are retried with backoff, then sent to DLQ
- [ ] Tests prove idempotency (same job processed twice → same result)
- [ ] Kafka consumer lag < 1 minute in production

### Interview Questions
- "Why use Kafka instead of RabbitMQ for async jobs?"
- "How do you ensure idempotency in Kafka consumers?"
- "What happens if a consumer crashes before committing an offset?"
- "Design a dead-letter queue strategy for failed jobs."
- "How would you debug slow Kafka consumer lag?"

---

## Phase 7: Cloud Deployment & CI/CD (Weeks 13-14)

### Objectives
- [ ] Containerize the Java application (Dockerfile)
- [ ] Create Docker Compose for local development (PostgreSQL, Redis, Kafka)
- [ ] Implement GitHub Actions CI/CD pipeline
- [ ] Deploy to Render or equivalent cloud platform
- [ ] Run smoke tests as post-deploy validation

### Deliverables
- [ ] `Dockerfile` (multi-stage, JDK 21, slim base image)
- [ ] `docker-compose.yml` (app, PostgreSQL, Redis, Kafka)
- [ ] `.github/workflows/ci.yml`:
  - Commit: compile, unit tests
  - Static analysis: SonarQube, Checkstyle
  - Integration tests: Testcontainers
  - Build: Docker image, push to registry
  - Deploy: to Render, Google Cloud Run, or AWS
  - Smoke test: post-deploy health checks
- [ ] `tools/smoke-test.sh` (check /healthz, /oauth discovery, /mcp auth, optional real comparison)
- [ ] Environment configuration: `.env.example`, Render deployment variables

### Success Criteria
- [ ] `git push` triggers CI automatically
- [ ] All tests pass before building Docker image
- [ ] Smoke test runs after deploy and blocks deployment on failure
- [ ] Rollback to previous version is one click

### Interview Questions
- "Design a CI/CD pipeline for a Spring Boot application."
- "How would you handle secrets in a CI/CD pipeline (API keys, database passwords)?"
- "What should a post-deploy smoke test check?"
- "How would you implement blue-green deployment or canary deployment?"

---

## Phase 8: Observability (Weeks 15-16)

### Objectives
- [ ] Add structured logging (JSON, correlation IDs)
- [ ] Implement Micrometer metrics (latency, error rate, cache hit ratio)
- [ ] Add OpenTelemetry distributed tracing
- [ ] Create Prometheus scraping configuration
- [ ] Build Grafana dashboards

### Deliverables
- [ ] `LoggingConfig.java` (SLF4J with Logback, JSON format)
- [ ] Correlation ID middleware:
  ```java
  @Component
  public class CorrelationIdFilter implements Filter {
      public void doFilter(ServletRequest req, ...) {
          String correlationId = UUID.randomUUID().toString();
          MDC.put("correlationId", correlationId);
          // ... request processing
      }
  }
  ```
- [ ] `MetricsConfig.java` (Micrometer, Prometheus):
  - Request latency (timer)
  - Error rate (counter)
  - Cache hit ratio (gauge)
  - OpenAI API latency (timer)
  - Job processing time (timer)
- [ ] `OpenTelemetryConfig.java` (tracing, span context propagation)
- [ ] Prometheus endpoint: `/actuator/prometheus`
- [ ] Grafana dashboards: request rate, latency percentiles, error rate, cache hit ratio

### Success Criteria
- [ ] Every request has a correlation ID in logs
- [ ] Slow queries (> 1s) are logged with execution plan
- [ ] Prometheus scrapes metrics successfully
- [ ] Grafana shows latency percentiles (p50, p95, p99)

### Interview Questions
- "How would you design a logging strategy for a distributed system?"
- "What information should a correlation ID include?"
- "How would you monitor OpenAI API latency and cost?"
- "Design a Grafana dashboard for a price comparison service."

---

## Phase 9: Spring AI & Agents (Weeks 17-20)

### Objectives
- [ ] Integrate Spring AI framework
- [ ] Implement tool calling (Search, ProductMatch, Pricing, Store lookup)
- [ ] Design agent orchestration layer
- [ ] Add prompt versioning and A/B testing
- [ ] Implement structured output validation

### Deliverables
- [ ] Spring AI dependency and configuration
- [ ] Tool definitions:
  - `SearchTool.java` (web search, returns store results)
  - `ProductMatchTool.java` (deterministic product matching)
  - `PricingTool.java` (calculate effective price)
  - `StoreTool.java` (fetch store metadata)
- [ ] `AgentOrchestrator.java` (router, determines which tools to call)
- [ ] `PromptVersionManager.java` (versioning, A/B tests)
- [ ] `ResponseValidator.java` (validates LLM output, prevents hallucination)
- [ ] Integration tests: agents don't hallucinate product matches

### Success Criteria
- [ ] Agent framework eliminates raw OpenAI client calls
- [ ] Tool results are validated before use
- [ ] Prompts can be versioned and A/B tested
- [ ] Tests prove agents don't match mismatched product variants

### Interview Questions
- "Design a tool calling architecture for an LLM agent."
- "How would you prevent an LLM agent from hallucinating?"
- "Why would you version prompts? How would you A/B test them?"

---

## Phase 10: MCP Server Implementation (Weeks 21-22)

### Objectives
- [ ] Implement MCP (Model Context Protocol) server
- [ ] Expose PriceAgent tools to external clients
- [ ] Secure MCP endpoint with OAuth tokens
- [ ] Rate limiting per MCP client
- [ ] Document MCP server capabilities

### Deliverables
- [ ] `MCPServerController.java` (JSON-RPC 2.0 handler)
- [ ] MCP tool definitions (compatible with Claude, other LLMs)
- [ ] `MCPAuthenticationFilter.java` (OAuth token validation)
- [ ] Integration tests: external client calls MCP endpoint

### Success Criteria
- [ ] External client can call `/mcp` with tool requests
- [ ] Responses match the MCP JSON-RPC schema
- [ ] Authentication is enforced (401 for missing token)

---

## Phase 11: Kubernetes & Scaling (Weeks 23-26)

### Objectives
- [ ] Create Kubernetes manifests (Deployment, Service, etc.)
- [ ] Implement horizontal autoscaling (Horizontal Pod Autoscaler)
- [ ] Set up readiness/liveness probes
- [ ] Deploy Kafka and PostgreSQL on Kubernetes
- [ ] Demonstrate zero-downtime rolling deployment

### Deliverables
- [ ] `k8s/app-deployment.yaml` (replicas, resource limits, probes)
- [ ] `k8s/app-service.yaml` (load balancer or ingress)
- [ ] `k8s/postgres-statefulset.yaml` (persistent storage)
- [ ] `k8s/kafka-statefulset.yaml` (3+ brokers)
- [ ] `k8s/hpa.yaml` (autoscale on CPU/memory)
- [ ] `k8s/configmap.yaml`, `k8s/secret.yaml` (config, secrets)

### Success Criteria
- [ ] App scales from 1 to 10 replicas automatically
- [ ] Database handles 1000 concurrent connections (via connection pooling)
- [ ] Rolling deployment shows zero downtime
- [ ] Load test: 1000 RPS, p99 latency < 1s

---

## Git Workflow & PRs

### Branch Naming
```
feature/phase-1-java-foundation
feature/phase-2-oauth2
feature/phase-3-product-identity
feature/phase-4-resilience
feature/phase-5-redis
feature/phase-6-kafka
feature/phase-7-cloud
feature/phase-8-observability
feature/phase-9-spring-ai
feature/phase-10-mcp
feature/phase-11-kubernetes
```

### PR Checklist
- [ ] Problem statement in PR description
- [ ] Architecture explanation
- [ ] Code changes (with tests)
- [ ] Documentation (README, docs/*.md, ADRs)
- [ ] Performance impact (if applicable)
- [ ] Screenshots/diagrams (if applicable)
- [ ] Interview questions generated

---

## Success Metrics

### Performance
- Latency: p95 < 100ms (with cache), p95 < 1s (cache miss)
- Throughput: 100 requests/s sustained
- Error rate: < 0.5%

### Reliability
- Uptime: 99.5%+
- MTTR: < 5 minutes
- Retry success rate: 90%+

### User Experience
- Sign-in: < 2s (OAuth)
- Comparison: < 200ms (cache hit), < 30s (cache miss, OpenAI)
- Error clarity: users understand why a job failed

### Cost
- Cloud infrastructure: < $100/month
- OpenAI: track per-user, warn if > $1/day

---

## Estimated Effort

| Phase | Duration | Effort | Difficulty |
|-------|----------|--------|------------|
| 1: Java Foundation | 2w | 80h | Medium |
| 2: OAuth2 | 2w | 60h | Medium |
| 3: Product Identity | 2w | 40h | Medium |
| 4: Resilience | 2w | 50h | Medium |
| 5: Redis | 2w | 40h | Low-Medium |
| 6: Kafka | 2w | 60h | Medium-High |
| 7: Cloud | 2w | 40h | Low-Medium |
| 8: Observability | 2w | 40h | Low-Medium |
| 9: Spring AI | 4w | 100h | Medium-High |
| 10: MCP | 2w | 40h | Medium |
| 11: Kubernetes | 4w | 80h | High |
| **Total** | **26w** | **630h** | |

---

## Risk Assessment & Mitigation

### Risk: PostgreSQL migration fails
- **Impact:** Data loss, rollback required
- **Mitigation:** Test migration on staging, backup strategy, rollback plan

### Risk: Kafka adds complexity
- **Impact:** Operational overhead, harder debugging
- **Mitigation:** Start with simple producer/consumer, add resilience incrementally

### Risk: Kubernetes is overkill
- **Impact:** Waste time on infrastructure, not features
- **Mitigation:** Start with Render, move to Kubernetes only if scaling demands it

### Risk: OpenAI API changes
- **Impact:** Breaking changes, API deprecated
- **Mitigation:** Implement fallback providers (gpt-4o-mini), monitor API announcements

---

## Next Steps

1. **Approve this roadmap.** Any changes?
2. **Start Phase 1.** Create Java project, run first tests.
3. **Weekly reviews.** Adjust timeline based on actual progress.
4. **Document learnings.** Use engineering journal template.

