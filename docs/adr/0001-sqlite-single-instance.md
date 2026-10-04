# ADR 0001: SQLite and a single instance
- Status: accepted
- Date: 2026-10-01
## Context
Need persistence (cache, jobs, OAuth, limits) with zero operations work.
## Decision
SQLite in WAL mode on a persistent disk; in-process thread pool; run exactly one instance.
## Consequences
Simple and cheap; cannot scale out and needs backups. Moving to Postgres + Redis is TODO #5 in the roadmap.
