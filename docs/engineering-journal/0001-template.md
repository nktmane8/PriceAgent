# Engineering Journal Entry Template

## Problem Statement

**Title:** [Descriptive title]

**Priority:** P0 | P1 | P2

**Date Identified:** [YYYY-MM-DD]

### Summary
[1-2 sentences: what is the problem?]

---

## Evidence

[Facts, logs, metrics, user reports that prove the problem]

Example:
- Smoke test shows 0 records returned from OpenAI search
- Error log: "model 'gpt-5.6-sol' not found"
- Render env: `MODEL` is set, but value is undefined

---

## Investigation

[What did we try? What did we learn?]

### Hypothesis 1
- **Test:** Curl the OpenAI API directly
- **Result:** Returns 404 (model not found)
- **Conclusion:** Model name is wrong

### Hypothesis 2
- **Test:** Check Render environment variables
- **Result:** `OPENAI_API_KEY` is set, but `MODEL` is empty
- **Conclusion:** `MODEL` env var is not set on Render

---

## Root Cause

[The core issue]

Render environment did not include the `MODEL` variable after the OpenAI migration. The Python app defaults to `config.DEFAULT_MODEL = "gpt-4o"` if `MODEL` is not set, but this default was not declared on Render.

---

## Options

### Option A: Set MODEL on Render
- **Pros:** Quick fix, 2 minutes
- **Cons:** Manual; easy to forget on next deploy
- **Cost:** Free

### Option B: Add validation + error message
- **Pros:** Catches errors early, user sees clear message
- **Cons:** Doesn't fix the root cause
- **Cost:** 30 min of work

### Option C: Redesign config loading
- **Pros:** Robust, handles missing vars gracefully
- **Cons:** More work, need to test all code paths
- **Cost:** 2 hours of work

---

## Decision

**Option A + B:** Set `MODEL=gpt-4o` on Render immediately, then add validation in the config loader.

**Rationale:** Unblock users now (Option A) while making the system more robust (Option B).

---

## Implementation

```python
# config.py - validation
if not os.environ.get("MODEL"):
    raise ConfigurationError(
        "MODEL env var is required. Set it to 'gpt-4o', 'gpt-4-turbo', etc. "
        "Check OpenAI model availability: https://platform.openai.com/docs/models"
    )
```

```yaml
# render.yaml - declare variable
envVars:
  - key: MODEL
    value: gpt-4o
    description: OpenAI model name
    required: true
```

---

## Testing

[How did we verify the fix works?]

1. **Local test:** `OPENAI_API_KEY=sk-test MODEL=gpt-4o python -m pytest tests/test_app.py::test_env_loader_precedence_and_production_checks`
   - ✅ Pass

2. **Smoke test:** `python tools/smoke.py https://priceagent.onrender.com --key <key>`
   - ✅ Returns 3 store records
   - ✅ Status code 200
   - ✅ Response time < 30s

3. **Manual test:** Visit https://priceagent.onrender.com, search for "iPhone 15"
   - ✅ Shows results
   - ✅ No error message

---

## Metrics (Before → After)

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Smoke test pass rate | 0% | 100% | +100pp |
| OpenAI success rate | 0% | 98% | +98pp |
| User-reported failures | 5 | 0 | -5 |

---

## Timeline

| Activity | Duration | Date |
|----------|----------|------|
| Investigation | 15 min | Oct 5, 10:00-10:15 |
| Fix + testing | 20 min | Oct 5, 10:15-10:35 |
| Deployment | 2 min | Oct 5, 10:35-10:37 |
| Validation | 5 min | Oct 5, 10:37-10:42 |
| **Total** | **42 min** | |

---

## Lessons Learned

### What Went Wrong
1. **Manual config for Render.** Migrated code from Anthropic to OpenAI but forgot to update the Render environment.
2. **Missing validation.** Config loader didn't validate required variables until runtime.
3. **No pre-deploy checklist.** Didn't verify Render env before declaring "migration complete."

### What Went Right
1. **Smoke test caught it.** Post-deploy smoke test immediately revealed the failure.
2. **Clear error message.** OpenAI returned a readable 404, not a cryptic error.
3. **Fast recovery.** Single-line fix, 42 minutes from detection to validation.

### Prevention
- [ ] Add config validation to tests
- [ ] Create a "production checklist" in RUNBOOK.md (verify all env vars are set)
- [ ] Automate smoke test in CI after deploy
- [ ] Document all required env vars in README.md with examples

---

## Interview Takeaway

> "Identified a configuration issue in production (MODEL env var not set on Render after OpenAI migration). Investigated methodically, validated the root cause, implemented a 2-part fix (set the var + add validation), and automated testing to prevent recurrence. Recovered in 42 minutes with zero data loss."

**Interviewer note:** This demonstrates debugging skills, system thinking (why did it fail?), and robustness mindset (how do we prevent this?).

---

## Links

- Issue: [GitHub issue #123]
- PR: [GitHub PR #124]
- Related: [docs/ROADMAP.md#11-verify-production-end-to-end]

