"""Environment-driven settings.

Precedence (highest first):  real environment variables  >  .env (local, git-ignored)  >  env/.env.<APP_ENV>
APP_ENV is one of: development (default), test, staging, production.
Fixed values shared by all environments are in constants.py. Secrets are NEVER stored in env files."""
import logging
import os
from pathlib import Path

from constants import ACCESS_TTL, AUTHREQ_TTL, CODE_TTL, REFRESH_TTL, SCOPE  # noqa: F401  (re-exported)

ROOT = Path(__file__).resolve().parent


def _load_file(path: Path) -> None:
    """Tiny .env reader: KEY=VALUE lines, # comments on their own line. Never overrides real env vars."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


_load_file(ROOT / ".env")                                   # local overrides (git-ignored)
APP_ENV = os.environ.get("APP_ENV", "development")
_load_file(ROOT / "env" / f".env.{APP_ENV}")                # per-environment defaults


def _int(name, default):
    """Read an integer environment variable with a default."""
    return int(os.environ.get(name, default))


PRODUCTION_LIKE = APP_ENV in ("staging", "production")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
MODEL = os.environ.get("MODEL", "gpt-6-luna")
AI_PROVIDER = os.environ.get("AI_PROVIDER", "auto")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", MODEL if AI_PROVIDER == "openai" else "gpt-6-luna")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
HF_MODEL = os.environ.get("HF_MODEL", "openai/gpt-oss-120b:fastest")
HF_BASE_URL = os.environ.get("HF_BASE_URL", "https://router.huggingface.co/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
MAX_SEARCHES = _int("MAX_SEARCHES", 15)                     # web searches per price comparison
MAX_INSIGHT_SEARCHES = _int("MAX_INSIGHT_SEARCHES", 10)     # searches for reviews + alternatives
MAX_PAUSE_LOOPS = _int("MAX_PAUSE_LOOPS", 4)                # retained for config compatibility; Responses handles tool continuation
RATE_LIMIT = _int("RATE_LIMIT", 5)                          # web users: comparisons per IP per hour
USER_RATE_LIMIT = _int("USER_RATE_LIMIT", 30)               # OAuth users: per user per hour
KEY_RATE_LIMIT = _int("KEY_RATE_LIMIT", 60)                 # API keys: per key per hour
LOCATE_LIMIT = _int("LOCATE_LIMIT", 20)                     # location lookups per IP per hour
CACHE_TTL = _int("CACHE_TTL_SECONDS", 1800)                 # 30 minutes
WORKERS = _int("WORKERS", 4)                                # background threads running the agent
AI_CONCURRENCY = _int("AI_CONCURRENCY", 2)                    # max concurrent OpenAI requests per process
AI_MAX_RETRIES = _int("AI_MAX_RETRIES", 1)                    # explicit provider retry count
AI_MAX_RETRY_DELAY = _int("AI_MAX_RETRY_DELAY_SECONDS", 4)     # bounded retry delay
JOB_WAIT = _int("JOB_WAIT_SECONDS", 50)                     # sync/MCP wait before returning a job id
DATABASE_URL = os.environ.get("DATABASE_URL", "")
REDIS_URL = os.environ.get("REDIS_URL", "")
QUEUE_NAME = os.environ.get("QUEUE_NAME", "price-agent")
FREE_RENDER = os.environ.get("FREE_RENDER", "false").lower() in ("1", "true", "yes")
JOB_TIMEOUT = _int("JOB_TIMEOUT_SECONDS", 180)
JOB_RESULT_TTL = _int("JOB_RESULT_TTL_SECONDS", 3600)
JOB_FAILURE_TTL = _int("JOB_FAILURE_TTL_SECONDS", 86400)
DB_PATH = os.environ.get("DATABASE_PATH", "data/price-agent.db")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "priceagent.onrender.com").rstrip("/")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
API_KEYS = [k.strip() for k in os.environ.get("API_KEYS", "").split(",") if k.strip()]   # secret
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")                                             # secret
NOMINATIM_CONTACT = os.environ.get("NOMINATIM_CONTACT", "set-NOMINATIM_CONTACT")
EXTRA_ORIGINS = [o for o in os.environ.get("EXTRA_ORIGINS", "").split(",") if o]


def problems() -> list[str]:
    """Configuration mistakes. Fatal in staging/production, warnings elsewhere."""
    p = []
    if PRODUCTION_LIKE and not DATABASE_URL:
        p.append("DATABASE_URL is required in staging/production")
    if PRODUCTION_LIKE and not REDIS_URL and not FREE_RENDER:
        p.append("REDIS_URL is required in staging/production unless FREE_RENDER is enabled")
    if AI_PROVIDER in ("gemini", "gemini,openai", "openai,gemini") and not os.environ.get("GEMINI_API_KEY"):
        p.append("GEMINI_API_KEY is required for the configured Gemini provider")
    if AI_PROVIDER in ("openai", "gemini,openai", "openai,gemini") and not os.environ.get("OPENAI_API_KEY"):
        p.append("OPENAI_API_KEY is required for the configured OpenAI provider")
    if AI_PROVIDER == "auto" and not any([
        os.environ.get("GROQ_API_KEY"),
        os.environ.get("GEMINI_API_KEY"),
        os.environ.get("HF_TOKEN"),
        os.environ.get("OPENAI_API_KEY"),
        os.environ.get("OLLAMA_API_KEY"),
        os.environ.get("OLLAMA_BASE_URL"),
    ]):
        p.append("No AI provider credentials or local Ollama endpoint are configured")
    if "groq" in AI_PROVIDER and not os.environ.get("GROQ_API_KEY"):
        p.append("GROQ_API_KEY is required for the configured Groq provider")
    if "huggingface" in AI_PROVIDER and not os.environ.get("HF_TOKEN"):
        p.append("HF_TOKEN is required for the configured Hugging Face provider")
    if "ollama" in AI_PROVIDER and not os.environ.get("OLLAMA_API_KEY") and not OLLAMA_BASE_URL.startswith(("http://localhost", "http://127.0.0.1")):
        p.append("OLLAMA_API_KEY is required for a remote Ollama endpoint")
    if PRODUCTION_LIKE:
        if not PUBLIC_URL.startswith("https://"):
            p.append("PUBLIC_URL must be an https URL")
        if not os.path.isabs(DB_PATH):
            p.append("DATABASE_PATH must be an absolute path on a persistent disk")
        if NOMINATIM_CONTACT.startswith("set-"):
            p.append("NOMINATIM_CONTACT must be your email or website")
        if any(len(k) < 20 for k in API_KEYS) or (ADMIN_KEY and len(ADMIN_KEY) < 20):
            p.append("API_KEYS and ADMIN_KEY must be random strings of 20+ characters")
    return p


def assert_ready() -> None:
    """Raise on bad config in staging/production; log warnings elsewhere."""
    found = problems()
    if found and PRODUCTION_LIKE:
        raise RuntimeError("Configuration problems: " + "; ".join(found))
    if found and APP_ENV != "test":
        for f in found:
            logging.getLogger("price-agent").warning("config: %s", f)


def summary() -> dict:
    """Non-secret settings, safe to log at start-up."""
    return {"env": APP_ENV, "public_url": PUBLIC_URL, "google_signin": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET), "provider": AI_PROVIDER, "model": MODEL,
            "gemini_model": GEMINI_MODEL, "openai_model": OPENAI_MODEL, "groq_model": GROQ_MODEL, "hf_model": HF_MODEL, "ollama_model": OLLAMA_MODEL, "workers": WORKERS, "free_render": FREE_RENDER, "db": DB_PATH,
            "searches": MAX_SEARCHES, "insight_searches": MAX_INSIGHT_SEARCHES, "cache_ttl": CACHE_TTL,
            "limits": [RATE_LIMIT, USER_RATE_LIMIT, KEY_RATE_LIMIT], "partner_keys": len(API_KEYS),
            "admin_enabled": bool(ADMIN_KEY)}
