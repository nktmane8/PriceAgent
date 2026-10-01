# Engineering process

## Principles
1. **Small, reversible changes** over big rewrites. 2. **Tests and evals decide quality**, not opinion. 3. **Cost and security are features**: every change states its impact. 4. **Honesty over polish**: limits stay documented.

## Workflow
1. **Pick** an item from `docs/ROADMAP.md` (top of section 3 first). Open an issue using the template (problem, acceptance criteria, cost/security impact).
2. **Branch** from `main` (`feature/<short-name>`); keep it under about 400 changed lines.
3. **Build with tests**: logic gets an offline test; model-facing changes also get an eval case.
4. **Open a PR** using the template. CI (`ci.yml`) must be green. Self-review with the checklist below if you work alone.
5. **Merge** (squash). Render deploys from `main`.
6. **Release**: bump version in `CHANGELOG.md` (semver: breaking = major, feature = minor, fix = patch), tag `vX.Y.Z`.
7. **After release**: watch `/healthz` and `/api/admin/stats` for an hour; roll back from the Render dashboard if errors or cost spike.

## Definition of Ready
Acceptance criteria written; blocker named; size S/M/L; cost and security impact noted.

## Definition of Done
- [ ] Tests added or updated and passing (`python -m pytest -q tests`)
- [ ] No secrets in code, logs or fixtures
- [ ] Docs updated (README, API, ROADMAP status, CHANGELOG)
- [ ] Cost impact stated if searches, tokens or calls per request change
- [ ] Security checklist done if auth, input handling or rendering changed
- [ ] If a prompt changed: eval run before and after, pass rate not lower

## Test strategy
| Level | What | When | Cost |
|---|---|---|---|
| Unit and integration | `tests/` with the agent faked | Every push (CI) | Free |
| Invariant evals | `evals/checks.py` on real results | Weekly + before prompt or model changes | Real searches |
| Manual smoke | Search 3 products, open links, try OAuth sign-in, delete a test account | Before each release | Small |

## Prompts are code
Prompts in `agent.py` change behaviour as much as code. Change them in their own PR, run the evals, and paste before/after pass rates in the PR.

## Security checklist (auth, input, output)
Inputs validated and length-limited; secrets hashed or from env; output escaped (`textContent`, HTML-escaped pages); redirects exact-match; rate limits on new endpoints; new dependency reviewed; error messages leak nothing. Anything touching OAuth gets a second reviewer where possible.

## Decisions
Architecture decisions are written as short ADRs in `docs/adr/` (template included). Change a decision by adding a new ADR that supersedes the old one.

## Dependencies and housekeeping
Dependabot proposes weekly updates. Pin `mcp<2` until migrated (SDK v2 renamed its API). Review the Anthropic search price and model names monthly (they change).

## Incidents
1. Stop the bleeding (lower `RATE_LIMIT`, set `MAX_SEARCHES` low, or suspend the service). 2. Check `/api/admin/stats` and logs. 3. Fix or roll back. 4. Write a short postmortem (what happened, impact, cause, fix, prevention) in the PR that fixes it.

## Metrics to watch
Cache hit rate, average agent seconds, error rate and top errors, searches per caller type, estimated search cost, eval pass rate.

## Roles
Solo today: author = reviewer, so the checklists are mandatory. With contributors, require one other approval for auth and prompt changes.
