"""Polite, safe page fetching: public hosts only, robots.txt respected, size/time limits, no redirects."""
import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

UA = "PriceAgentCollector/1.0 (+respects robots.txt)"
MAX_BYTES = 1_500_000


class FetchError(Exception):
    pass


def is_public_url(url: str) -> bool:
    u = urllib.parse.urlsplit(url)
    if u.scheme not in ("http", "https") or not u.hostname or u.port not in (None, 80, 443) or u.username:
        return False
    try:
        ips = {i[4][0] for i in socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80))}
        return bool(ips) and all(ipaddress.ip_address(ip).is_global for ip in ips)
    except (socket.gaierror, ValueError):
        return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        raise FetchError("redirects are not followed")


def fetch(url: str) -> str:
    if not is_public_url(url):
        raise FetchError("not a public http(s) address")
    try:
        with urllib.request.build_opener(_NoRedirect).open(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=15) as r:
            data = r.read(MAX_BYTES + 1)
    except FetchError:
        raise
    except (urllib.error.URLError, OSError) as e:
        raise FetchError(f"fetch failed: {e}") from e
    if len(data) > MAX_BYTES:
        raise FetchError("response too large")
    return data.decode("utf-8", "replace")


def allowed(url: str) -> bool:
    """True if robots.txt allows our user agent (or none can be read)."""
    u = urllib.parse.urlsplit(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.parse(fetch(f"{u.scheme}://{u.netloc}/robots.txt").splitlines())
    except FetchError:
        return True
    return rp.can_fetch(UA, url)
