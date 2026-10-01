"""Small shared helpers."""
import re

from fastapi import Request

PLACE_RE = re.compile(r"^[\w\s.,'&()-]{2,60}$")  # country / city whitelist


def client_ip(request: Request) -> str:
    # Behind Render's proxy the real client is the first X-Forwarded-For entry.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def validate(p):
    """Shared input rules (also used by the REST API)."""
    place = PLACE_RE
    if not 3 <= len(p["product"]) <= 120:
        return "Product name must be 3-120 characters."
    if not place.match(p["country"]) or (p["city"] and not place.match(p["city"])):
        return "Country and city may contain only letters, numbers and basic punctuation (2-60 chars)."
    if any(not re.match(r"^[a-z0-9.-]{3,60}\.[a-z]{2,}$", s) for s in p["sites"]):
        return "Preferred stores must be plain domains like example.com."
    return None
