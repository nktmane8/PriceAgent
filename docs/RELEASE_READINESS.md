# PriceAgent Release Readiness

Last reviewed: 2026-10-05

## Objective

Reach a stable Python release candidate before transferring the application to Java 21. The Python application remains the behavioral reference during migration.

## P0 — must pass before Java

- [x] Web UI loads.
- [x] OAuth browser login uses Authorization Code + PKCE S256.
- [x] /api/v1/me validates the logged-in user.
- [x] Authenticated users can submit and poll price comparisons.
- [x] REST job access is scoped to the authenticated principal.
- [x] MCP endpoint requires OAuth.
- [x] MCP protected-resource discovery is implemented.
- [x] MCP resource/audience binding is strict and explicit.
- [x] Provider fallback and controlled failures are implemented.
- [x] Stable machine-readable job error codes are implemented.
- [x] PostgreSQL backend is implemented.
- [x] Redis/Valkey + RQ worker integration is implemented.
- [x] Render Blueprint defines web, database, Key Value and worker.
- [ ] Provision and wire Postgres in the actual Render workspace.
- [ ] Provision and wire persistent Valkey/Key Value in the actual Render workspace.
- [ ] Provision and run the dedicated worker.
- [ ] Verify create-job -> queue -> worker -> PostgreSQL -> poll end-to-end.
- [ ] Verify API restart does not lose jobs.
- [ ] Verify worker restart/retry behavior.
- [ ] Verify two API instances share jobs and rate limits.
- [ ] Run a real production comparison and manually validate representative prices.
- [ ] Run a real external MCP-client OAuth connection.
- [ ] Complete MCP interoperability/conformance tests, including `scripts/mcp_external_smoke.py` against the deployed service.
- [ ] Complete backup and restore drill.
- [ ] Complete load-test baseline.
- [ ] Complete external OAuth/MCP security review.
- [ ] Freeze REST/OpenAPI, OAuth, MCP, job-state, error-code and provider contracts.

## P1 — recommended before Java

- [ ] Email verification.
- [ ] Password reset.
- [ ] Account/profile page.
- [ ] OAuth client registration/revocation administration.
- [ ] Client metadata/CIMD support with SSRF protections.
- [ ] Structured request/job/provider logs.
- [ ] Queue/provider/database dashboards and alerts.
- [x] 30 source-verified evaluation cases are committed; run the live evaluator and promote/adjust ranges as evidence changes.
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

## Contract invariants verified in the reference implementation

- REST OAuth tokens must have resource = `PUBLIC_URL`.
- MCP OAuth tokens must have resource = `PUBLIC_URL/mcp`.
- REST job polling is caller-owned; cross-principal access returns 403.
- Job states are `queued -> running -> done|error`.
- PostgreSQL is durable state; Valkey/RQ is operational queue/lock state.
- Valkey queues use `noeviction`; the production Blueprint uses persistent Journal + Snapshot storage.
- Provider failures are hidden behind stable error codes rather than provider-specific API details.
- Evaluation cases record the expected price band and verification date; live evaluation remains evidence, not a hard-coded truth.

## Remaining external proof

The code-level reference implementation is hardened, but these cannot be honestly marked green until executed against infrastructure: distributed Render web/worker tests, worker-loss recovery, external MCP client, backup/restore, load baseline, security review, and the live evaluation run.
