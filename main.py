"""Price Comparison Agent - API wiring.
Google-only identity with signed JWT bearer access tokens. Every business API requires a valid JWT.
MCP is protected by the same OAuth authorization server."""
import hmac
import json
import logging
import time
import threading
import urllib.error
import urllib.request
from pathlib import Path

_LOCATION_LOCK = threading.Lock()
_LOCATION_LAST_REQUEST = 0.0
from typing import Literal
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.routing import Mount

import config
from product_identity import normalize
import db
import jobs
import oauth
import analytics
from constants import KIND_INSIGHTS, KIND_PRICES, MAX_SITES
from mcp_app import mcp
from util import client_ip, validate

logging.basicConfig(level=config.LOG_LEVEL)
config.assert_ready()  # fail fast on bad production config
logging.getLogger("price-agent").info("Starting with %s", config.summary())
db.init()            # create tables (idempotent)
db.recover_stale_jobs(max(300, config.JOB_TIMEOUT * 2))
jobs.start_purger()  # background cleanup thread

BASE = Path(__file__).parent
api = FastAPI(title="Price Comparison Agent", servers=[{"url": config.PUBLIC_URL}],
              description="Region-aware price comparison across online and local stores.")
api.include_router(oauth.router)

oauth2 = OAuth2AuthorizationCodeBearer(
    authorizationUrl=config.PUBLIC_URL + "/oauth/authorize", tokenUrl=config.PUBLIC_URL + "/oauth/token",
    scopes={config.SCOPE: "Compare prices"}, auto_error=False)
CHALLENGE = {"WWW-Authenticate": f'Bearer resource_metadata="{config.PUBLIC_URL}/.well-known/oauth-protected-resource"'}

class CompareRequest(BaseModel):
    """Request body for a price or insight lookup (validated by pydantic)."""
    product: str = Field(..., min_length=3, max_length=120)
    country: str = Field(..., min_length=2, max_length=60)
    city: str | None = Field(default=None, max_length=60)
    sites: list[str] | None = Field(default=None, max_length=MAX_SITES)  # optional preferred domains
    kind: Literal["prices", "insights"] = KIND_PRICES  # insights = reviews + similar products


def params_of(req: CompareRequest) -> dict:
    """Turn a request into a clean params dict and validate it (422 on bad input)."""
    p = {"product": req.product.strip(), "country": req.country.strip(), "city": (req.city or "").strip(),
         "sites": [s.strip().lower() for s in (req.sites or [])], "kind": req.kind}
    err = validate(p)
    if err:
        raise HTTPException(422, err)
    return p


def start(params, principal, limit):
    """Submit a job for this caller or raise HTTP 429; insights use a separate allowance."""
    if params["kind"] == KIND_INSIGHTS:
        principal += ":insights"  # separate allowance so reviews do not use up price comparisons
    try:
        return jobs.submit(params, principal, limit)
    except jobs.RateLimited as e:
        raise HTTPException(429, f"Hourly limit reached. Try again in about {e.minutes} minutes.")
    except jobs.QueueUnavailable:
        raise HTTPException(503, "The job queue is temporarily unavailable. Please retry.", headers={"Retry-After": "10"})


def jwt_user(bearer: str | None = Depends(oauth2)):
    """Require a valid signed JWT for every business API."""
    row = oauth.verify_access_token(bearer) if bearer else None
    if not row or row["resource"] != config.PUBLIC_URL:
        raise HTTPException(401, "Valid Google-authenticated JWT bearer token required.", headers=CHALLENGE)
    return "user:" + str(row["user_id"]), config.USER_RATE_LIMIT

partner = jwt_user
web_user = jwt_user
@api.middleware("http")
async def security_headers(request, call_next):
    """Middleware: add nosniff and no-referrer headers to every response."""
    r = await call_next(request)
    r.headers.setdefault("X-Content-Type-Options", "nosniff")
    r.headers.setdefault("Referrer-Policy", "no-referrer")
    return r


def respond(job):
    """Map job lifecycle states to honest HTTP responses."""
    body = jobs.view(job)
    if job["status"] == "done":
        return JSONResponse(body, status_code=200)
    if job["status"] == "error":
        # The comparison failed while calling an upstream dependency (normally
        # the AI/search provider). Do not report a failed job as HTTP 200.
        return JSONResponse(body, status_code=502)
    return JSONResponse(body, status_code=202)


# ---- first-party web UI ------------------------------------------------------------
@api.get("/api/v1/me", operation_id="currentUser", summary="Validate the current OAuth login")
def current_user(bearer: str | None = Depends(oauth2)):
    """Return the authenticated user's identity; the web UI uses this as its login check."""
    row = oauth.verify_access_token(bearer) if bearer else None
    if not row or row["resource"] not in (None, "", config.PUBLIC_URL):
        raise HTTPException(401, "Valid OAuth login required.", headers=CHALLENGE)
    return {"authenticated": True, "user_id": str(row["user_id"]), "scope": row["scope"],
            "expires_at": int(row["expires_at"])}


@api.post("/api/jobs", include_in_schema=False)
def create_job(req: CompareRequest, who=Depends(web_user)):
    """Legacy web endpoint: requires OAuth login."""
    principal, limit = who
    jid = start(params_of(req), principal, limit)
    return respond(db.job_get(jid))


@api.get("/api/jobs/{job_id}", include_in_schema=False)
def read_job(job_id: str, who=Depends(web_user)):
    """Legacy web polling endpoint: requires OAuth and caller-owned job."""
    principal, _ = who
    job = db.job_get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job.")
    if principal.startswith("user:") and job.get("principal", "").split(":")[:2] != principal.split(":")[:2]:
        raise HTTPException(403, "You do not have access to this job.")
    return respond(job)


# ---- AI apps / partners ------------------------------------------------------------
@api.post("/api/v1/compare", operation_id="comparePrices", summary="Compare prices for a product across stores in a region")
def compare_v1(req: CompareRequest, who=Depends(partner)):
    """Waits up to JOB_WAIT_SECONDS. Returns 200 with the result, or 202 with a job_id to poll at /api/v1/jobs/{id}."""
    jid = start(params_of(req), *who)
    return respond(jobs.wait(jid, config.JOB_WAIT))


@api.get("/api/v1/jobs/{job_id}", operation_id="getComparison", summary="Get a comparison job's status or result")
def job_v1(job_id: str, who=Depends(partner)):
    """AI apps/partners: poll a job (OAuth or API key)."""
    job = db.job_get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job.")
    principal, _ = who
    if principal.startswith("user:") and job.get("principal", "").split(":")[:2] != principal.split(":")[:2]:
        raise HTTPException(403, "You do not have access to this job.")
    return respond(job)


@api.post("/api/v1/account/delete", operation_id="deleteAccount", summary="Delete my account and all data tied to it")
def delete_account(bearer: str | None = Depends(oauth2)):
    """Delete the signed-in user's account; Google authentication is the account identity proof."""
    row = oauth.verify_access_token(bearer) if bearer else None
    if not row or row["resource"] != config.PUBLIC_URL:
        raise HTTPException(401, "Valid Google-authenticated JWT required.", headers=CHALLENGE)
    res = oauth.delete_user(row["user_id"])
    if res == "limited":
        raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
    return {"deleted": True}

# ---- helpers ---------------------------------------------------------------------------
@api.get(
    "/api/locate",
    summary="Reverse geocode coordinates",
    description="Convert latitude and longitude into a country and city using OpenStreetMap Nominatim.",
)
def locate(
    request: Request,
    who=Depends(jwt_user),
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
):
    """Coordinates -> country + city via OpenStreetMap Nominatim.

    The lookup is rounded to ~1 km and cached for CACHE_TTL seconds. Provider
    failures are treated as a temporary dependency outage rather than exposing
    a generic 502 to the browser.
    """
    cache_key = "location:" + str(round(lat, 2)) + ":" + str(round(lon, 2))

    # Cache hits do not call Nominatim and should not consume the per-IP quota.
    cached = db.cache_get(cache_key)
    if cached is not None:
        return cached

    wait = db.rate_check("loc:" + client_ip(request), config.LOCATE_LIMIT)
    if wait:
        raise HTTPException(429, f"Too many lookups. Try again in about {wait} minutes.")

    url = "https://nominatim.openstreetmap.org/reverse?" + urlencode({
        "format": "jsonv2",
        "lat": round(lat, 2),
        "lon": round(lon, 2),
        "zoom": 10,
        "accept-language": "en",
    })
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"price-agent/1.0 ({config.NOMINATIM_CONTACT})",
            "Accept": "application/json",
        },
    )

    logger = logging.getLogger("price-agent")
    addr = None
    last_error = None
    retry_after = None

    # Nominatim is a shared public service. Pace every provider request in this
    # process so retries cannot create a burst. The lock is held only while
    # pacing, never while doing network I/O.
    def pace_location_request():
        global _LOCATION_LAST_REQUEST
        with _LOCATION_LOCK:
            elapsed = time.monotonic() - _LOCATION_LAST_REQUEST
            if elapsed < 1.1:
                time.sleep(1.1 - elapsed)
            _LOCATION_LAST_REQUEST = time.monotonic()

    # Nominatim is an external dependency. Retry only transient failures,
    # with a short bounded timeout so the browser is not left waiting.
    for attempt in range(2):
        pace_location_request()
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status != 200:
                    raise urllib.error.HTTPError(
                        url, response.status, f"Unexpected status {response.status}",
                        response.headers, None,
                    )
                payload = json.load(response)
                if not isinstance(payload, dict):
                    raise ValueError("Nominatim returned a non-object JSON response")
                addr = payload.get("address") or {}
                if not isinstance(addr, dict):
                    raise ValueError("Nominatim returned an invalid address payload")
            break
        except urllib.error.HTTPError as e:
            last_error = e
            retry_after = e.headers.get("Retry-After")
            transient = e.code in (429, 500, 502, 503, 504)
            logger.warning(
                "location provider HTTP failure: status=%s attempt=%s/2 retryable=%s",
                e.code, attempt + 1, transient,
            )
            if not transient or attempt == 1:
                break
            try:
                delay = min(4, max(1, int(retry_after))) if retry_after else 2 ** attempt
            except (TypeError, ValueError):
                delay = 2 ** attempt
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as e:
            last_error = e
            logger.warning(
                "location provider failure: type=%s attempt=%s/2",
                type(e).__name__, attempt + 1,
            )
            if attempt == 1:
                break
            time.sleep(2 ** attempt)

    if addr is None:
        logger.warning(
            "location provider unavailable after retries: error=%r retry_after=%s",
            last_error, retry_after,
        )
        headers = {"Retry-After": "10"}
        if retry_after and str(retry_after).isdigit():
            headers["Retry-After"] = retry_after
        raise HTTPException(
            503,
            "Location service is temporarily unavailable. Type your country and city instead.",
            headers=headers,
        )

    if not addr.get("country"):
        raise HTTPException(404, "No country found for that location. Type it instead.")

    city = (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("state_district")
        or addr.get("county")
        or addr.get("state")
        or ""
    )
    result = {"country": addr["country"], "city": city}
    db.cache_set(cache_key, result)
    return result


@api.get("/api/product/resolve", include_in_schema=False)
def resolve_product(product: str = Query(..., min_length=3, max_length=120), who=Depends(jwt_user)):
    """Resolve shopping text to PriceAgent's conservative canonical product identity."""
    identity = normalize(product.strip())
    stored = db.product_get(identity["canonical_key"])
    return {
        "canonical_key": identity["canonical_key"],
        "product": identity["display_name"],
        "brand": identity["brand"],
        "variant": identity["variant"],
        "storage": identity["storage"],
        "color": identity["color"],
        "known": stored is not None,
        "product_id": stored["id"] if stored else None,
    }


@api.get("/api/history", include_in_schema=False)
def history(request: Request, product: str = Query(..., min_length=3, max_length=120), country: str = Query(..., min_length=2, max_length=60),
            city: str = Query("", max_length=60), who=Depends(jwt_user)):
    """Lowest recorded prices for a product and region over the last 90 days; JWT required."""
    p = {"product": product.strip(), "country": country.strip(), "city": city.strip(), "sites": []}
    err = validate(p)
    if err:
        raise HTTPException(422, err)
    if db.rate_check("hist:" + client_ip(request), 60):
        raise HTTPException(429, "Too many requests.")
    return db.history_summary(db.history_key(p["product"], p["country"], p["city"]))


@api.get("/api/admin/analytics", include_in_schema=False)
def admin_analytics(days: int = Query(30, ge=1, le=90), x_admin_key: str | None = Header(default=None)):
    if not config.ADMIN_KEY or not x_admin_key or not hmac.compare_digest(x_admin_key, config.ADMIN_KEY):
        raise HTTPException(401, "Admin key required.")
    return analytics.dashboard(days)

@api.get("/api/admin/stats", include_in_schema=False)
def admin_stats(x_admin_key: str | None = Header(default=None)):
    """Admin metrics (needs the X-Admin-Key header)."""
    if not config.ADMIN_KEY or not x_admin_key or not hmac.compare_digest(x_admin_key, config.ADMIN_KEY):
        raise HTTPException(401, "Admin key required.")
    return db.stats()


@api.get("/healthz", include_in_schema=False)
def healthz():
    """Health check; also proves the database is reachable."""
    db.cache_get("health")  # also proves the database is reachable
    return {"status": "ok"}


api.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


def _index_html() -> str:
    """Render the public HTML with deployment-specific analytics/SEO settings."""
    html = (BASE / "static" / "index.html").read_text(encoding="utf-8")
    html = html.replace("__GA4_MEASUREMENT_ID__", config.GA4_MEASUREMENT_ID)
    verification = config.GOOGLE_SEARCH_CONSOLE_VERIFICATION.strip()
    if verification:
        html = html.replace("</head>", '<meta name="google-site-verification" content="' + verification + '">\\n</head>')
    return html


@api.get("/", include_in_schema=False)
def index():
    """Serve the SEO/analytics-enabled web page."""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(_index_html())


@api.get("/robots.txt", include_in_schema=False)
def robots():
    """Public crawler policy."""
    return HTMLResponse(
        "User-agent: *\\nAllow: /\\nDisallow: /api/\\nDisallow: /oauth/\\nSitemap: " + config.PUBLIC_URL.rstrip("/") + "/sitemap.xml\\n",
        media_type="text/plain",
    )


@api.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    """Minimal XML sitemap for the public homepage."""
    from fastapi.responses import Response
    loc = config.PUBLIC_URL.rstrip("/") + "/"
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>' + loc + '</loc></url></urlset>'
    return Response(content=xml, media_type="application/xml")


@api.get("/oauth/callback", include_in_schema=False)
def oauth_callback():
    """OAuth browser-client redirect target; the page completes the PKCE token exchange."""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(_index_html())


# The MCP app is the outer ASGI app (it owns /mcp and its auth middleware); everything else goes to `api`.
app = mcp.streamable_http_app()
app.router.routes.append(Mount("/", app=api))
