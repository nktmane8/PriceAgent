"""Settings. Precedence: real env vars > .env > env/.env.<APP_ENV>. No secrets in committed files."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(path: Path):
    if path.is_file():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


_load(ROOT / ".env")
APP_ENV = os.environ.get("APP_ENV", "development")
_load(ROOT / "env" / f".env.{APP_ENV}")


def _i(n, d):
    return int(os.environ.get(n, d))


DB_PATH = os.environ.get("DATABASE_PATH", "data/rag.db")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")                 # secret; ingest/delete need it
# LLM: any OpenAI-compatible server. Free local option: Ollama (http://localhost:11434/v1). "none" = no generation.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "none")       # none | openai_compatible
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")
LLM_MODEL = os.environ.get("LLM_MODEL", "llama3.2:3b")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")             # secret, only if your provider needs one
EMBED_MODEL = os.environ.get("EMBED_MODEL", "")             # empty = keyword search only (BM25)
LLM_TIMEOUT = _i("LLM_TIMEOUT", 120)
ASK_RATE_LIMIT = _i("ASK_RATE_LIMIT", 30)                   # questions per IP per hour
TOP_K = _i("TOP_K", 5)
CHUNK_WORDS, CHUNK_OVERLAP = _i("CHUNK_WORDS", 120), _i("CHUNK_OVERLAP", 20)
MAX_FETCH_BYTES = _i("MAX_FETCH_BYTES", 1_000_000)
