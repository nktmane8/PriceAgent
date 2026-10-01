"""Price Comparison Agent - API wiring.
Web page -> /api/jobs (async, per-IP limit). AI apps -> /api/v1/* (OAuth bearer or API key) and /mcp (OAuth)."""
import hashlib
import hmac
import json
import logging
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import APIKeyHeader, OAuth2AuthorizationCodeBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.routing import Mount

import config
import db
import jobs
import oauth
from mcp_app import mcp
from util import client_ip, validate

logging.basicConfig(level=logging.INFO)
db.init()            # create tables (idempotent)
jobs.start_purger()  # background cleanup thread

BASE = Path(__file__).parent
api = FastAPI(title="Price Comparison Agent", servers=[{"url": config.PUBLIC_URL}],
              description="Region-aware price comparison across online and local stores.")
api.include_router(oauth.router)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
oauth2 = OAuth2AuthorizationCodeBearer(
    authorizationUrl=config.PUBLIC_URL + "/oauth/authorize", tokenUrl=config.PUBLIC_URL + "/oauth/token",
    scopes={config.SCOPE: "Compare prices"}, auto_error=False)
CHALLENGE = {"WWW-Authenticate": f'Bearer resource_metadata="{config.PUBLIC_URL}/.well-known/oauth-protected-resource"'}


class CompareRequest(BaseModel):
    product: str = Field(..., min_length=3, max_length=120)
    country: str = Field(..., min_length=2, max_length=60)
    city: str | None = Field(default=None, max_length=60)
    sites: list[str] | None = Field(default=None, max_length=8)  # optional preferred domains


def params_of(req: CompareRequest) -> dict:
    p = {"product": req.product.strip(), "country": req.country.strip(), "city": (req.city or "").strip(),
         "sites": [s.strip().lower() for s in (req.sites or [])]}
    err = validate(p)
    if err:
        raise HTTPException(422, err)
    return p


def start(params, principal, limit):
    try:
        return jobs.submit(params, principal, limit)
    except jobs.RateLimited as e:
        raise HTTPException(429, f"Hourly limit reached. Try again in about {e.minutes} minutes.")


def partner(key: str | None = Depends(api_key_header), bearer: str | None = Depends(oauth2)):
    """Who is calling /api/v1? OAuth user (preferred) or a partner API key. Returns (principal, limit)."""
    if bearer:
        row = oauth.verify_access_token(bearer)
        if row and row["resource"] in (None, "", config.PUBLIC_URL):
            return "user:" + str(row["user_id"]), config.USER_RATE_LIMIT
    if key and any(hmac.compare_digest(key, k) for k in config.API_KEYS):
        return "key:" + hashlib.sha256(key.encode()).hexdigest()[:12], config.KEY_RATE_LIMIT
    raise HTTPException(401, "Sign in with OAuth or send a valid X-API-Key.", headers=CHALLENGE)


@api.middleware("http")
async def security_headers(request, call_next):
    r = await call_next(request)
    r.headers.setdefault("X-Content-Type-Options", "nosniff")
    r.headers.setdefault("Referrer-Policy", "no-referrer")
    return r


def respond(job):
    return JSONResponse(jobs.view(job), status_code=200 if job["status"] in ("done", "error") else 202)


# ---- web page (anonymous, per-IP limit) -----------------------------------------
@api.post("/api/jobs", include_in_schema=False)
def create_job(req: CompareRequest, request: Request):
    jid = start(params_of(req), "ip:" + client_ip(request), config.RATE_LIMIT)
    return respond(db.job_get(jid))


@api.get("/api/jobs/{job_id}", include_in_schema=False)
def read_job(job_id: str):
    job = db.job_get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job.")
    return respond(job)


# ---- AI apps / partners ------------------------------------------------------------
@api.post("/api/v1/compare", operation_id="comparePrices", summary="Compare prices for a product across stores in a region")
def compare_v1(req: CompareRequest, who=Depends(partner)):
    """Waits up to JOB_WAIT_SECONDS. Returns 200 with the result, or 202 with a job_id to poll at /api/v1/jobs/{id}."""
    jid = start(params_of(req), *who)
    return respond(jobs.wait(jid, config.JOB_WAIT))


@api.get("/api/v1/jobs/{job_id}", operation_id="getComparison", summary="Get a comparison job's status or result")
def job_v1(job_id: str, who=Depends(partner)):
    job = db.job_get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job.")
    return respond(job)


# ---- helpers ---------------------------------------------------------------------------
@api.get("/api/locate", include_in_schema=False)
def locate(request: Request, lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)):
    """Coordinates -> country + city via OpenStreetMap Nominatim. Rounded to ~1 km; not stored."""
    wait = db.rate_check("loc:" + client_ip(request), config.LOCATE_LIMIT)
    if wait:
        raise HTTPException(429, f"Too many lookups. Try again in about {wait} minutes.")
    url = "https://nominatim.openstreetmap.org/reverse?" + urlencode(
        {"format": "jsonv2", "lat": round(lat, 2), "lon": round(lon, 2), "zoom": 10, "accept-language": "en"})
    req = urllib.request.Request(url, headers={"User-Agent": f"price-agent/1.0 ({config.NOMINATIM_CONTACT})"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            addr = json.load(r).get("address", {})
    except Exception:
        raise HTTPException(502, "Could not look up your location. Type your country and city instead.")
    if not addr.get("country"):
        raise HTTPException(404, "No country found for that location. Type it instead.")
    city = (addr.get("city") or addr.get("town") or addr.get("village") or addr.get("state_district")
            or addr.get("county") or addr.get("state") or "")
    return {"country": addr["country"], "city": city}


@api.get("/api/admin/stats", include_in_schema=False)
def admin_stats(x_admin_key: str | None = Header(default=None)):
    if not config.ADMIN_KEY or not x_admin_key or not hmac.compare_digest(x_admin_key, config.ADMIN_KEY):
        raise HTTPException(401, "Admin key required.")
    return db.stats()


@api.get("/healthz", include_in_schema=False)
def healthz():
    db.cache_get("health")  # also proves the database is reachable
    return {"status": "ok"}


api.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


@api.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE / "static" / "index.html")


# The MCP app is the outer ASGI app (it owns /mcp and its auth middleware); everything else goes to `api`.
app = mcp.streamable_http_app()
app.router.routes.append(Mount("/", app=api))
