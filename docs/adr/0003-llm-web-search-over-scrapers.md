# ADR 0003: LLM with web search instead of per-store scrapers
- Status: accepted (revisit for cost, ROADMAP #10)
- Date: 2026-10-01
## Context
Stores differ by region and change layouts; per-site code does not scale.
## Decision
Let the model discover stores and read pages; validate everything it returns (`agent.clean*`).
## Consequences
Works anywhere, but slower, costlier and non-deterministic. Mitigated by caching, dedupe, caps and evals. A cheaper no-AI mode is planned (ROADMAP #10). Provider swapped from Anthropic to OpenAI in v2.6.0 without touching `clean*`, which confirms the validation layer is provider-independent.
