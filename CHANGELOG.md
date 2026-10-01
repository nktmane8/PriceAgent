# Changelog
## 2.0.0
- Async jobs on a thread pool with in-flight dedupe; SQLite persistence (cache, jobs, rate limits, users, OAuth).
- OAuth 2.1 authorization server (PKCE, dynamic registration, refresh rotation); OAuth-protected remote MCP server at `/mcp`.
- Cost tracking per job, admin stats, purge thread, output validation, test suite.
## 1.x
- Region-aware stores, location fallback, MCP stdio wrapper, API-key endpoint.
