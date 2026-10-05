# ADR-003: Redis Caching Layer (V3)

**Status:** Proposed for Java V3 (after PostgreSQL is stable)

## Decision

Introduce Redis (or Valkey) for caching, distributed locks, and rate limiting.

## What Goes in Redis

### 1. Comparison Results Cache (Hot Path)
```
Key: comparison:{product_hash}:{country}
TTL: 24 hours
Value: { results: [...], explanation: "...", usage: {...} }

Hit rate target: 40-60% (same products searched multiple times)
```

### 2. User Rate Limit Counters
```
Key: ratelimit:api_key:{key}:day
TTL: 1 day
Value: number of requests
```

### 3. Distributed Locks (Job Processing)
```
Key: job:lock:{job_id}
TTL: 30 seconds (prevents concurrent processing)
Value: worker_id
```

### 4. Short-Lived State (OAuth, Sessions)
```
Key: oauth:state:{state_token}
TTL: 10 minutes
Value: { redirect_uri, pkce_challenge, ... }

Key: session:{session_id}
TTL: 24 hours
Value: { user_id, roles, ... }
```

## What Does NOT Go in Redis

❌ **Persistent data.** Use PostgreSQL instead (users, jobs, pricing history).
❌ **Large objects.** Redis is in-memory; keep values < 1 MB.
❌ **Complex queries.** Use PostgreSQL for filtering and aggregation.
❌ **Audit trails.** PostgreSQL for historical records.

## Architecture

```
Client Request
    ↓
Spring Cache (@Cacheable)
    ↓
Redis (Lettuce client)
    ↓
PostgreSQL (on cache miss)
```

## Implementation (Spring)

```java
@Service
@EnableCaching
public class ComparisonService {
    
    @Cacheable(
        value = "comparisons",
        key = "#productHash + ':' + #country",
        cacheManager = "redisCacheManager",
        unless = "#result == null"
    )
    public ComparisonResult getComparison(String productHash, String country) {
        return openaiClient.search(productHash, country);
    }
    
    @CachePut(value = "comparisons", key = "#productHash + ':' + #country")
    public ComparisonResult updateComparison(String productHash, String country, ComparisonResult result) {
        return result;
    }
    
    @CacheEvict(value = "comparisons", key = "#productHash + ':' + #country")
    public void invalidateComparison(String productHash, String country) {}
}

// Config
@Configuration
public class CacheConfig {
    @Bean
    public RedisCacheManager cacheManager(LettuceConnectionFactory factory) {
        return RedisCacheManager.create(factory);
    }
}
```

## Rate Limiting (Resilience4j + Redis)

```java
@Service
public class RateLimitService {
    private final RedisTemplate<String, Integer> redisTemplate;
    
    public void checkLimit(String apiKey) {
        String key = "ratelimit:" + apiKey + ":" + LocalDate.now();
        Integer count = redisTemplate.opsForValue().get(key);
        
        if (count != null && count >= 100) { // 100 requests per day
            throw new RateLimitExceededException();
        }
        
        redisTemplate.opsForValue().increment(key);
        redisTemplate.expire(key, 24, TimeUnit.HOURS);
    }
}
```

## Scaling Considerations

| Scenario | Solution |
|----------|----------|
| Cache grows to 10 GB | Eviction policy (LRU), separate Redis cluster |
| Single Redis is bottleneck | Redis Cluster or Sentinel |
| Cache is not reused | Shorter TTL, different partition key |

## When Redis is NOT Needed

- **No repeated queries.** Every user searches for unique products → cache hit rate < 5%.
- **Data is always fresh.** Prices change every hour → 24-hour TTL is too long.
- **Latency is acceptable.** Waiting 200ms for PostgreSQL is fine.
- **Cost matters.** Redis instance costs money; in-memory caching might not ROI.

## Interview Questions

- "How would you design a cache key for price comparisons?"
- "What's the difference between `@Cacheable` and `@CachePut`?"
- "What happens if Redis goes down?"
- "How would you cache OpenAI results without hallucinating stale data?"
- "Design a rate limiting system using Redis."

