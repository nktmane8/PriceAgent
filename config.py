"""All settings come from environment variables (never hardcode secrets)."""
import os


def _int(name, default):
    return int(os.environ.get(name, default))


MODEL = os.environ.get("MODEL", "claude-sonnet-5-5")
MAX_SEARCHES = _int("MAX_SEARCHES", 15)          # web searches per comparison
MAX_PAUSE_LOOPS = 4                              # pause_turn continuation rounds
RATE_LIMIT = _int("RATE_LIMIT", 5)               # web users: comparisons per IP per hour
USER_RATE_LIMIT = _int("USER_RATE_LIMIT", 30)    # OAuth users: per user per hour
KEY_RATE_LIMIT = _int("KEY_RATE_LIMIT", 60)      # API keys: per key per hour
LOCATE_LIMIT = _int("LOCATE_LIMIT", 20)          # location lookups per IP per hour
CACHE_TTL = _int("CACHE_TTL_SECONDS", 1800)      # 30 minutes
WORKERS = _int("WORKERS", 4)                     # background threads running the agent
JOB_WAIT = _int("JOB_WAIT_SECONDS", 50)          # how long sync/MCP calls wait before returning a job id
DB_PATH = os.environ.get("DATABASE_PATH", "data/price-agent.db")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEYS = [k.strip() for k in os.environ.get("API_KEYS", "").split(",") if k.strip()]
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
NOMINATIM_CONTACT = os.environ.get("NOMINATIM_CONTACT", "set-NOMINATIM_CONTACT")
EXTRA_ORIGINS = [o for o in os.environ.get("EXTRA_ORIGINS", "").split(",") if o]
ACCESS_TTL, REFRESH_TTL = 3600, 30 * 86400       # OAuth token lifetimes (seconds)
CODE_TTL, AUTHREQ_TTL = 600, 900
SCOPE = "prices:read"
