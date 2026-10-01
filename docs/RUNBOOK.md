# Runbook

## Deploy / rollback
Push to GitHub; Render builds from `render.yaml`. Roll back from the Render dashboard. Keep `WORKERS` and a single instance; never run more than one process.

## Backups
The disk holds `/var/data/price-agent.db`. Back up from a Render shell: `sqlite3 /var/data/price-agent.db ".backup '/var/data/backup.db'"` and copy it off-box regularly.

## Cost (check `GET /api/admin/stats`)
Search fees are $10 per 1,000 searches (Anthropic's published price when written; verify), so each uncached comparison costs up to `MAX_SEARCHES x $0.01`, plus tokens (`input_tokens`, `output_tokens` are stored per job; multiply by your model's rates). Cache hits are free. Levers: lower `MAX_SEARCHES`, raise `CACHE_TTL_SECONDS`, lower `RATE_LIMIT`. Set a spend limit in the Anthropic Console.

## Common problems
| Symptom | Check |
|---|---|
| All jobs `error: Server is missing ANTHROPIC_API_KEY` | Env var set on the service |
| Jobs `error: AI service error` | Anthropic status, billing credit, `MODEL` name |
| Data vanished after deploy | Disk not attached or `DATABASE_PATH` not on `/var/data` |
| OAuth redirect shows "invalid redirect" | Client must register the exact callback URL |
| MCP client gets 421/403 | `PUBLIC_URL` must equal the public https URL; add browser origins to `EXTRA_ORIGINS` |
| 401 on /mcp after an hour | Client must use the refresh token; check it stores it |
| Many `429`s | Raise `RATE_LIMIT` / `USER_RATE_LIMIT` deliberately, not blindly |

## Tests
`pip install -r requirements-dev.txt && python -m pytest -q tests` (no network or API key needed; the agent is faked).
