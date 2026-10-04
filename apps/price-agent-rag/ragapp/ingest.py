"""Getting documents in: plain text, price rows, RSS feeds and web pages. All fetching goes through safe_fetch."""
import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

from . import config, llm, store
from .chunk import chunk_text

UA = "PriceAgentRAGBot/1.0 (+respects robots.txt)"


class FetchError(Exception):
    pass


def is_public_url(url: str) -> bool:
    """http(s) on port 80/443 whose host resolves ONLY to public IPs (blocks localhost, LAN, cloud metadata)."""
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


def safe_fetch(url: str) -> bytes:
    """GET with SSRF protection, size and time limits, no redirects. (Residual risk: DNS rebinding between check and fetch.)"""
    if not is_public_url(url):
        raise FetchError("URL is not a public http(s) address")
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=10) as r:
            data = r.read(config.MAX_FETCH_BYTES + 1)
    except FetchError:
        raise
    except (urllib.error.URLError, OSError) as e:
        raise FetchError(f"fetch failed: {e}") from e
    if len(data) > config.MAX_FETCH_BYTES:
        raise FetchError("response too large")
    return data


def allowed_by_robots(url: str) -> bool:
    u = urllib.parse.urlsplit(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.parse(safe_fetch(f"{u.scheme}://{u.netloc}/robots.txt").decode("utf-8", "replace").splitlines())
    except FetchError:
        return True   # no readable robots.txt = no restrictions stated
    return rp.can_fetch(UA, url)


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.title, self._skip, self._in_title = [], "", 0, False

    def handle_starttag(self, tag, attrs):
        self._skip += tag in ("script", "style", "noscript")
        self._in_title = tag == "title"

    def handle_endtag(self, tag):
        self._skip -= tag in ("script", "style", "noscript") and self._skip > 0
        self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip and data.strip():
            self.parts.append(data.strip())


def html_to_text(html: str):
    p = _Text()
    p.feed(html)
    return p.title.strip(), " ".join(p.parts)


def add_text(c, title, text, meta=None):
    """Chunk, optionally embed, and store. Returns (doc_id, chunk_count, created)."""
    chunks = chunk_text(text, config.CHUNK_WORDS, config.CHUNK_OVERLAP)
    if not chunks:
        raise ValueError("no text to index")
    emb = None
    if llm.embeddings_enabled():
        try:
            emb = llm.embed(chunks)
        except llm.LLMError:
            emb = None            # still searchable by keyword
    doc_id, created = store.add_document(c, {**(meta or {}), "title": title}, chunks, emb)
    return doc_id, len(chunks), created


def add_url(c, url, meta=None):
    if not allowed_by_robots(url):
        raise FetchError("blocked by robots.txt")
    title, text = html_to_text(safe_fetch(url).decode("utf-8", "replace"))
    return add_text(c, title or url, text, {**(meta or {}), "url": url})


def add_rss(c, url, meta=None, limit=20):
    """Index feed items (title + summary) as separate documents. Feeds are a legitimate, structured way to get reviews."""
    root = ET.fromstring(safe_fetch(url))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item") or root.findall(".//a:entry", ns)
    n = 0
    for it in items[:limit]:
        g = lambda tag, atom=None: (it.findtext(tag) or (it.findtext(f"a:{atom or tag}", namespaces=ns)) or "").strip()
        link = g("link") or (it.find("a:link", ns).get("href") if it.find("a:link", ns) is not None else "")
        body = re.sub(r"<[^>]+>", " ", g("description", "summary") or g("content"))
        if body.strip() or g("title"):
            n += add_text(c, g("title") or link, f"{g('title')}. {body}", {**(meta or {}), "url": link,
                          "published": g("pubDate", "updated")})[2]
    return n
