# ADR 0003: LLM with web search instead of per-store scrapers
- Status: accepted (revisit for cost, TODO #11)
- Date: 2026-10-01
## Context
Stores differ by region and change layouts; per-site code does not scale.
## Decision
Let the model discover stores and read pages; validate everything it returns (`agent.clean*`).
## Consequences
Works anywhere, but slower, costlier and non-deterministic. Mitigated by caching, dedupe, caps and evals. A cheaper no-AI mode is planned.
