# Interview Questions by Level

Generated from PriceAgent implementation.

## L4-L5: Senior Engineer

### Database Design
**Q:** You're moving PriceAgent from SQLite to PostgreSQL. Explain the trade-offs in choice of isolation level for the comparison service.

**A:** 
- REPEATABLE_READ: Prevents phantom reads, allows non-repeatable reads. Good for reads with some writes.
- SERIALIZABLE: Highest isolation, all transactions are serialized. Blocks on conflicts.
- For comparisons (mostly reads), REPEATABLE_READ is sufficient. For completing a job (write-heavy), SERIALIZABLE prevents race conditions.

### REST API Design
**Q:** Design the `/api/v1/compare` endpoint. What should it accept? What should it return? How would you version it?

**A:**
- Accept: { productQuery, country, optional: userId }
- Return: HTTP 202 { jobId, status='pending' }
- Versioning: /v1/, /v2/ if breaking changes
- Future: /v3/ if we add filters or new fields

### Caching Strategy
**Q:** PriceAgent's comparison result cache is 24 hours. Why that TTL? What happens at 48 hours?

**A:**
- 24h is a trade-off: prices change daily, but caching 24h covers most repeat queries.
- At 48h, stale prices are a problem. At 1h, cache hit rate drops.
- If prices change every 6h, use 6h TTL.
- If prices change every week, use 7d TTL.
- Verify with metrics: cache hit rate vs. price staleness.

## L6: Staff Engineer

### Distributed Systems
**Q:** Design the Kafka architecture for async job processing. How do you ensure exactly-once semantics?

**A:**
- Partitions: user_id % 10 (ordering per user)
- Consumer group: comparison-group (3 consumers)
- Offset management: auto-commit disabled, manual commit after job completion
- Idempotency: check if job is already completed before processing
- Failure: if consumer crashes, offset not committed, message replayed
- Dead-letter: if > 3 retries, send to dlq-comparison-jobs

### System Design at Scale
**Q:** PriceAgent gets 10x traffic. Where's the bottleneck? How would you fix it?

**A:**
- **First bottleneck:** OpenAI rate limit (429). Fix: queue jobs, pace requests.
- **Second bottleneck:** Database connections. Fix: HikariCP pooling, read replicas.
- **Third bottleneck:** Redis memory. Fix: eviction policy (LRU), separate cluster.
- **Fourth bottleneck:** Kafka brokers. Fix: Kafka cluster with 3+ brokers.
- Measure each: latency percentiles, error rates, resource usage.

### Failure Mode Analysis
**Q:** What happens if Redis goes down for 1 hour? What's the impact?

**A:**
- **Immediate:** Cache misses spike. All comparisons hit OpenAI.
- **5 min:** OpenAI rate limit kicks in. New comparisons queue.
- **15 min:** Queue grows, SLA breach if > 5 min latency.
- **1 hour:** Some users abandon, retry later.
- **Fix:** Distributed Redis (Sentinel, Cluster). Graceful degradation (serve stale cache if Redis is down).

### Trade-off Analysis
**Q:** Why Kafka instead of RabbitMQ for the async jobs?

**A:**
- **Kafka:** Partitions (ordered per partition), log-based (can replay), large throughput, scales well.
- **RabbitMQ:** Queues (fast deletes), lower latency, easier to reason about.
- **Decision:** Kafka because we need ordering per user and potential replay for debugging.

## L7: Principal Engineer

### Architecture Evolution
**Q:** Walk me through the evolution of PriceAgent from V1 (Python) to V3 (Java + Kafka).

**A:** [See MIGRATION_STRATEGY.md]

### Organizational Impact
**Q:** How would you scale PriceAgent from a solo project to a 10-person team?

**A:**
- **Team structure:** API team (2), Data team (2), AI team (3), DevOps (1), PM (1), QA (1)
- **Service boundaries:** API service, AI service, Store scraper service
- **Ownership:** Each team owns one service, API via contracts
- **Decision-making:** ADRs per team, reviewed by architecture council
- **Career growth:** Senior on each team, staff engineer bridging teams

### Risk Assessment
**Q:** What are the top 3 risks in moving from Render (SQLite) to Kubernetes (PostgreSQL)?

**A:**
1. **Data migration risk:** Corrupt data, lost transactions, slow migration window
   - Fix: Test migration on staging, backup strategy, rollback plan
2. **Operational complexity:** More failure modes, harder debugging, requires expertise
   - Fix: Runbooks, chaos testing, monitoring alerts
3. **Cost escalation:** Kubernetes, PostgreSQL, Kafka all cost money
   - Fix: Measure cost per request, set budgets, optimize as you grow

### Cost Optimization
**Q:** Reduce PriceAgent's monthly AWS bill by 50% without sacrificing SLA.

**A:**
- **Compute:** Use spot instances (AWS Spot), 3x cheaper but can terminate
- **Database:** Reserved instances (1-year discount), read replicas only where needed
- **OpenAI:** Cache more aggressively (48h TTL), A/B test cheaper models (gpt-4o-mini)
- **Storage:** Compress job history, archive to S3, delete > 1 year

