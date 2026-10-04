# Variants: original agent, RAG app, plain app (why they differ)
Measured from the code on 2026-10-01.

| | Original (this repo root) | `apps/price-agent-rag` | `apps/price-agent-plain` |
|---|---|---|---|
| Where answers come from | Claude with the web search tool, live | Passages retrieved from a knowledge base you ingest (SQLite FTS5 BM25, optional vectors); LLM optional | Prices in a database fed by a collector, CSV, admins and community reports |
| Paid key | Anthropic (required) | none | none |
| Python size | 1,319 lines in 10 modules, 301 test lines (16 tests) | 548 lines in 9 modules, 146 test lines (10 tests) | Node API 8 tests, Python collector 7, Java collector 22 |
| Python dependencies | fastapi, uvicorn, anthropic, pydantic, mcp | fastapi, uvicorn, pydantic | (Node: express; Java: Spring Boot) |
| API surface | `/api/jobs`, `/api/v1/compare`, `/api/history`, `/api/locate`, account delete, admin stats, OAuth, `/mcp` | `/api/ask`, `/api/search`, `/api/ingest/{text,url,rss,prices}`, `/api/documents` | `/api/compare`, `/history`, `/offers`, `/ingest`, `/products`, `/stores` |

## Why prices differ between the original and the RAG app
- **The original** asks Claude to find each store's page, read the price and compute an effective price (price minus verified instant discounts). Prices are fresh but model-dependent and costly per search.
- **The RAG app does not look prices up.** `POST /api/ingest/prices` turns rows **you** supply into text documents, and `/api/ask` quotes them with citations. So a price is exactly as current as the last ingest, and there is **no effective-price rule, ranking or best-deal logic**. Asking "which is cheapest?" returns passages (or a model's reading of them), not a computed answer.
- The plain app is the one that computes effective price deterministically (price minus a stated instant discount), flags offers older than 7 days, and refuses to rank mixed currencies.

## What the RAG app does not have (the original does)
OAuth and MCP; background jobs (RAG answers are synchronous, so a slow local model can time out clients); region-aware store discovery; price history; location lookup; cost tracking and admin stats; the evals harness; fail-fast production config checks (RAG has the env-file loader only); the long documentation set.

## What the RAG app adds
An ingestion pipeline (text, price rows, RSS/Atom, web pages with SSRF protection and robots.txt), chunking, hybrid retrieval with Reciprocal Rank Fusion, citation validation and extractive fallbacks, and no paid dependency.

## Convergence options
1. Keep the three separate (simplest, current state).
2. Use RAG retrieval inside the original to ground the reviews/insights step.
3. Port the original's async job queue and the plain app's effective-price rule into the RAG app.
