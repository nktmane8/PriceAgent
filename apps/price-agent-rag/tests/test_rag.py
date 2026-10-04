import socket

import pytest

from ragapp import answer, config, ingest, llm, retrieve, store
from ragapp.chunk import chunk_text

PHONE = "Phone X review. The battery lasts two full days and charging is fast. The camera is good in daylight but weak at night."
LAPTOP = "Laptop Y review. The keyboard is comfortable and the screen is bright, but the fan is loud under load."


def seed(c):
    ingest.add_text(c, "Phone X review", PHONE, {"product": "Phone X", "country": "India", "source_type": "publication", "url": "https://paper.example/x"})
    ingest.add_text(c, "Laptop Y review", LAPTOP, {"product": "Laptop Y", "country": "UK", "source_type": "video", "url": "https://video.example/y"})


def test_chunking_overlaps_and_handles_empty():
    words = " ".join(f"w{i}" for i in range(30))
    ch = chunk_text(words, size=10, overlap=3)
    assert ch[0].split()[-3:] == ch[1].split()[:3] and len(ch) == 4
    assert chunk_text("   ") == []


def test_keyword_search_ranks_filters_and_is_injection_safe(conn):
    seed(conn)
    hits = retrieve.search(conn, "how is the battery life?", 3)
    assert hits[0]["title"] == "Phone X review" and hits[0]["via"] == ["keyword"]
    assert retrieve.search(conn, "battery", 3, product="laptop") == []          # product filter
    assert retrieve.search(conn, "screen", 3, country="india") == []             # country filter
    assert retrieve.search(conn, '" OR 1=1 -- NEAR(', 3) == []                   # FTS syntax cannot be injected


def test_duplicate_text_is_not_indexed_twice(conn):
    a = ingest.add_text(conn, "t", PHONE)
    b = ingest.add_text(conn, "t", PHONE)
    assert a[0] == b[0] and a[2] is True and b[2] is False


def test_ask_without_sources_never_calls_the_model(conn, monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai_compatible")
    monkeypatch.setattr(llm, "chat", lambda m: (_ for _ in ()).throw(AssertionError("model must not be called")))
    r = answer.ask(conn, "what about the toaster?")
    assert r["mode"] == "no_sources" and r["grounded"] is False


def test_llm_answer_citations_are_validated(conn, monkeypatch):
    seed(conn)
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai_compatible")
    seen = {}
    monkeypatch.setattr(llm, "chat", lambda m: seen.update(m=m) or "Battery lasts two days [1] and more [9].")
    r = answer.ask(conn, "battery of phone x", product="Phone X")
    assert r["mode"] == "llm" and "[9]" not in r["answer"] and [c["n"] for c in r["citations"]] == [1]
    assert seen["m"][0]["role"] == "system" and "ONLY the numbered sources" in seen["m"][0]["content"]


def test_ungrounded_or_failing_llm_falls_back_to_extractive(conn, monkeypatch):
    seed(conn)
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai_compatible")
    monkeypatch.setattr(llm, "chat", lambda m: "It is the best phone ever.")           # no citations
    assert answer.ask(conn, "battery")["mode"] == "llm_answer_discarded_no_citations"
    monkeypatch.setattr(llm, "chat", lambda m: (_ for _ in ()).throw(llm.LLMError("down")))
    assert answer.ask(conn, "battery")["mode"] == "llm_unavailable"
    monkeypatch.setattr(config, "LLM_PROVIDER", "none")
    r = answer.ask(conn, "battery")
    assert r["mode"] == "extractive" and "[1]" in r["answer"]


def fake_embed(texts):  # deterministic bag-of-words vectors, no model needed
    vocab = ["battery", "camera", "keyboard", "screen", "fan", "charging", "days"]
    return [[float(t.lower().count(w)) for w in vocab] for t in texts]


def test_hybrid_retrieval_merges_keyword_and_vector(conn, monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai_compatible")
    monkeypatch.setattr(config, "EMBED_MODEL", "fake")
    monkeypatch.setattr(llm, "embed", fake_embed)
    seed(conn)
    hits = retrieve.search(conn, "battery", 3)
    assert hits[0]["title"] == "Phone X review" and set(hits[0]["via"]) == {"keyword", "vector"}
    monkeypatch.setattr(llm, "embed", lambda t: (_ for _ in ()).throw(llm.LLMError("down")))
    assert retrieve.search(conn, "battery", 3)[0]["via"] == ["keyword"]                 # degrades gracefully


def test_ssrf_guard(monkeypatch):
    for bad in ["http://127.0.0.1/", "http://localhost/", "http://169.254.169.254/latest", "file:///etc/passwd",
                "http://10.0.0.5/", "https://example.com:8443/", "ftp://example.com/"]:
        assert ingest.is_public_url(bad) is False, bad
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    assert ingest.is_public_url("https://shop.example/p") is True
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.1.2.3", 443))])
    assert ingest.is_public_url("https://sneaky.example/p") is False                    # public name, private IP


def test_html_rss_and_atom_ingest(conn, monkeypatch):
    title, text = ingest.html_to_text("<html><title>T</title><script>evil()</script><body><p>Hello</p><style>x{}</style>World</body></html>")
    assert title == "T" and text == "Hello World"
    rss = b"<rss><channel><item><title>Phone X test</title><link>https://p.example/1</link><description>&lt;b&gt;Great&lt;/b&gt; battery life overall</description></item></channel></rss>"
    atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom review</title><link href="https://p.example/2"/><summary>Solid build quality and display</summary></entry></feed>'
    monkeypatch.setattr(ingest, "safe_fetch", lambda url: rss)
    assert ingest.add_rss(conn, "https://p.example/feed", {"product": "Phone X"}) == 1
    monkeypatch.setattr(ingest, "safe_fetch", lambda url: atom)
    assert ingest.add_rss(conn, "https://p.example/atom") == 1
    assert {d["title"] for d in store.list_documents(conn)} == {"Phone X test", "Atom review"}


def test_api_admin_ingest_ask_delete_and_rate_limit(client, monkeypatch):
    body = {"title": "Phone X review", "text": PHONE, "product": "Phone X", "source_type": "publication"}
    assert client.post("/api/ingest/text", json=body).status_code == 401
    ok = client.post("/api/ingest/text", json=body, headers={"X-Admin-Key": "adm"})
    assert ok.status_code == 200 and ok.json()["created"] is True
    r = client.post("/api/ask", json={"question": "How is the battery?"}).json()
    assert r["citations"][0]["title"] == "Phone X review"
    assert client.post("/api/ingest/url", json={"url": "http://127.0.0.1/x"}, headers={"X-Admin-Key": "adm"}).status_code == 422
    prices = {"country": "India", "rows": [{"product": "Phone X", "store": "Shop A", "price": 999.5, "currency": "INR", "date": "2026-10-01"}]}
    assert client.post("/api/ingest/prices", json=prices, headers={"X-Admin-Key": "adm"}).json()["rows"] == 1
    cheap = client.post("/api/ask", json={"question": "which store lists Phone X price?", "product": "Phone X"}).json()
    assert "Shop A" in cheap["answer"]
    doc = client.get("/api/documents").json()[0]["id"]
    assert client.delete(f"/api/documents/{doc}", headers={"X-Admin-Key": "adm"}).status_code == 200
    monkeypatch.setattr(config, "ASK_RATE_LIMIT", 0)
    assert client.post("/api/ask", json={"question": "anything at all"}).status_code == 429
