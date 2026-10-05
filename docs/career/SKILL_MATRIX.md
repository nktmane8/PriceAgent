# Skill Matrix: PriceAgent → Principal Engineer

This document maps each feature of PriceAgent to the engineering skills and interview topics it covers.

## Java Skills

| Skill | Feature | Depth |
|-------|---------|-------|
| **Records** | Job, Product, Price entities | Core |
| **Sealed Classes** | Isolation levels, status enums | Intermediate |
| **Virtual Threads** | Kafka consumers, async handlers | Advanced |
| **Generics** | Repository<T>, Service<T> | Core |
| **Concurrency** | Kafka, Redis, distributed locks | Advanced |
| **Streams** | Data transformation, filtering | Core |
| **Exception Handling** | Resilience4j, custom domain exceptions | Intermediate |

## Spring Boot Skills

| Skill | Feature | Depth |
|-------|---------|-------|
| **Data JPA** | Job, User repositories | Core |
| **Web** | REST controllers, request/response | Core |
| **Security** | OAuth2 server, JWT, PKCE | Advanced |
| **Cloud Config** | Environment variables, profiles | Intermediate |
| **AOP** | Caching (@Cacheable), metrics | Intermediate |
| **Test** | Spring Boot Test, TestContainers | Core |
| **Actuator** | Health checks, metrics endpoints | Intermediate |

## Distributed Systems

| Skill | Feature | Depth |
|-------|---------|-------|
| **Transactions** | PostgreSQL isolation, Spring @Transactional | Intermediate |
| **Eventual Consistency** | Kafka, async jobs, idempotency | Advanced |
| **Idempotency** | Kafka consumer, job processing | Advanced |
| **Distributed Locks** | Redis locks, job processing | Advanced |
| **Replication** | PostgreSQL replicas, failover | Intermediate |
| **Sharding** | Kafka partitions, user_id partitioning | Intermediate |

## Database Skills

| Skill | Feature | Depth |
|-------|---------|-------|
| **Normalization** | Job, User, Product schema design | Core |
| **Indexing** | Query optimization, B-tree, BRIN | Intermediate |
| **Transaction Isolation** | REPEATABLE_READ vs SERIALIZABLE | Intermediate |
| **Connection Pooling** | HikariCP, max-pool-size tuning | Intermediate |
| **Replication** | Primary-replica, standby setup | Intermediate |

## Caching & Performance

| Skill | Feature | Depth |
|-------|---------|-------|
| **Cache Invalidation** | TTL, cache-aside pattern | Intermediate |
| **Cache Warming** | Preload popular products | Intermediate |
| **Distributed Caching** | Redis, multiple instances | Advanced |
| **Rate Limiting** | Token bucket, sliding window | Intermediate |

## Message Queues

| Skill | Feature | Depth |
|-------|---------|-------|
| **Pub-Sub vs Queues** | Decision: why Kafka, not RabbitMQ | Advanced |
| **Partitioning** | Ordering, parallelism | Advanced |
| **Consumer Groups** | Scaling, rebalancing | Intermediate |
| **Offset Management** | Exactly-once semantics | Advanced |
| **Dead-Letter Queues** | Failure handling | Intermediate |

## Resilience & Reliability

| Skill | Feature | Depth |
|-------|---------|-------|
| **Retry** | Exponential backoff, jitter | Intermediate |
| **Circuit Breaker** | Failure detection, recovery | Advanced |
| **Timeout** | Deadline handling, cascading failures | Intermediate |
| **Bulkhead** | Resource isolation, thread pools | Intermediate |
| **Health Checks** | Readiness, liveness probes | Intermediate |

## Security

| Skill | Feature | Depth |
|-------|---------|-------|
| **OAuth2** | Authorization code flow, PKCE | Advanced |
| **JWT** | Token structure, claims, verification | Intermediate |
| **HTTPS/TLS** | Redirect URLs, secure cookies | Core |
| **SSRF Protection** | Input validation, OpenAI URLs | Intermediate |
| **Secret Management** | Environment variables, vault | Core |
| **RBAC** | Scopes, permissions, authorization | Intermediate |

## Observability

| Skill | Feature | Depth |
|-------|---------|-------|
| **Structured Logging** | JSON, correlation IDs | Intermediate |
| **Metrics** | Micrometer, Prometheus | Intermediate |
| **Tracing** | OpenTelemetry, request paths | Advanced |
| **Alerting** | Threshold-based, anomaly detection | Intermediate |
| **Dashboarding** | Grafana, query writing | Intermediate |

## AI / LLM Engineering

| Skill | Feature | Depth |
|-------|---------|-------|
| **Prompt Design** | Versioning, testing, A/B tests | Intermediate |
| **Tool Calling** | Structured outputs, validation | Intermediate |
| **RAG** | Vector search, retrieval | Advanced |
| **Agents** | Orchestration, reasoning loops | Advanced |
| **Cost Control** | Token limits, caching, fallbacks | Intermediate |

## System Design

| Skill | Feature | Depth |
|-------|---------|-------|
| **Requirements** | Functional, non-functional, constraints | Core |
| **Capacity Planning** | Throughput, latency, storage | Intermediate |
| **API Design** | REST, versioning, backwards compatibility | Intermediate |
| **Data Model** | Schema design, normalization, denormalization | Intermediate |
| **Scaling** | Horizontal, vertical, caching, sharding | Advanced |
| **Failure Modes** | SPOF, cascading failures, degradation | Advanced |
| **Trade-offs** | Consistency vs availability, cost vs latency | Advanced |

## Interview Topics Covered

### L4-L5 (Senior Engineer)

- Database design (transactions, indexing, scaling)
- Resilience patterns (retry, circuit breaker, timeout)
- Caching strategies (cache-aside, write-through, invalidation)
- OAuth2 implementation
- REST API design

### L6 (Staff Engineer)

- Distributed systems (eventual consistency, idempotency)
- Kafka architecture (partitioning, consumer groups, failure handling)
- Observability (logging, metrics, tracing)
- System design at scale (10x traffic, bottleneck analysis)
- Trade-off analysis (monolith vs services, PostgreSQL vs DynamoDB)

### L7 (Principal Engineer)

- Architecture evolution (V1 → V7, migration strategy)
- Organizational impact (team structure, service boundaries)
- Cost optimization (AWS/OpenAI spend, infrastructure)
- Risk assessment (security, reliability, operational complexity)
- Technical leadership (decision records, mentoring, learning culture)

## Skill Development Roadmap

### Month 1: Foundations (Weeks 1-4)
- Java 21 basics (records, sealed classes, virtual threads)
- Spring Boot Web, Data, Security
- PostgreSQL fundamentals

### Month 2: Intermediate (Weeks 5-8)
- Distributed systems (transactions, locks, idempotency)
- Kafka basics (partitions, consumer groups)
- Resilience4j patterns

### Month 3: Advanced (Weeks 9-13)
- System design interviews (scale to 10M DAU)
- Observability and debugging
- Cost optimization and trade-offs

### Month 4+: Expert (Weeks 14+)
- Architecture evolution and refactoring
- Multi-team coordination
- Thought leadership (blogs, talks, mentoring)

## Self-Assessment Rubric

For each skill, rate yourself:

- **0**: Never done this
- **1**: Done once, with guidance
- **2**: Done multiple times, comfortable
- **3**: Done many times, can explain to others
- **4**: Expert, can design and optimize, asked in interviews
- **5**: Thought leader, can teach and evolve

Example trajectory for "Kafka":
- Week 1: 0 (never used)
- Week 12 (after Phase 6): 2 (implemented producer/consumer, understand partitions)
- Week 20 (after production use): 3 (can debug consumer lag, know failure modes)
- Week 30+: 4-5 (could architect a Kafka migration for another team)

## Interview Question Generator

For each skill and level, generate questions using this template:

**Skill:** Kafka  
**Level:** Staff  
**Question:** "Design a Kafka architecture for a payment system that processes 1M transactions/day with exactly-once semantics. What are the failure modes?"

**Expected Answer Should Cover:**
- Partitioning strategy (by merchant_id?)
- Producer idempotency (dedup key?)
- Consumer offset management (exactly-once delivery)
- Failure scenarios (broker down, consumer crash, network partition)
- Trade-offs (throughput vs latency, cost vs complexity)

