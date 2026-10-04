"""Small shared helpers."""
from fastapi import Request

from constants import DOMAIN_RE, PLACE_RE, PRODUCT_MAX, PRODUCT_MIN


def client_ip(request: Request) -> str:
    # Behind Render's proxy the real client is the first X-Forwarded-For entry.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def validate(p):
    """Shared input rules for REST and MCP. Returns an error message or None."""
    if not PRODUCT_MIN <= len(p["product"]) <= PRODUCT_MAX:
        return f"Product name must be {PRODUCT_MIN}-{PRODUCT_MAX} characters."
    if not PLACE_RE.match(p["country"]) or (p["city"] and not PLACE_RE.match(p["city"])):
        return "Country and city may contain only letters, numbers and basic punctuation (2-60 chars)."
    if any(not DOMAIN_RE.match(s) for s in p["sites"]):
        return "Preferred stores must be plain domains like example.com."
    return None
