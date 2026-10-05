# ADR-002: PostgreSQL over SQLite (Production Requirement)

**Status:** Proposed for Java V2

## Decision

Migrate from SQLite to PostgreSQL for the production Java platform.

## Rationale

### SQLite (V1) Strengths
- ✅ Embedded, single file, no setup
- ✅ Perfect for prototypes
- ✅ No network latency
- ✅ Suitable for <100 concurrent users

### SQLite (V1) Weaknesses for Production
- ❌ **Concurrent writes lock the entire database.** Only one writer at a time.
- ❌ **Limited connection pooling.** Designed for single-process access.
- ❌ **No replication.** Single file = single point of failure.
- ❌ **No distributed transactions.** Can't coordinate with other systems.
- ❌ **WAL mode has overhead.** Write-Ahead Logging mitigates some issues but adds complexity.
- ❌ **Scaling ceiling.** Can't exceed the instance's local storage.

### PostgreSQL (V2) Advantages
- ✅ **MVCC (Multi-Version Concurrency Control).** Readers don't block writers.
- ✅ **Connection pooling.** Hundreds of concurrent connections.
- ✅ **Replication.** Primary-replica, standby, failover.
- ✅ **Advanced indexing.** B-tree, BRIN, GiST, GIN, Hash.
- ✅ **Full ACID transactions.** Serializable isolation level available.
- ✅ **JSON support.** Native `JSONB` for semi-structured data (e.g., job results).
- ✅ **Extensions.** UUID, JSON, Full-text search, etc.

## Database Schema (V2 Draft)

```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    oauth_subject TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE jobs (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_query TEXT NOT NULL,
    country TEXT NOT NULL,
    status TEXT NOT NULL, -- 'pending', 'running', 'completed', 'failed'
    result JSONB, -- { results: [...], explanation: "...", usage: {...} }
    error TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX ON (user_id, created_at DESC),
    INDEX ON (status)
);

CREATE TABLE comparison_cache (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    product_query_hash TEXT NOT NULL,
    country TEXT NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    UNIQUE(product_query_hash, country),
    INDEX ON (expires_at)
);

CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Connection Pooling (HikariCP in Spring Boot)

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/priceagent
    username: ${DATABASE_USER}
    password: ${DATABASE_PASSWORD}
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      connection-timeout: 30000
      idle-timeout: 600000
      max-lifetime: 1800000
```

## Transaction Boundaries

```java
@Service
public class ComparisonService {
    @Transactional(isolation = Isolation.REPEATABLE_READ)
    public Job startComparison(String productQuery, String country, User user) {
        // 1. Check cache (read-only)
        var cached = cacheRepository.findByQueryAndCountry(productQuery, country);
        if (cached != null && !cached.isExpired()) {
            return createJobFromCache(cached, user);
        }
        
        // 2. Create job record (write)
        var job = new Job(productQuery, country, user);
        return jobRepository.save(job); // Marks status as 'pending'
    }
    
    @Transactional(isolation = Isolation.SERIALIZABLE)
    public void completeJob(Long jobId, String result) {
        // Ensure job isn't already completed (serializable prevents race)
        var job = jobRepository.findById(jobId).orElseThrow();
        job.setStatus("completed");
        job.setResult(result);
        job.setCompletedAt(Instant.now());
        jobRepository.save(job);
    }
}
```

## Indexing Strategy

```sql
-- Access patterns:
-- 1. Fetch user's recent jobs
CREATE INDEX idx_jobs_user_created ON jobs(user_id, created_at DESC);

-- 2. Poll for pending jobs
CREATE INDEX idx_jobs_status_created ON jobs(status, created_at);

-- 3. Cache lookup
CREATE UNIQUE INDEX idx_cache_query_country 
ON comparison_cache(product_query_hash, country) 
WHERE expires_at > NOW();

-- 4. Cleanup expired cache
CREATE INDEX idx_cache_expires ON comparison_cache(expires_at);
```

## Scaling Considerations

| Scenario | Solution |
|----------|----------|
| Read-heavy (many users polling) | Replica with read-only endpoint |
| Write-heavy (many jobs created) | Sharding by user_id or country |
| Large result sets | Archive old jobs, JSON compression |
| Connection exhaustion | Connection pooling, pgBouncer |

## Deployment

- **Local:** `docker run postgres:16` in docker-compose.yml
- **Staging:** Render PostgreSQL (paid tier, ~$15/month)
- **Production:** AWS RDS, GCP Cloud SQL, or managed PostgreSQL

## Migration from SQLite

```python
# Python migration script (one-time)
import sqlite3
import psycopg2

# Read from SQLite
sqlite_conn = sqlite3.connect('data.db')
sqlite_cur = sqlite_conn.cursor()

# Write to PostgreSQL
pg_conn = psycopg2.connect(...)
pg_cur = pg_conn.cursor()

# Copy tables
for row in sqlite_cur.execute("SELECT * FROM users"):
    pg_cur.execute("INSERT INTO users VALUES (%s, %s, ...)", row)

pg_conn.commit()
```

## Consequences

- **More to learn.** Transactions, indexing, query planning.
- **More to operate.** Backups, monitoring, scaling.
- **More to pay.** Free tier is limited; production PostgreSQL costs money.
- **Better scaling.** Horizontal read replicas, connection pooling.

## Interview Questions

- "Why PostgreSQL over SQLite for production?"
- "Explain MVCC and why it matters for concurrent writes."
- "How would you design indexes for the jobs table?"
- "What isolation level would you use for the comparison service?"
- "How would you scale to 10 million daily comparisons?"

