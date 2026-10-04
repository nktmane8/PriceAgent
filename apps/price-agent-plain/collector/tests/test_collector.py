import json
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import collect
import jsonld
import safefetch


def page(ld):
    return f'<html><head><script type="application/ld+json">{json.dumps(ld)}</script></head></html>'


def test_single_product_offer_and_stock_mapping():
    o = jsonld.extract_offers(page({"@type": "Product", "name": "P", "offers": {"@type": "Offer", "price": "1,299.00", "priceCurrency": "inr",
                                                                          "availability": "https://schema.org/InStock", "url": "https://s/p"}}))[0]
    assert (o["price"], o["currency"], o["in_stock"], o["url"]) == (1299.0, "INR", True, "https://s/p")
    out = jsonld.extract_offers(page({"@type": "Product", "offers": {"price": 5, "priceCurrency": "USD", "availability": "OutOfStock"}}))
    assert out[0]["in_stock"] is False


def test_graph_lists_aggregate_offers_and_bad_json():
    g = {"@graph": [{"@type": "WebSite"}, {"@type": ["Thing", "Product"], "name": "G", "offers": [
        {"price": "10", "priceCurrency": "EUR"}, {"@type": "AggregateOffer", "lowPrice": 8, "priceCurrency": "EUR"}]}]}
    assert [o["price"] for o in jsonld.extract_offers(page(g))] == [10.0, 8.0]
    assert jsonld.extract_offers('<script type="application/ld+json">{broken</script>') == []


def test_price_parsing_edge_cases():
    assert jsonld.parse_price("₹ 1,299") == 1299.0 and jsonld.parse_price("12,50") == 12.5 and jsonld.parse_price(True) is None
    assert jsonld.parse_price("free") is None and jsonld.parse_price(0) is None and jsonld.parse_price(-5) is None
    assert jsonld.parse_price("1.299,00") == 1299.0 and jsonld.parse_price("1.299.000") == 1299000.0 and jsonld.parse_price("Rs. 1,299.") == 1299.0
    assert jsonld.parse_price("1,299 - 1,499") is None and jsonld.parse_price("-5") is None


def test_meta_tag_fallback():
    html = '<meta property="product:price:amount" content="499.50"><meta property="product:price:currency" content="INR"><meta property="og:title" content="Gadget">'
    o = jsonld.extract_offers(html)[0]
    assert (o["price"], o["currency"], o["name"]) == (499.5, "INR", "Gadget")


def test_collect_reports_skips_and_builds_items():
    src = [{"product": "A", "store": "S", "country": "India", "url": "https://a.example/1"},
           {"product": "B", "store": "S", "country": "India", "url": "https://b.example/2"},
           {"product": "C", "store": "S", "country": "India", "url": "https://c.example/3"},
           {"product": "D", "store": "S", "country": "India", "url": "https://d.example/4"}]
    pages = {"https://a.example/1": page({"@type": "Product", "offers": {"price": 100, "priceCurrency": "INR"}}),
             "https://c.example/3": "<html>no data</html>"}

    def fake_fetch(u):
        if u not in pages:
            raise safefetch.FetchError("boom")
        return pages[u]
    items, report = collect.collect(src, fetch=fake_fetch, allowed=lambda u: "b.example" not in u, sleep=lambda s: None)
    assert [i["product"] for i in items] == ["A"] and items[0]["price"] == 100.0
    text = " | ".join(s for _, s in report)
    assert "robots.txt" in text and "no structured price" in text and "boom" in text


def test_csv_import(tmp_path):
    f = tmp_path / "p.csv"
    f.write_text("product,store,store_type,country,city,price,currency,instant_discount,discount_note,in_stock,url\n"
                 "Phone,Shop,local,India,Pune,100,inr,10,Bank offer,true,https://s/p\n")
    it = collect.items_from_csv(f)[0]
    assert it["currency"] == "INR" and it["instantDiscount"] == 10.0 and it["inStock"] is True and it["city"] == "Pune"


def test_ssrf_guard(monkeypatch):
    for bad in ["http://127.0.0.1/", "http://localhost/", "http://169.254.169.254/", "file:///etc/passwd", "https://example.com:8443/"]:
        assert safefetch.is_public_url(bad) is False
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.0.0.1", 443))])
    assert safefetch.is_public_url("https://sneaky.example/") is False
