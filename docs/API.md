# API reference
Schema: `GET /openapi.json`. Base URL = `PUBLIC_URL`.

| Method + path | Auth | Purpose |
|---|---|---|
| `POST /api/jobs` | none, 5/h per IP | Start a comparison (web page). 200 if cached, else 202 |
| `GET /api/jobs/{id}` | none (id is secret) | Poll a job |
| `POST /api/v1/compare` | OAuth bearer or `X-API-Key` | Start and wait up to 50 s. 200 result or 202 + job_id |
| `GET /api/v1/jobs/{id}` | same | Poll |
| `POST /mcp` | OAuth bearer | MCP tools `compare_prices`, `get_comparison_result` |
| `POST /api/v1/account/delete` | OAuth bearer | Body `{"password"}`; deletes account, tokens, jobs, usage |
| `GET /api/history?product&country&city` | none, 60/h per IP | Daily lowest effective prices and the lowest ever seen (90 days) |
| `GET /api/locate?lat&lon` | none, 20/h per IP | Coordinates to country + city |
| `GET /api/admin/stats` | `X-Admin-Key` | Jobs, cache hit rate, average agent seconds, top errors, searches and cost by caller type, history rows |
| `GET /healthz` | none | Health check |
| `/oauth/register, authorize, token, revoke`, `/.well-known/*` | see ARCHITECTURE | OAuth server |

Request body: `{"product": "iPhone 15 128GB Black", "country": "India", "city": "Pune", "sites": ["example.com"]}` (`city`, `sites` optional).
Job response: `{"job_id", "status": "queued|running|done|error", "result"?, "cached"?, "error"?}`.
Result: `{product, region, currency, results:[{site, store_type, location, price, effective_price, offers[], in_stock, url}], best_deal, notes}`.
Errors: 401 auth, 422 bad input, 429 rate limit (message has minutes to wait), 404 unknown job.
Partner API keys are read from the comma-separated `API_KEYS` environment variable. Generate a random 20+ character key, replace the old value in `.env` or your host dashboard, restart the service, then send it in `X-API-Key`.

```bash
curl -X POST $URL/api/v1/compare -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"product":"Samsung Galaxy S24 256GB","country":"India","city":"Pune"}'
```
