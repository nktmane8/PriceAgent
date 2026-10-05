# Configuration: environments, variables, global constants

## Environments
| `APP_ENV` | File loaded | Purpose | Strictness |
|---|---|---|---|
| `development` (default) | `env/.env.development` | Your laptop: cheap and loose | Warnings only |
| `test` | `env/.env.test` | Automated tests (fake agent) | Silent |
| `staging` | `env/.env.staging` (copy of `.example`) or host dashboard | Pre-production rehearsal | **Fails at start-up on bad config** |
| `production` | `env/.env.production` (copy of `.example`) or host dashboard | Real users | **Fails at start-up on bad config** |

Precedence: real environment variable > `.env` > `env/.env.<APP_ENV>`. Files: `KEY=VALUE`, comments on their own lines. **Secrets never go in committed files**; `.gitignore` excludes `.env`, `env/.env.local`, `env/.env.staging`, `env/.env.production`. On Render set secrets and `APP_ENV=production` in the dashboard (`render.yaml` sets `APP_ENV`).
Switch environment: `APP_ENV=staging uvicorn main:app`.

## Variables
| Variable | Secret | Default | dev | test | staging (example) | production (example) |
|---|---|---|---|---|---|---|
| `APP_ENV` | no | development | development | test | staging | production |
| `LOG_LEVEL` | no | INFO | DEBUG | WARNING | INFO | INFO |
| `OPENAI_API_KEY` | **yes** | none (required) | shell/.env | not needed | dashboard | dashboard |
| `MODEL` | no | gpt-5.6-sol | same | same | same | same |
| `MAX_SEARCHES` | no | 15 | 5 | 1 | 8 | 15 |
| `MAX_INSIGHT_SEARCHES` | no | 10 | 4 | 1 | 6 | 10 |
| `MAX_PAUSE_LOOPS` | no | 4 | default | default | default | default |
| `RATE_LIMIT` (web, per IP/h) | no | 5 | 50 | 1000 | 20 | 5 |
| `USER_RATE_LIMIT` (OAuth user/h) | no | 30 | 100 | default | default | 30 |
| `KEY_RATE_LIMIT` (API key/h) | no | 60 | 200 | default | default | 60 |
| `LOCATE_LIMIT` | no | 20 | default | default | default | default |
| `CACHE_TTL_SECONDS` | no | 1800 | 1800 | default | default | 1800 |
| `WORKERS` (threads) | no | 4 | 2 | 2 | 2 | 4 |
| `JOB_WAIT_SECONDS` | no | 50 | 50 | 5 | default | 50 |
| `DATABASE_PATH` | no | data/price-agent.db | data/dev.db | temp file (tests) | /var/data/...-staging.db | /var/data/price-agent.db |
| `PUBLIC_URL` | no | http://127.0.0.1:8000 | same | same | https URL | https URL (OAuth issuer) |
| `NOMINATIM_CONTACT` | no | unset | dev@example.com | unset | your email | your email |
| `API_KEYS` | **yes** | empty | optional | testkey (fake) | dashboard, 20+ chars | dashboard, 20+ chars |
| `ADMIN_KEY` | **yes** | empty | optional | adm (fake) | dashboard, 20+ chars | dashboard, 20+ chars |
| `EXTRA_ORIGINS` | no | empty | empty | empty | as needed | as needed |
| `PORT` | no | set by host | n/a | n/a | host | host |

## Start-up checks (`config.problems()`)
Always: missing `OPENAI_API_KEY`. Staging/production also: `PUBLIC_URL` not https; `DATABASE_PATH` not absolute; `NOMINATIM_CONTACT` unset; `API_KEYS` or `ADMIN_KEY` shorter than 20 characters. They stop the app there; elsewhere they log warnings.

## Global constants (`constants.py`)
Not environment-specific; change only with a code review.
| Group | Contents |
|---|---|
| Jobs | statuses (`queued/running/done/error`), `ACTIVE`, `FINISHED`, kinds (`prices`, `insights`) |
| Validation | product 3-120 chars, country/city 2-60, max 8 preferred sites, `PLACE_RE`, `DOMAIN_RE` |
| Time windows | hour, login window 15 min, purge every 10 min, job retention 7 days, usage 1 day, history shown 90 days and kept 180 |
| OAuth | scope `prices:read`, access 1 h, refresh 30 d, code 10 min, auth request 15 min, login/token/register limits, password minimum 10 |
| Output caps | 12 results, 8 offers, 10 reviews, 5 alternatives, store and review source types |
| Cost | `SEARCH_COST_USD = 0.01` (verify against current pricing) |
