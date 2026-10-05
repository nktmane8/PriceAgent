# ADR-004: Kafka for Async Job Processing (V3)

**Status:** Proposed for Java V3

## Decision

Use Kafka for decoupling the REST API from long-running AI comparison jobs.

## Today (V2: Synchronous)

```
POST /api/v1/compare
  ↓
1. Create Job record (status='pending')
  ↓
2. Call OpenAI (blocks request)
  ↓
3. Update Job (status='completed')
  ↓
HTTP 200 + job_id
```

**Problem:** If OpenAI takes 30 seconds, the user waits 30 seconds. If OpenAI fails, the request fails.

## Tomorrow (V3: Asynchronous with Kafka)

```
POST /api/v1/compare
  ↓
1. Create Job record (status='pending')
  ↓
2. Publish ComparisonRequested event to Kafka
  ↓
HTTP 202 Accepted + job_id (return immediately)
  ↓
[Kafka consumer in background]
  ↓
3. Call OpenAI
  ↓
4. Update Job (status='completed')
  ↓
[Client polls GET /api/v1/job/{id} to check status]
```

**Benefit:** REST returns in 10ms; OpenAI takes 30s; no blocking.

## Kafka Topic Design

```
Topic: comparison-requests
Partitions: {user_id} % 10 (ensure same user's requests are ordered)
Replication: 3
Retention: 7 days (for replay)

Schema:
{
  "jobId": "uuid",
  "userId": "uuid",
  "productQuery": "iPhone 15 128GB",
  "country": "India",
  "requestedAt": "2026-10-05T10:00:00Z"
}
```

## Implementation

```java
// Producer (REST API)
@RestController
@RequestMapping("/api/v1")
public class ComparisonController {
    private final KafkaTemplate<String, ComparisonRequest> kafkaTemplate;
    private final JobRepository jobRepository;
    
    @PostMapping("/compare")
    public ResponseEntity<JobResponse> compare(
        @RequestBody ComparisonRequest req,
        @AuthenticationPrincipal User user
    ) {
        // 1. Create job record
        var job = new Job(req.productQuery(), req.country(), user);
        job.setStatus("pending");
        job = jobRepository.save(job);
        
        // 2. Publish event (async, doesn't block)
        kafkaTemplate.send(
            "comparison-requests",
            job.getId().toString(),
            new ComparisonEvent(job.getId(), user.getId(), req.productQuery(), req.country())
        );
        
        // 3. Return immediately
        return ResponseEntity.accepted().body(new JobResponse(job.getId(), "pending"));
    }
}

// Consumer (Background Worker)
@Service
public class ComparisonWorker {
    @KafkaListener(topics = "comparison-requests", groupId = "comparison-group")
    public void processComparison(ComparisonEvent event) throws Exception {
        try {
            var job = jobRepository.findById(event.jobId()).orElseThrow();
            job.setStatus("running");
            jobRepository.save(job);
            
            var result = openaiClient.search(event.productQuery(), event.country());
            
            job.setStatus("completed");
            job.setResult(result);
            jobRepository.save(job);
        } catch (Exception e) {
            jobRepository.updateStatus(event.jobId(), "failed", e.getMessage());
            throw e; // Retry (Kafka will re-deliver)
        }
    }
}
```

## Failure Handling

### Scenario 1: Consumer Crashes
```
Kafka offset is NOT committed
→ On restart, the same message is re-processed
→ Job might be completed twice
→ Idempotency required: check if job is already completed before writing
```

### Scenario 2: OpenAI Timeout
```
Exception in consumer
→ Kafka doesn't commit offset
→ Message goes to retry backoff (exponential)
→ After N retries, send to dead-letter queue
```

### Scenario 3: Database Connection Lost
```
Consumer can't update job status
→ Exception, offset not committed
→ Message stays in partition
→ Manual intervention or retry policy
```

## Idempotency (Critical)

```java
@Service
public class ComparisonWorker {
    @KafkaListener(topics = "comparison-requests", groupId = "comparison-group")
    public void processComparison(ComparisonEvent event) throws Exception {
        var job = jobRepository.findById(event.jobId()).orElseThrow();
        
        // Idempotency check: don't re-process completed jobs
        if ("completed".equals(job.getStatus()) || "failed".equals(job.getStatus())) {
            return; // Already processed, skip
        }
        
        // Process normally
        var result = openaiClient.search(event.productQuery(), event.country());
        job.setResult(result);
        job.setStatus("completed");
        jobRepository.save(job);
    }
}
```

## Scaling

| Metric | Threshold | Action |
|--------|-----------|--------|
| Consumer lag > 1 hour | Add replicas | `replicas: 3` |
| Partition latency > 5s | Increase partitions | `partitions: 20` |
| Broker CPU > 80% | Scale broker cluster | Multi-node Kafka |

## Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: comparison-worker
spec:
  replicas: 3 # Scale horizontally
  template:
    spec:
      containers:
      - name: worker
        image: priceagent:latest
        env:
        - name: SPRING_KAFKA_BOOTSTRAP_SERVERS
          value: kafka-broker-0:9092,kafka-broker-1:9092,kafka-broker-2:9092
        - name: KAFKA_CONSUMER_GROUP_ID
          value: comparison-group
```

## Interview Questions

- "Why use Kafka instead of a simpler queue like RabbitMQ?"
- "How do you ensure idempotency in Kafka consumers?"
- "What happens if the consumer crashes before committing an offset?"
- "Design a dead-letter queue for failed comparisons."
- "How would you debug slow consumer lag in production?"

