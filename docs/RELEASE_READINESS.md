# PriceAgent Release Readiness

Last reviewed: 2026-10-05

## Objective

Reach a stable Python release candidate before transferring the application to Java 21. The Python application remains the behavioral reference during migration.

## P0 — must pass before Java

- [x] Web UI loads.
- [x] OAuth browser login uses Authorization Code + PKCE S256.
- [x] /api/v1/me validates the logged-in user.
- [x] Authenticated users can submit and poll price comparisons.
- [x] Job access is scoped to the authenticated user.
- [x] MCP endpoint requires OAuth.
- [x] MCP protected-resource discovery is implemented.
- [x] MCP resource/audience binding is implemented.
- [x] Provider fallback and controlled failures are implemented.
- [x] PostgreSQL backend is implemented.
- [x] Redis/Valkey + RQ worker integration is implemented.
- [x] Render Blueprint defines web, database, Key Value and worker.
- [ ] Provision Postgres in the actual Render workspace.
- [ ] Provision Valkey/Key Value in the actual Render workspace.
- [ ] Provision and run the dedicated worker.
- [ ] Verify create-job -> queue -> worker -> PostgreSQL -> poll end-to-end.
- [ ] Verify API restart does not lose jobs.
- [ ] Verify worker restart/retry behavior.
- [ ] Verify two API instances share jobs and rate limits.
- [ ] Run a real production comparison and manually validate representative prices.
- [ ] Run a real external MCP-client OAuth connection.
- [ ] Complete MCP interoperability/conformance tests.
- [ ] Complete backup and restore drill.
- [ ] Complete load-test baseline.
- [ ] Complete external OAuth/MCP security review.
- [ ] Freeze REST/OpenAPI and MCP contracts.

## P1 — recommended before Java

- [ ] Email verification.
- [ ] Password reset.
- [ ] Account/profile page.
- [ ] OAuth client registration/revocation administration.
- [ ] Client metadata/CIMD support with SSRF protections.
- [ ] Structured request/job/provider logs.
- [ ] Queue/provider/database dashboards and alerts.
- [ ] 30–50 verified evaluation cases.
- [ ] Store coverage report.
- [ ] Final privacy/terms review.

## Stable user journey

Browser -> OAuth login -> /api/v1/me -> product search -> durable job -> worker -> store/search providers -> AI gateway -> validated result -> PostgreSQL -> polling -> best deal/history.

MCP follows: MCP client -> 401 + protected-resource metadata -> authorization server metadata -> OAuth + PKCE + resource indicator -> bearer token -> /mcp -> authenticated MCP tool -> caller-owned result.

## Java handoff

Start Java only when every P0 checkbox is green.

Before migration freeze:

1. REST/OpenAPI contract.
2. OAuth behavior and security invariants.
3. MCP tool names, schemas and authorization behavior.
4. Job state machine and idempotency rules.
5. PostgreSQL data ownership.
6. Valkey queue/cache/lock semantics.
7. Provider fallback/error taxonomy.
8. Representative evaluation fixtures.
9. Observability requirements.
10. Security and privacy requirements.

Java should first be a compatibility implementation of the stable Python behavior. Kafka, Kubernetes, microservices and advanced agent orchestration are later optimization/scale phases, not prerequisites for the migration.