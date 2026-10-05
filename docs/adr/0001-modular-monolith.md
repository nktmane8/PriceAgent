# ADR-001: Modular Monolith over Microservices (Java V2)

**Status:** Proposed for Java migration (V2)

## Decision

Start with a **modular monolith** in Java 21 + Spring Boot. Do NOT extract microservices initially.

## Rationale

### Why Monolith First

1. **Operational simplicity.** One deployed artifact, one database, one set of secrets.
2. **Easier refactoring.** Move code between modules without distributed system complexity.
3. **No distribution tax.** No network latency, no partial failures, no eventual consistency.
4. **Feature velocity.** Ship features faster without service coordination.

### When We'd Extract

Only after the monolith demonstrates **clear boundaries** AND **scaling pressure** on a specific boundary:

- **Boundary 1: AI Orchestrator** (if OpenAI calls become a bottleneck)
  - Today: OpenAI is called synchronously for each comparison.
  - Future: Move AI to async workers, decouple from REST latency.

- **Boundary 2: Job Processor** (if background jobs become a bottleneck)
  - Today: Jobs are persisted but processed synchronously.
  - Future: Kafka consumer group for distributed job processing.

- **Boundary 3: Store Scrapers** (if search becomes a bottleneck)
  - Today: OpenAI web_search is called per comparison.
  - Future: Cache store data, run periodic crawlers.

## Architecture (Monolith)

```
java-platform/
├── src/main/java/com/priceagent/
│   ├── api/
│   │   ├── ComparisonController.java
│   │   ├── OAuthController.java
│   │   └── HealthController.java
│   ├── application/
│   │   ├── ComparisonService.java
│   │   ├── JobService.java
│   │   └── OAuthService.java
│   ├── domain/
│   │   ├── Product.java
│   │   ├── Store.java
│   │   ├── Price.java
│   │   ├── Job.java
│   │   └── User.java
│   ├── infrastructure/
│   │   ├── persistence/ (JPA repositories)
│   │   ├── ai/ (OpenAI client)
│   │   ├── cache/ (Redis)
│   │   └── messaging/ (Kafka)
│   ├── security/
│   │   ├── OAuth2Server.java
│   │   ├── JwtTokenProvider.java
│   │   └── SecurityConfig.java
│   └── configuration/
│       ├── ApplicationConfig.java
│       ├── SecurityConfig.java
│       └── OpenAIConfig.java
└── src/test/
    ├── java/com/priceagent/
    │   ├── api/
    │   ├── application/
    │   └── infrastructure/
    └── resources/
        └── application-test.yml
```

## Modules (Within the Monolith)

Each module is independently testable and deployable (in theory), but deployed as one artifact:

1. **API Module**
   - REST endpoints
   - Request validation
   - Response formatting

2. **Application Module**
   - Business logic
   - Orchestration
   - Transaction boundaries

3. **Domain Module**
   - Product, Price, Store, Job entities
   - Domain logic (e.g., product matching)
   - No database dependencies

4. **Infrastructure Module**
   - JPA repositories
   - OpenAI client
   - Redis client
   - Kafka producer

5. **Security Module**
   - OAuth2 server
   - JWT handling
   - Permission checks

## Transition Path to Services (If Needed)

```
Stage 1: Monolith (V2)
  All modules in one JAR

Stage 2: Modular Monolith (V3)
  Each module is independently deployable in theory
  Still one JAR in practice
  Clear boundaries, no circular dependencies

Stage 3: Distributed Monolith (V4)
  Add Kafka for cross-module communication
  Keep single database
  Async processing within modules

Stage 4: Service Extraction (V5+)
  Only extract boundaries where:
    - Clear ownership
    - Different scaling requirements
    - Different deployment frequency
    - True data isolation
```

## Benefits

- **Simple deployment:** One JAR, one health check, one version.
- **Simple testing:** No service mocking, no contract tests.
- **Simple debugging:** Stack traces include the whole system.
- **Easy refactoring:** Rename classes, move logic, no service contracts to break.
- **Measured scaling:** Only extract services after proving the boundary is real.

## Risks

- **Single point of failure:** One pod going down takes everything offline.
  - Mitigation: Kubernetes replica sets, readiness probes.

- **Uneven scaling:** Can't scale the AI orchestrator without scaling the web API.
  - Mitigation: Watch metrics; extract AI orchestrator when compute-bound.

- **Shared database.** Tight coupling between API and persistence.
  - Mitigation: Clear repository interfaces, transaction boundaries, later extraction to CQRS if needed.

## Consequences

- **Simpler for next 6 months.** Focus on features, not plumbing.
- **Bounded flexibility.** If the AI orchestrator needs to scale 10x while APIs stay at 1x, we'll extract it.
- **Standard Spring Boot.** Use Spring Data JPA, Spring Security, Spring Kafka. No custom frameworks.

## When We'd Reconsider

- If one module's latency > 50% of the other's → extract
- If one module scales 3x faster than the other → extract
- If one module fails frequently while the other is stable → extract
- If one team owns the code while another owns the service → extract

## Interview Questions

- "Why start with a monolith instead of microservices?"
- "What signals would tell you to extract the AI orchestrator into a separate service?"
- "How would you implement modular boundaries in Spring Boot?"
- "What's the difference between a modular monolith and a service?"
- "When is a monolith NOT the right choice?"

