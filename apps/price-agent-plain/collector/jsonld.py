"""Extract price offers from a product page WITHOUT AI: read schema.org JSON-LD (and meta tags) that shops publish for search engines."""
import json
import re
from html.parser import HTMLParser


class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks, self.meta, self._cur = [], {}, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._cur = []
        elif tag == "meta":
            key = a.get("property") or a.get("name")
            if key and a.get("content"):
                self.meta[key] = a["content"]

    def handle_data(self, data):
        if self._cur is not None:
            self._cur.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._cur is not None:
            self.blocks.append("".join(self._cur))
            self._cur = None


def parse_price(v):
    """'1,299.00', '₹ 1299', '1.299,00', 1299 -> float. None if not ONE usable positive price (ranges, negatives, text)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    if not isinstance(v, str) or v.strip().startswith("-"):
        return None
    runs = re.findall(r"\d[\d.,]*\d|\d", v)
    if len(runs) != 1:
        return None                                   # no number, or a range like "1,299 - 1,499"
    s = runs[0]
    commas, dots = s.count(","), s.count(".")
    if commas and dots:                               # both present: the last separator is the decimal one
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif commas == 1 and len(s.split(",")[1]) <= 2:
        s = s.replace(",", ".")                       # 12,50 -> decimal comma
    elif commas:
        s = s.replace(",", "")                        # 1,299 or 1,299,000 -> thousands
    elif dots > 1:
        s = s.replace(".", "")                        # 1.299.000 -> thousands
    try:
        n = float(s)
    except ValueError:
        return None
    return n if n > 0 else None


def stock(avail):
    a = str(avail or "").lower()
    if "outofstock" in a or "soldout" in a or "discontinued" in a:
        return False
    if "instock" in a or "limitedavailability" in a or "onlineonly" in a:
        return True
    return None


def _walk(node):
    if isinstance(node, list):
        for x in node:
            yield from _walk(x)
    elif isinstance(node, dict):
        yield node
        for v in node.values():
            if isinstance(v, (list, dict)):
                yield from _walk(v)


def _is_type(node, name):
    t = node.get("@type")
    return name in (t if isinstance(t, list) else [t])


def extract_offers(html: str) -> list[dict]:
    """Return [{name, price, currency, in_stock, url}] found on the page (best first). Empty if the page has no structured data."""
    p = _Scripts()
    p.feed(html)
    out = []
    for block in p.blocks:
        try:
            data = json.loads(block)
        except (json.JSONDecodeError, ValueError):
            continue
        for node in _walk(data):
            if not _is_type(node, "Product"):
                continue
            offers = node.get("offers")
            for off in (offers if isinstance(offers, list) else [offers]):
                if not isinstance(off, dict):
                    continue
                price = parse_price(off.get("price", off.get("lowPrice")))
                if price:
                    out.append({"name": str(node.get("name") or "")[:200], "price": price,
                                "currency": str(off.get("priceCurrency") or "").upper()[:3],
                                "in_stock": stock(off.get("availability")), "url": off.get("url") or node.get("url")})
    if not out:  # fallback: Open Graph / product meta tags
        m = p.meta
        price = parse_price(m.get("product:price:amount") or m.get("og:price:amount"))
        if price:
            out.append({"name": m.get("og:title", ""), "price": price,
                        "currency": (m.get("product:price:currency") or m.get("og:price:currency") or "").upper()[:3],
                        "in_stock": stock(m.get("product:availability") or m.get("og:availability")), "url": m.get("og:url")})
    return out
