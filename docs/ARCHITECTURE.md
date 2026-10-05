# PriceAgent Architecture

## Target architecture

PriceAgent is evolving from a single-process Python prototype into a production-ready, provider-agnostic Java 21 platform. The first target is a modular monolith, not immediate microservices.

### High-level flow

Clients (Browser / REST / AI Apps / MCP)
-> API and Security Layer
-> Spring Boot application
-> PostgreSQL for durable state
-> Redis/Valkey for cache, locks, rate limits and queue state
-> Workers for expensive asynchronous work
-> Search/Web providers
-> AI Gateway
-> Groq / Gemini / OpenAI / Hugging Face / Ollama

Observability surrounds every layer:
Metrics -> Micrometer
Health -> Actuator
Tracing -> OpenTelemetry
Logs -> structured logs with request_id, trace_id and job_id

## Project structure

Recommended Java structure:

apps/price-agent-java/
  src/main/java/com/nktmane/priceagent/
    PriceAgentApplication.java

    common/
      config/
      error/
      security/
      observability/

    compare/
      api/
      application/
      domain/
      infrastructure/

    jobs/
      api/
      application/
      domain/
      infrastructure/

    product/
      api/
      application/
      domain/
      infrastructure/

    pricing/
      application/
      domain/
      infrastructure/

    search/
      application/
      domain/
      infrastructure/

    ai/
      api/
      application/
      domain/
      infrastructure/
        groq/
        gemini/
        openai/
        huggingface/
        ollama/

    insights/
    accounts/
    mcp/

  src/main/resources/
    application.yml
    application-dev.yml
    application-prod.yml

  src/test/java/com/nktmane/priceagent/
    unit/
    integration/
    architecture/

Spring Boot recommends placing the main application class in a root package above the application components. Domain-based structuring is also recommended when stronger module boundaries are desired. citeturn0search1

## Dependency rules

API -> Application -> Domain

Infrastructure implements ports defined by the application/domain layers.

The domain must not depend directly on:
- Spring
- PostgreSQL
- Redis
- Kafka
- HTTP clients
- AI SDKs

This gives us a Ports and Adapters architecture while retaining a modular-monolith deployment.

## Core modules

| Module | Responsibility |
|---|---|
| compare | Comparison use-case orchestration |
| jobs | Durable asynchronous job lifecycle |
| product | Product identity, variants and matching |
| pricing | Normalization, discounts and effective price |
| search | Store/web discovery and source extraction |
| ai | Provider routing, fallback and AI calls |
| insights | Reviews, pros/cons and alternatives |
| accounts | Users, OAuth and API authorization |
| mcp | MCP transport and tools |
| common | Security, errors and observability |

## AI Gateway

AIProvider
-> ProviderRouter
-> Groq
-> Gemini
-> OpenAI
-> Hugging Face
-> Ollama

ProviderRouter decides using:
- configured priority
- provider availability
- capability
- recent health
- timeout/failure state
- quota state

Provider failure, transient timeout or applicable rate limit moves execution to the next eligible provider.

The comparison domain must never depend on a specific AI provider.

## Job architecture

### Current

HTTP -> process-local ThreadPoolExecutor -> SQLite

This is suitable only for local development or a single instance.

### Target

POST /compare
-> create job in PostgreSQL
-> publish job to Redis/Valkey
-> return 202 + jobId

Worker
-> load job
-> search
-> normalize products
-> calculate deterministic prices
-> call AI Gateway only where AI is required
-> persist result
-> mark job COMPLETED or FAILED

GET /jobs/{id}
-> PostgreSQL
-> return current state/result

This removes process-local job state and allows multiple API and worker instances.

## Data ownership

PostgreSQL is the source of truth for:
- users
- OAuth data
- jobs
- comparison results
- products
- normalized prices
- price history
- usage/audit data

Redis/Valkey owns short-lived operational state:
- cache
- rate-limit counters
- distributed locks
- queue/stream state where appropriate

Kafka is a later-stage addition for durable event streaming and independent consumers. It is not required for the first production runtime.

## Reliability

External calls follow:

Timeout
-> retry only transient failures
-> circuit breaker
-> fallback provider/source
-> controlled failure

Do not retry:
- invalid credentials
- authorization failures
- invalid requests
- unsupported models
- hard quota/billing exhaustion

Retry where appropriate:
- 429
- connection failures
- timeouts
- transient 502/503/504

Every attempt records provider, model, latency, status and error classification.

## Security boundary

Client
-> authentication/authorization
-> input validation
-> application use case
-> provider gateway
-> external service

Required controls:
- OAuth/API-key authentication
- resource authorization
- request validation
- rate limiting
- CORS/Origin/Host validation
- outbound request restrictions
- prompt-injection-aware tool boundaries
- audit logging
- secret rotation

API keys and tokens must never be committed to GitHub.

## Observability

Every request/job/provider call should carry:
- request_id
- trace_id
- job_id
- provider
- model
- status
- latency_ms
- error_code

Core metrics:
- http_requests_total
- job_created_total
- job_completed_total
- job_failed_total
- job_duration
- provider_requests_total
- provider_failures_total
- provider_latency
- provider_429_total
- provider_quota_exhausted_total
- queue_depth
- database_latency
- cache_hit_ratio

Spring Boot provides production features such as health checks and metrics, with Actuator/Micrometer forming the base for the observability layer. citeturn0search0turn0search7

## Current implementation status\n\nThe Python application now contains the target distributed building blocks: PostgreSQL storage, Redis/Valkey-backed RQ jobs, a dedicated worker, multi-provider AI routing, OAuth-protected browser/API flows and OAuth-protected MCP. These components are implemented in code, but the Render workspace still needs the Postgres/Key Value/worker resources provisioned and end-to-end validated before this architecture is considered production-stable.\n\n## Migration structure

Phase 0: release-gate the Python reference implementation\n- complete Postgres/Valkey/worker deployment validation\n- complete OAuth/MCP interoperability tests\n- complete backup/restore, load and failure drills\n- freeze API, MCP and behavioral contracts\n\nPhase 1: stabilize Python
- provider fallback
- automated tests
- Render deployment verification
- API/MCP compatibility

Phase 2: distributed runtime
- PostgreSQL
- Redis/Valkey
- persistent job repository
- background worker
- idempotency

Phase 3: AI Gateway
- AIProvider interface
- provider adapters
- capability registry
- health scoring
- circuit breaker
- latency/cost metrics

Phase 4: production operations
- structured logging
- metrics
- tracing
- security hardening
- load testing

Phase 5: Java 21 modular monolith
- Spring Boot
- domain modules
- ports and adapters
- PostgreSQL
- Redis
- resilience
- Testcontainers

Phase 6: event-driven scale
- Kafka
- independent workers
- event contracts
- replay and idempotency

Phase 7: AI engineering
- RAG
- MCP tools
- agent orchestration
- evaluation
- guardrails

## Technology target

| Concern | Target |
|---|---|
| Runtime | Java 21 |
| Framework | Spring Boot 4.x |
| Database | PostgreSQL |
| Cache/locks | Redis/Valkey |
| Messaging | Kafka when justified |
| AI | Groq, Gemini, OpenAI, Hugging Face, Ollama |
| Resilience | Resilience4j / platform-native controls |
| Observability | Actuator + Micrometer + OpenTelemetry |
| Testing | JUnit 5 + Mockito + Testcontainers + WireMock |
| Security | Spring Security + OAuth 2.1 |
| Deployment | Docker + Render initially |
| Orchestration | Kubernetes later, only when justified |

Spring Boot 4.1.1 is currently the stable release and supports Java 21. Java 21 also enables virtual threads when they are appropriate for the workload. citeturn0search0turn0search2turn0search5

## Final architecture goal

Browser / REST / MCP
-> API Gateway and Security
-> Java 21 Spring Boot Modular Monolith
-> PostgreSQL + Redis/Valkey
-> Workers
-> Search + Pricing + AI Gateway
-> Groq / Gemini / OpenAI / Hugging Face / Ollama
-> Observability

The Python implementation remains the reference implementation during migration. Microservices are extracted only after module boundaries, traffic patterns, ownership and failure-isolation requirements justify the split.
